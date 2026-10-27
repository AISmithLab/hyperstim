"""The collector (plan 013): which uploads it takes, in what order, and what it writes."""

import csv
import json
import random
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hyperstim_api.collector import sampling
from hyperstim_api.collector.collector import DAY_S, QUERIES, Collector, Settings, load_classifier
from hyperstim_api.collector.sampling import Details
from hyperstim_api.collector.seed import seed
from hyperstim_api.collector.store import Store
from hyperstim_api.collector.youtube import ApiError, DataApi, OutOfUnits
from hyperstim_api.dataset import collected_files, load_dataset
from hyperstim_api.scoring import FEATURES
from tests.conftest import FakePipeline, video_row, write_dataset

NOW = 1_793_000_000.0  # 2026-10-26
CHANNEL = "UC" + "a" * 22


# --- the store -----------------------------------------------------------------------------


def test_a_transaction_commits_only_a_finished_block(tmp_path: Path) -> None:
    store = Store(tmp_path / "collector.db")
    with store.transaction():
        store.set("a", 1)
    with pytest.raises(RuntimeError), store.transaction():
        store.set("b", 1)
        raise RuntimeError
    abandoned = store.transaction()
    abandoned.__enter__()
    store.set("c", 1)
    abandoned.gen.close()  # left without __exit__, e.g. dropped mid-block
    assert (store.get("a"), store.get("b"), store.get("c")) == ("1", "", "")
    store.close()


# --- the sampling rule ---------------------------------------------------------------------


def test_rank_is_fixed_and_in_range() -> None:
    assert sampling.rank("dQw4w9WgXcQ") == sampling.rank("dQw4w9WgXcQ")
    ranks = [sampling.rank(f"video{i:06d}") for i in range(2000)]
    assert all(0 <= r < 1 for r in ranks)
    assert 0.45 < sum(ranks) / len(ranks) < 0.55  # spread evenly
    assert len(set(ranks)) == len(ranks)


@pytest.mark.parametrize(
    ("iso", "seconds"),
    [("PT1H2M3S", 3723), ("PT45S", 45), ("PT10M", 600), ("P1DT1S", 86401), ("P0D", 0),
     ("", None), (None, None), ("1:00", None)],
)  # fmt: skip
def test_duration(iso: str | None, seconds: int | None) -> None:
    assert sampling.duration_s(iso) == seconds


def details(**changes: Any) -> Details:
    base: dict[str, Any] = {
        "made_for_kids": True,
        "duration_s": 600,
        "live": False,
        "region_blocked": False,
        "title": "A song",
        "description": "",
        "tags": "",
        "channel_title": "Channel",
    }
    return Details(**{**base, **changes})


@pytest.mark.parametrize(
    ("found", "short", "expected"),
    [
        (details(), None, "eligible"),
        (None, None, "gone"),
        (details(live=True), None, "wait"),
        (details(region_blocked=True), None, "region"),
        (details(made_for_kids=False), None, "not_for_kids"),
        (details(made_for_kids=None), None, "not_for_kids"),
        (details(duration_s=60), None, "duration"),
        (details(duration_s=119), None, "duration"),
        (details(duration_s=3601), None, "duration"),
        (details(duration_s=None), None, "duration"),
        (details(duration_s=150), False, "eligible"),
        (details(duration_s=150), True, "short"),
        (details(duration_s=150), None, "short"),  # undecided counts as a Short, as in v2
        (details(duration_s=181), None, "eligible"),
    ],
)
def test_verdict(found: Details | None, short: bool | None, expected: str) -> None:
    assert sampling.verdict(found, short) == expected


def test_region_blocked() -> None:
    assert sampling.region_blocked({"regionRestriction": {"blocked": ["US", "CA"]}})
    assert sampling.region_blocked({"regionRestriction": {"allowed": ["DE"]}})
    assert not sampling.region_blocked({"regionRestriction": {"allowed": ["US"]}})
    assert not sampling.region_blocked({})


# --- a fake YouTube ------------------------------------------------------------------------


class FakeYouTube:
    """The Data API's answers, from dicts; counts calls by method."""

    def __init__(self) -> None:
        self.uploads: dict[str, list[tuple[str, str]]] = {}  # channel -> newest first
        self.videos: dict[str, dict[str, Any]] = {}  # video ID -> item
        self.search: dict[str, list[str]] = {}
        self.channels: dict[str, tuple[str, int, int]] = {}  # ID -> title, subscribers, videos
        self.calls: list[str] = []
        self.quota_exceeded = False

    def video(self, video_id: str, **changes: Any) -> None:
        item: dict[str, Any] = {
            "id": video_id,
            "snippet": {"title": f"Song {video_id}", "description": "", "tags": ["song"],
                        "channelTitle": "Channel", "liveBroadcastContent": "none"},
            "contentDetails": {"duration": "PT10M"},
            "status": {"madeForKids": True},
        }  # fmt: skip
        for key, value in changes.items():
            part, field = key.split("__")
            item[part][field] = value
        self.videos[video_id] = item

    def get(self, url: str) -> dict[str, Any]:
        method, _, query = url.removeprefix("https://www.googleapis.com/youtube/v3/").partition("?")
        params = dict(urllib.parse.parse_qsl(query))
        self.calls.append(method)
        if self.quota_exceeded:
            raise ApiError("HTTP 403: quotaExceeded", quota_exceeded=True)
        if method == "playlistItems":
            channel = "UC" + params["playlistId"][2:]
            if channel not in self.uploads:
                raise ApiError("HTTP 404: playlistNotFound")
            rows = self.uploads[channel]
            start = int(params.get("pageToken", "0"))
            page = rows[start : start + 50]
            body: dict[str, Any] = {
                "items": [
                    {"contentDetails": {"videoId": v, "videoPublishedAt": p}} for v, p in page
                ]
            }
            if start + 50 < len(rows):
                body["nextPageToken"] = str(start + 50)
            return body
        if method == "videos":
            return {"items": [self.videos[v] for v in params["id"].split(",") if v in self.videos]}
        if method == "search":
            return {"items": [{"id": {"channelId": c}} for c in self.search.get(params["q"], [])]}
        if method == "channels":
            items = []
            for c in params["id"].split(","):
                if c in self.channels:
                    title, subs, videos = self.channels[c]
                    items.append({"id": c, "snippet": {"title": title},
                                  "statistics": {"subscriberCount": str(subs),
                                                 "videoCount": str(videos)}})  # fmt: skip
            return {"items": items}
        raise AssertionError(method)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


class EvenSpacing(random.Random):
    """Spaces downloads by the average gap, not a random one, so a test's ticks always line up
    with the pace (a random gap longer than a tick made tests fail now and then)."""

    def expovariate(self, lambd: float = 1.0) -> float:
        return 1 / lambd


def make_store(path: Path) -> Store:
    store = Store(path / "collector.db")
    store.upsert_channel(id=CHANNEL, title="Channel", status="in", source="v2", listed_at=NOW)
    store.set("seeded", "yes")
    return store


def make_collector(
    tmp_path: Path,
    youtube: FakeYouTube,
    pipeline: FakePipeline,
    clock: Clock,
    budget: int = 7000,
    blocked: Callable[[str], bool] = lambda video_id: False,
    shorts: dict[str, bool | None] | None = None,
) -> Collector:
    store = make_store(tmp_path)

    def spend(units: int) -> None:
        if store.units_used("day") + units > budget:
            raise OutOfUnits("budget")
        store.add_units("day", units)

    settings = Settings(
        data_dir=tmp_path / "data",
        clips_dir=tmp_path / "clips",
        analysis_dir=tmp_path / "analyses",
        per_day=150,
        provenance={"ytdlp_version": "test"},
    )
    collector = Collector(
        settings,
        store,
        DataApi(youtube.get, spend),
        pipeline,
        lambda video_id: (shorts or {}).get(video_id, False),
        load_classifier(),
        blocked,
        clock=clock,
        rng=EvenSpacing(),
    )
    collector.low_on_space = lambda: False  # type: ignore[method-assign]
    return collector


def uploads(n: int, published: str = "2024-05-01T00:00:00Z") -> list[tuple[str, str]]:
    return [(f"vid{i:08d}", published) for i in range(n)]


@pytest.fixture
def youtube() -> FakeYouTube:
    yt = FakeYouTube()
    yt.uploads[CHANNEL] = uploads(30)
    for video_id, _ in yt.uploads[CHANNEL]:
        yt.video(video_id)
    return yt


def by_rank(rows: list[tuple[str, str]]) -> list[str]:
    return sorted((v for v, _ in rows), key=sampling.rank)


def collected_ids(collector: Collector) -> list[str]:
    return [r["video_id"] for r in collector.store.collected_rows()]


def run(collector: Collector, clock: Clock, ticks: int, step: float = DAY_S) -> None:
    for _ in range(ticks):
        collector.tick()
        clock.now += step


# --- collecting ----------------------------------------------------------------------------


def test_takes_eligible_uploads_lowest_number_first(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    order = by_rank(youtube.uploads[CHANNEL])
    youtube.video(order[1], status__madeForKids=False)  # the second-lowest isn't for kids
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 3, step=3600)
    assert collected_ids(collector) == [order[0], order[2], order[3]]
    assert collector.store.upload(order[1]).state == "ineligible"  # type: ignore[union-attr]
    # The cut-off is the highest number checked: everything eligible below it is taken.
    assert collector.store.cutoff() >= sampling.rank(order[3])


def test_v2_picks_taken_out_dont_move_the_cutoff(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    high = next(f"pick{i:07d}" for i in range(1000) if sampling.rank(f"pick{i:07d}") > 0.9)
    collector.store.add_uploads(CHANNEL, [(high, "2020-01-01")])
    collector.store.set_state(high, "removed", "gone")
    assert collector.store.cutoff() == 0.0
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()
    assert youtube.calls.count("videos") == 1  # one batch, not everything below 0.9


def test_raising_the_cutoff_only_adds(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    seen: list[list[str]] = []
    for _ in range(5):
        run(collector, clock, 1, step=3600)
        seen.append(collected_ids(collector))
    for before, after in zip(seen, seen[1:], strict=False):
        assert after[: len(before)] == before


def test_new_uploads_below_the_cutoff_come_first_after_a_day(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 10, step=3600)
    # A new upload with a lower number than any waiting one: listed by the daily check, then
    # checked and taken first once it's a day old.
    waiting = collector.store.db.execute("SELECT MIN(r) FROM uploads WHERE state = 'eligible'")
    lowest = waiting.fetchone()[0]
    fresh = next(f"new{i:08d}" for i in range(100_000) if sampling.rank(f"new{i:08d}") < lowest)
    published = sampling_time(clock.now - 3600)
    youtube.uploads[CHANNEL].insert(0, (fresh, published))
    youtube.video(fresh)
    collector.store.update_channel(CHANNEL, listed_at=0)
    run(collector, clock, 1, step=3600)
    assert collector.store.known(fresh)
    assert fresh not in collected_ids(collector)  # not a day old yet
    clock.now += DAY_S
    run(collector, clock, 1, step=3600)
    assert collected_ids(collector)[-1] == fresh


def sampling_time(t: float) -> str:
    from hyperstim_api.collector.collector import utc

    return utc(t)


def test_uploads_before_2015_and_v2_picks_are_never_taken(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    old = uploads(5, published="2014-12-31T00:00:00Z")
    old = [(f"old{v[3:]}", p) for v, p in old]
    collector.store.add_uploads(CHANNEL, old + youtube.uploads[CHANNEL])
    pick = by_rank(youtube.uploads[CHANNEL])[0]
    collector.store.set_state(pick, "v2")
    run(collector, clock, 40, step=3600)
    taken = collected_ids(collector)
    assert pick not in taken
    assert not [v for v in taken if v.startswith("old")]
    assert len(taken) == 29


def test_premieres_wait_a_day(tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    youtube.video(first, snippet__liveBroadcastContent="upcoming")
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 1, step=60)
    assert collector.store.upload(first).state == "new"  # type: ignore[union-attr]
    youtube.video(first)
    clock.now += DAY_S
    run(collector, clock, 30, step=3600)
    assert first in collected_ids(collector)


def test_shorts_are_left_out(tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline) -> None:
    clock = Clock()
    first, second = by_rank(youtube.uploads[CHANNEL])[:2]
    youtube.video(first, contentDetails__duration="PT2M30S")
    youtube.video(second, contentDetails__duration="PT2M30S")
    collector = make_collector(tmp_path, youtube, pipeline, clock, shorts={first: True})
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 1, step=3600)
    reason = collector.store.db.execute("SELECT reason FROM uploads WHERE id = ?", (first,))
    assert reason.fetchone()[0] == "short"
    assert collector.store.upload(second).state == "collected"  # type: ignore[union-attr]


def test_pace_spreads_downloads_over_the_day(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    youtube.uploads[CHANNEL] = uploads(400)
    for video_id, _ in youtube.uploads[CHANNEL]:
        youtube.video(video_id)
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.s.per_day = 24
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 24 * 12, step=300)  # one day, a tick every 5 minutes
    assert 10 <= len(collected_ids(collector)) <= 24  # on average 24, never more


def test_a_failed_download_is_skipped(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    pipeline.fail[first] = ("download", "unavailable")
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 2, step=3600)
    assert collector.store.upload(first).state == "failed"  # type: ignore[union-attr]
    assert len(collected_ids(collector)) == 1


def test_a_block_pauses_downloads_and_backs_off(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    pipeline.fail[first] = ("download", "unavailable")
    collector = make_collector(tmp_path, youtube, pipeline, clock, blocked=lambda v: True)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()
    assert collector.store.upload(first).state == "eligible"  # type: ignore[union-attr]
    assert float(collector.store.get("blocked_until")) == NOW + 6 * 3600
    clock.now += 3600
    collector.tick()
    assert collector.store.attempts_since(0) == 1  # still waiting
    clock.now = NOW + 6 * 3600 + 1
    collector.tick()  # blocked again right away: twice the wait, half the pace
    assert float(collector.store.get("blocked_until")) == clock.now + 12 * 3600
    assert collector.per_day(clock.now) == 75
    del pipeline.fail[first]
    clock.now += 12 * 3600 + 1
    collector.tick()
    assert collected_ids(collector) == [first]
    assert collector.store.get("block_wait") == "0"
    assert collector.per_day(clock.now + 8 * DAY_S) == 150  # the pace comes back after a week


def test_a_live_check_goes_first_and_its_result_is_reused(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    analyses = tmp_path / "analyses"
    analyses.mkdir()
    (analyses / "other000000.json").write_text(json.dumps({"status": "download"}))
    collector.tick()
    assert collected_ids(collector) == []
    features = dict.fromkeys(FEATURES, 1.25)
    (analyses / "other000000.json").write_text(json.dumps({"status": "done"}))
    (analyses / f"{first}.json").write_text(json.dumps({"status": "done", "features": features}))
    collector.tick()
    assert collected_ids(collector) == [first]
    assert pipeline.workdirs == []  # nothing downloaded
    row = collector.store.collected_rows()[0]
    assert json.loads(row["features"]) == features
    assert json.loads(row["provenance"])["measured_by"] == "live analysis"


def test_a_block_seen_by_a_live_check_pauses_downloads(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    (tmp_path / "analyses").mkdir()
    (tmp_path / "analyses" / "youtube-blocked").write_text(f"{NOW - 60}\n")
    collector.tick()
    assert collected_ids(collector) == []
    clock.now += 6 * 3600
    collector.tick()
    assert len(collected_ids(collector)) == 1


def test_clips_and_feature_caches_are_kept(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]

    def write(step: str, video_id: str, workdir: Path | None) -> None:
        assert workdir is not None
        if step == "download":
            (workdir / "clips").mkdir()
            (workdir / "clips" / f"{video_id}.mp4").write_text("clip")
        if step == "measure":
            (workdir / "cache").mkdir()
            (workdir / "cache" / f"{video_id}.npz").write_text("cache")

    pipeline.during = write
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()
    assert (tmp_path / "clips" / "clips" / f"{first}.mp4").read_text() == "clip"
    assert (tmp_path / "clips" / "cache" / f"{first}.npz").read_text() == "cache"
    assert not (tmp_path / "clips" / "work" / first).exists()


def test_backs_up_its_database_once_a_day_and_keeps_a_week(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    backups = tmp_path / "clips" / "backups"
    collector.tick()
    collector.tick()  # the same day: no second copy
    assert [p.name for p in backups.iterdir()] == ["collector-2026-10-26.db"]
    copy = Store(backups / "collector-2026-10-26.db")
    assert copy.get("seeded") == "yes"
    assert copy.db.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 30
    copy.close()
    run(collector, clock, ticks=9)
    names = sorted(p.name for p in backups.iterdir())
    assert len(names) == 7
    assert names[0] == "collector-2026-10-28.db"  # 9 days, the newest 7 kept
    assert names[-1] == "collector-2026-11-03.db"


def test_categories_come_from_v2s_keywords(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first, second = by_rank(youtube.uploads[CHANNEL])[:2]
    youtube.video(first, snippet__title="Minecraft lets play", snippet__tags=[])
    youtube.video(second, snippet__title="Hello", snippet__tags=[])
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 2, step=3600)
    rows = {r["video_id"]: r["category"] for r in collector.store.collected_rows()}
    assert rows == {first: "gaming", second: None}


# --- the export the API reads --------------------------------------------------------------


def test_export_is_read_by_the_api(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 3, step=3600)
    folder = tmp_path / "data" / "collected"
    with (folder / "2026.tsv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert [r["video_id"] for r in rows] == collected_ids(collector)
    assert rows[0]["ytdlp_version"] == "test" and rows[0]["rule_version"] == "v1"
    reference = write_dataset(tmp_path / "videos.tsv", [video_row("ref00000001", CHANNEL, 5.0)])
    dataset = load_dataset(reference, folder)
    assert len(dataset.videos) == 4
    assert all(dataset.videos_by_id[r["video_id"]].added_at == r["added_at"] for r in rows)
    # The changelog the release notes read: one line a day, with the totals.
    with (folder / "CHANGELOG.tsv").open(newline="", encoding="utf-8") as fh:
        log = list(csv.DictReader(fh, delimiter="\t"))
    assert log == [
        {"date": "2026-10-26", "added": "3", "removed": "0", "channels_added": "1",
         "videos": "3", "channels": "1"}
    ]  # fmt: skip
    assert "CHANGELOG.tsv" not in [p.name for p in collected_files(folder)]


# --- channels ------------------------------------------------------------------------------


def test_discovery_adds_channels_that_meet_v2s_rules(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    good, small, topic = "UC" + "g" * 22, "UC" + "s" * 22, "UC" + "t" * 22
    youtube.search[QUERIES[0]] = [good, small, topic, CHANNEL]
    youtube.channels = {
        good: ("Good Songs", 50_000, 300),
        small: ("Small", 5_000, 300),
        topic: ("Artist - Topic", 1_000_000, 9_000),
    }
    youtube.uploads[good] = uploads(120)
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.discover(clock.now)
    store = collector.store
    assert store.channel_status(good) == "in"
    assert store.channel_status(small) == "near_miss"
    assert store.channel_status(topic) == "rejected"
    assert (
        store.db.execute("SELECT COUNT(*) FROM uploads WHERE channel_id = ?", (good,)).fetchone()[0]
        == 120
    )
    assert youtube.calls.count("search") == 6  # today's share of the 36 queries
    collector.discover(clock.now)  # nothing more today
    assert youtube.calls.count("search") == 6
    for day in range(1, 6):  # 6 a day: all 36 in 6 days, so each query at least weekly
        collector.discover(clock.now + day * DAY_S)
    assert youtube.calls.count("search") == 36
    assert store.get("channels_checked_at") == "2026-10-31"


def test_a_near_miss_that_grew_is_added(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    grown = "UC" + "n" * 22
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.upsert_channel(
        id=grown, status="near_miss", source="v2", queries="kids songs", checked_at="2026-08-26"
    )
    youtube.channels[grown] = ("Grown", 20_000, 150)
    youtube.uploads[grown] = uploads(3)
    collector.check_near_misses(clock.now)
    row = collector.store.db.execute("SELECT * FROM channels WHERE id = ?", (grown,)).fetchone()
    assert (row["status"], row["source"], row["queries"]) == ("in", "v2", "kids songs")
    assert row["joined_at"].startswith("2026-10-2")


def test_offline_videos_are_taken_out(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(
        CHANNEL, [("pick0000001", "2020-01-01"), ("pick0000002", "2020-01-01")]
    )
    collector.store.set_state("pick0000001", "v2", online_at=0)
    collector.store.set_state("pick0000002", "v2", online_at=0)
    youtube.video("pick0000002", contentDetails__regionRestriction={"blocked": ["US"]})
    collector.check_online(clock.now)
    removed = {r["video_id"]: r["reason"] for r in collector.store.removed_rows()}
    assert removed == {"pick0000001": "gone", "pick0000002": "region"}
    text = (tmp_path / "data" / "collected" / "removed.tsv").read_text()
    assert "pick0000001" in text
    changelog = (tmp_path / "data" / "collected" / "CHANGELOG.tsv").read_text().splitlines()
    assert changelog[-1].split("\t") == ["2026-10-26", "0", "2", "0", "0", "0"]


# --- the Data API budget -------------------------------------------------------------------


def test_stops_at_its_budget_until_the_next_day(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    youtube.search = {q: [] for q in QUERIES}
    collector = make_collector(tmp_path, youtube, pipeline, clock, budget=250)
    collector.tick()
    assert youtube.calls.count("search") == 2  # 100 units each; the third would pass 250
    assert collector.store.get("out_of_units")
    calls = len(youtube.calls)
    collector.tick()
    assert len(youtube.calls) == calls  # no more calls today


def test_youtube_saying_quota_exceeded_stops_for_the_day(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    youtube.quota_exceeded = True
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.tick()
    assert collector.store.get("out_of_units")


def test_a_gone_channel_has_no_uploads(youtube: FakeYouTube) -> None:
    api = DataApi(youtube.get, lambda units: None)
    assert api.uploads_page("UC" + "x" * 22) == ([], None)


def test_other_api_errors_surface() -> None:
    def failing(url: str) -> dict[str, Any]:
        raise ApiError("HTTP 500")

    with pytest.raises(ApiError):
        DataApi(failing, lambda units: None).videos(["a"])


# --- seeding from v2 -----------------------------------------------------------------------


def test_seed_from_v2(tmp_path: Path) -> None:
    repo = tmp_path / "research"
    probe = repo / "runs" / "channel-yield-probe"
    probe.mkdir(parents=True)
    other, topic = "UC" + "o" * 22, "UC" + "t" * 22
    columns = ["channel_id", "title", "subscriber_count", "video_count", "auto_generated",
               "discovery_queries"]  # fmt: skip
    with (probe / "channels-p1.tsv").open("w", encoding="utf-8") as fh:
        fh.write("\t".join(columns) + "\n")
        fh.write(f"{CHANNEL}\tSampled\t2000000\t500\t0\tkids songs\n")
        fh.write(f"{other}\tSmall\t9000\t500\t0\tkids songs\n")
        fh.write(f"{topic}\tX - Topic\t90000\t500\t1\tkids songs\n")
    catalogue = repo / "runs" / "contemporary-v2" / "catalogue-cache"
    catalogue.mkdir(parents=True)
    (catalogue / f"{CHANNEL}.tsv").write_text(
        "video_id\tpublished_at\npick0000001\t2020-01-01T00:00:00Z\nmore0000001\t2021-01-01T00:00:00Z\n"
    )
    dataset = write_dataset(tmp_path / "videos.tsv", [video_row("pick0000001", CHANNEL, 1.0)])
    store = Store(tmp_path / "db" / "collector.db")
    assert seed(store, repo, dataset) == "Seeded 1 channels (1 near misses), 2 uploads, 1 v2 picks"
    assert store.channel_status(topic) == "rejected"
    assert store.upload("pick0000001").state == "v2"  # type: ignore[union-attr]
    assert store.upload("more0000001").state == "new"  # type: ignore[union-attr]
    with pytest.raises(RuntimeError, match="already seeded"):
        seed(store, repo, dataset)
