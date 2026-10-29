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
        # (method, params) -> True: that call fails with HTTP 500
        self.fails: Callable[[str, dict[str, str]], bool] = lambda method, params: False

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
        if self.fails(method, params):
            raise ApiError("HTTP 500: backendError")
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
    at_floor: bool = True,
) -> Collector:
    store = make_store(tmp_path)
    if at_floor:  # tests of the cut-off: the channel already has its 5, so only `t` picks
        fill_floor(store, CHANNEL)

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


def fill_floor(store: Store, channel_id: str, n: int = sampling.FLOOR) -> list[str]:
    """Gives the channel `n` v2 picks (not due for the offline check)."""
    picks = [f"v2{channel_id[-6:]}{i:03d}" for i in range(n)]
    store.add_uploads(channel_id, [(v, "2016-01-01T00:00:00Z") for v in picks])
    for video_id in picks:
        store.set_state(video_id, "v2", title="Old", channel_title="Channel", online_at=1e12)
    return picks


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


def failing(pipeline: FakePipeline, video_id: str) -> None:
    """Every download of the video fails, leaving a log like the download script's."""
    pipeline.fail[video_id] = ("download", "unavailable")

    def write_log(step: str, vid: str, workdir: Path | None) -> None:
        if step == "download" and workdir is not None and vid == video_id:
            (workdir / "clips").mkdir(exist_ok=True)
            (workdir / "clips" / f"{vid}.mweb.log").write_text("ERROR: empty stream")

    pipeline.during = write_log


def test_a_failed_download_is_tried_again_after_1_3_and_7_days_then_given_up(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    failing(pipeline, first)
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])

    def tries() -> int:
        return collector.store.failures(first)

    def upload_state() -> str:
        return collector.store.upload(first).state  # type: ignore[union-attr]

    collector.tick()
    assert (tries(), upload_state()) == (1, "eligible")
    failed_at = NOW
    for wait, count in ((DAY_S, 2), (3 * DAY_S, 3), (7 * DAY_S, 4)):
        clock.now = failed_at + wait - 1200  # not yet: other videos go on meanwhile
        collector.store.set("next_download_at", 0)
        collector.tick()
        assert tries() == count - 1
        clock.now = failed_at + wait
        collector.store.set("next_download_at", 0)
        collector.tick()
        assert tries() == count
        failed_at = clock.now
    assert upload_state() == "failed"  # the 4th failure gives up
    assert len(collected_ids(collector)) == 3
    clock.now += 30 * DAY_S
    run(collector, clock, 5, step=3600)
    assert tries() == 4


def test_retries_come_one_per_slot_and_count_towards_the_pace(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()  # checks the uploads; downloads the lowest
    waiting = by_rank(youtube.uploads[CHANNEL])[1:6]
    for video_id in waiting:  # five failed a day ago, all due now
        collector.store.log_attempt(video_id, NOW - DAY_S, "failed")
        collector.store.set_state(video_id, "eligible", retry_at=NOW)
    gap = DAY_S / 150
    for i in range(5):
        clock.now += gap
        collector.tick()
        collector.tick()  # a second tick in the same slot downloads nothing
        assert collected_ids(collector)[1:] == waiting[: i + 1]
    collector.s.per_day = 6  # today's 6 slots are used: the 1st download and the 5 retries
    clock.now += gap
    collector.tick()
    assert len(collected_ids(collector)) == 6


def test_three_failures_in_a_row_pause_downloads_for_an_hour(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    order = by_rank(youtube.uploads[CHANNEL])
    for video_id in order[:4]:
        pipeline.fail[video_id] = ("download", "unavailable")
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    gap = DAY_S / 150
    for _ in range(3):
        collector.tick()
        clock.now += gap
    assert float(collector.store.get("paused_until")) == NOW + 2 * gap + 3600
    collector.tick()
    assert collector.store.attempts_since(0) == 3  # paused
    clock.now = NOW + 2 * gap + 3600
    collector.tick()
    assert collector.store.failures(order[3]) == 1  # the 4th, after the pause
    clock.now += gap
    collector.tick()
    assert collected_ids(collector) == [order[4]]  # the pace is unchanged
    assert collector.per_day(clock.now) == 150
    assert collector.store.get("failures_in_a_row") == "0"


def test_the_downloaders_output_is_kept_for_30_days(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    failing(pipeline, first)
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    logs = tmp_path / "data" / "download-logs"
    collector.tick()
    kept = logs / "2026-10-26" / f"{first}.log"
    assert "ERROR: empty stream" in kept.read_text()
    clock.now += 30 * DAY_S
    collector.tick()
    assert kept.exists()  # 30 days: still kept
    clock.now += DAY_S
    collector.tick()
    assert not kept.parent.exists()
    assert (logs / "2026-11-25" / f"{first}.log").exists()  # the retry's, kept


def test_downloads_failed_before_retries_are_tried_again(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add_uploads(CHANNEL, [("once0000001", "2024-01-01"), ("four0000001", "2024-01-01")])
    for video_id, failures in (("once0000001", 1), ("four0000001", 4)):
        store.set_state(video_id, "failed")
        for i in range(failures):
            store.log_attempt(video_id, NOW + i, "failed")
    store.log_attempt("once0000001", NOW, "blocked")
    assert store.requeue_failed(4) == 1
    assert store.upload("once0000001").state == "eligible"  # type: ignore[union-attr]
    assert store.upload("four0000001").state == "failed"  # type: ignore[union-attr]
    assert store.requeue_failed(4) == 0


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
    collector = make_collector(tmp_path, youtube, pipeline, clock, at_floor=False)
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


# --- the floor: at least 5 videos per channel -----------------------------------------------

SMALL = "UC" + "b" * 22


def small_channel(
    collector: Collector, youtube: FakeYouTube, n: int, picks: int = 1, prefix: str = "sml"
) -> list[str]:
    """A second channel with `picks` v2 picks and `n` eligible uploads; returns them by number."""
    store = collector.store
    store.upsert_channel(id=SMALL, title="Small", status="in", source="v2", listed_at=NOW)
    fill_floor(store, SMALL, picks)
    rows = [(f"{prefix}{i:08d}", "2024-05-01T00:00:00Z") for i in range(n)]
    youtube.uploads[SMALL] = rows
    for video_id, _ in rows:
        youtube.video(video_id)
    store.add_uploads(SMALL, rows)
    return by_rank(rows)


def picks_of(collector: Collector, channel_id: str) -> dict[str, str]:
    rows = collector.store.db.execute(
        "SELECT id, pick FROM uploads WHERE channel_id = ? AND state = 'collected'", (channel_id,)
    )
    return {r["id"]: r["pick"] for r in rows}


def test_a_channel_below_the_floor_is_topped_up_by_its_lowest_numbers_first(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    small = small_channel(collector, youtube, 30)
    collector.tick()
    # Only the floor's checks so far: they don't raise the cut-off, and only the 4 it lacks
    # are kept; the others it checked go back to unchecked.
    assert collector.store.cutoff() == 0.0
    waiting = collector.store.db.execute(
        "SELECT id FROM uploads WHERE state = 'eligible' ORDER BY r"
    ).fetchall()
    assert [r["id"] for r in waiting] == small[1:4]
    run(collector, clock, 4, step=3600)
    assert collected_ids(collector) == small[:4]  # before any upload of the other channel
    assert set(picks_of(collector, SMALL).values()) == {"floor"}
    # Then the cut-off rises over both channels; once it passes the floor's picks nothing
    # changes: in the end every eligible upload is in, each once.
    run(collector, clock, 70, step=3600)
    taken = collected_ids(collector)
    assert taken[:4] == small[:4]
    assert sorted(taken) == sorted(small + [v for v, _ in youtube.uploads[CHANNEL]])
    assert collector.store.cutoff() > max(sampling.rank(v) for v in small[:4])
    assert {v for v, p in picks_of(collector, SMALL).items() if p == "floor"} == set(small[:4])
    rows = list(csv.DictReader((tmp_path / "data" / "collected" / "2026.tsv").open(),
                               delimiter="\t"))  # fmt: skip
    assert {r["video_id"]: r["pick"] for r in rows}[small[0]] == "floor"


def test_a_channel_with_too_few_eligible_uploads_takes_its_next_new_one(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    youtube.uploads[CHANNEL] = []  # nothing for the cut-off to take
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    small = small_channel(collector, youtube, 3, picks=0)
    run(collector, clock, 5, step=3600)
    assert collected_ids(collector) == small
    # A new upload with a number far above the cut-off: taken, as the channel lacks 2.
    fresh = next(f"new{i:08d}" for i in range(100_000) if sampling.rank(f"new{i:08d}") > 0.9)
    youtube.uploads[SMALL].insert(0, (fresh, sampling_time(clock.now - 3600)))
    youtube.video(fresh)
    collector.store.update_channel(SMALL, listed_at=0)
    clock.now += DAY_S
    run(collector, clock, 3, step=3600)
    assert collected_ids(collector)[-1] == fresh
    assert collector.store.cutoff() == 0.0


def test_a_channel_that_loses_a_video_is_topped_up_again(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    small = small_channel(collector, youtube, 10, picks=sampling.FLOOR)
    assert collector.store.below_floor() == []
    gone = f"v2{SMALL[-6:]}000"
    collector.store.set_state(gone, "removed", "gone")
    collector.store.add_removed(gone, "2026-10-26T00:00:00Z", "gone")
    collector.check_candidates(clock.now)
    collector.tick()
    assert picks_of(collector, SMALL) == {small[0]: "floor"}


def test_with_no_floor_video_ready_the_slot_goes_to_raising_the_cutoff(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    (only,) = small_channel(collector, youtube, 1)
    failing(pipeline, only)
    collector.tick()  # the floor's only video: its download fails, it waits a day
    assert collector.store.failures(only) == 1
    run(collector, clock, 1, step=3600)
    clock.now += 3600
    collector.tick()
    assert collected_ids(collector) == by_rank(youtube.uploads[CHANNEL])[:1]
    assert collector.store.cutoff() > 0


def test_floor_downloads_count_towards_the_pace(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.s.per_day = 2
    small = small_channel(collector, youtube, 30)
    run(collector, clock, 23, step=3600)
    assert collected_ids(collector) == small[:2]


def test_status_shows_the_channels_below_the_floor(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    from hyperstim_api.collector.__main__ import floor_line

    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    small_channel(collector, youtube, 0)
    assert floor_line(collector.store) == (
        "Below the floor of 5: 1 channels lacking 4 videos, 1 of them with every upload checked"
    )


# --- the export the API reads --------------------------------------------------------------


def test_export_is_read_by_the_api(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock, at_floor=False)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    run(collector, clock, 3, step=3600)
    folder = tmp_path / "data" / "collected"
    with (folder / "2026.tsv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert [r["video_id"] for r in rows] == collected_ids(collector)
    assert rows[0]["ytdlp_version"] == "test" and rows[0]["rule_version"] == "v1"
    assert {r["pick"] for r in rows} == {"floor"}  # the channel had no videos
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
    collector = make_collector(tmp_path, youtube, pipeline, clock, at_floor=False)
    collector.store.add_uploads(
        CHANNEL, [("pick0000001", "2020-01-01"), ("pick0000002", "2020-01-01")]
    )
    collector.store.set_state("pick0000001", "v2", online_at=0)
    collector.store.set_state("pick0000002", "v2", online_at=0)
    youtube.video("pick0000002", contentDetails__regionRestriction={"blocked": ["US"]})
    collector.check_online(clock.now)
    assert collector.store.removed_rows() == []  # not on one answer: checked again in a day
    clock.now += DAY_S - 60
    collector.check_online(clock.now)
    assert collector.store.removed_rows() == []
    clock.now += 60
    collector.check_online(clock.now)
    removed = {r["video_id"]: r["reason"] for r in collector.store.removed_rows()}
    assert removed == {"pick0000001": "gone", "pick0000002": "region"}
    text = (tmp_path / "data" / "collected" / "removed.tsv").read_text()
    assert "pick0000001" in text
    changelog = (tmp_path / "data" / "collected" / "CHANGELOG.tsv").read_text().splitlines()
    assert changelog[-1].split("\t") == ["2026-10-27", "0", "2", "0", "0", "0"]


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


# --- when something fails (decision 12) ----------------------------------------------------

OTHER = "UC" + "b" * 22


def test_a_failing_channel_list_waits_while_the_others_and_downloads_go_on(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.store.upsert_channel(id=OTHER, title="Other", status="in", source="v2", listed_at=0)
    collector.store.update_channel(CHANNEL, listed_at=0)
    youtube.uploads[OTHER] = [("othr0000001", "2024-05-01T00:00:00Z")]
    youtube.fails = lambda method, params: params.get("playlistId") == "UU" + CHANNEL[2:]
    collector.tick()
    assert collector.store.known("othr0000001")  # the other channel was read
    assert len(collected_ids(collector)) == 1  # and a video downloaded
    calls = youtube.calls.count("playlistItems")
    clock.now += 1800
    collector.tick()
    assert youtube.calls.count("playlistItems") == calls  # it waits an hour, not every tick
    youtube.fails = lambda method, params: False
    clock.now += 1800
    collector.tick()
    row = collector.store.db.execute("SELECT * FROM channels WHERE id = ?", (CHANNEL,)).fetchone()
    assert (row["api_failures"], row["listed_at"]) == (0, clock.now)


def test_a_failing_batch_of_details_waits_and_downloads_go_on(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()  # checks the uploads, downloads one
    below = collector.store.cutoff()
    late = next(f"late{i:07d}" for i in range(100_000) if sampling.rank(f"late{i:07d}") < below)
    collector.store.add_uploads(CHANNEL, [(late, "2024-05-01T00:00:00Z")])
    youtube.video(late)
    youtube.fails = lambda method, params: method == "videos"
    clock.now += 3600
    collector.tick()
    upload = collector.store.upload(late)
    assert upload is not None and (upload.state, upload.api_failures) == ("new", 1)
    assert len(collected_ids(collector)) == 2  # downloads went on
    calls = youtube.calls.count("videos")
    clock.now += 600
    collector.tick()
    assert youtube.calls.count("videos") == calls  # the job waits after the error
    youtube.fails = lambda method, params: False
    clock.now += 3600
    collector.tick()
    assert collector.store.upload(late).state == "eligible"  # type: ignore[union-attr]


def test_a_missing_upload_is_asked_again_after_1_3_and_7_days(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    del youtube.videos[first]  # private for a while
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.check_candidates(clock.now)
    upload = collector.store.upload(first)
    assert upload is not None and (upload.state, upload.unsure) == ("new", 1)
    clock.now += DAY_S
    collector.check_candidates(clock.now)
    assert collector.store.upload(first).unsure == 2  # type: ignore[union-attr]
    youtube.video(first)  # public again
    clock.now += 3 * DAY_S
    collector.check_candidates(clock.now)
    assert collector.store.upload(first).state == "eligible"  # type: ignore[union-attr]


def test_an_undecided_shorts_probe_is_final_only_the_4th_time(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    youtube.video(first, contentDetails__duration="PT2M30S")
    collector = make_collector(tmp_path, youtube, pipeline, clock, shorts={first: None})
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    for wait in (0, DAY_S, 3 * DAY_S, 7 * DAY_S):
        clock.now += wait
        assert collector.store.upload(first).state == "new"  # type: ignore[union-attr]
        collector.check_candidates(clock.now)
    upload = collector.store.upload(first)
    assert upload is not None and (upload.state, upload.unsure) == ("ineligible", 4)
    reason = collector.store.db.execute("SELECT reason FROM uploads WHERE id = ?", (first,))
    assert reason.fetchone()[0] == "short"


def test_a_half_written_removal_is_checked_again(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, [("pick0000001", "2020-01-01")])
    collector.store.set_state("pick0000001", "removed", "gone")  # no removed.tsv row
    collector.repair(clock.now)
    upload = collector.store.upload("pick0000001")
    assert upload is not None and upload.state == "v2"
    assert collector.store.in_dataset(clock.now, clock.now, 50)[0].id == "pick0000001"


def test_a_failed_backup_doesnt_stop_the_collector(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "backups").write_text("not a folder")  # as if the volume broke
    collector.tick()
    assert len(collected_ids(collector)) == 1
    assert collector.store.get("backup_failures") == "1"
    (tmp_path / "clips" / "backups").unlink()
    clock.now += 1800
    collector.tick()
    assert not (tmp_path / "clips" / "backups").exists()  # waits an hour
    clock.now += 1800
    collector.tick()
    assert (tmp_path / "clips" / "backups" / "collector-2026-10-26.db").exists()
    assert collector.store.get("backup_failures") == "0"


def test_an_unexpected_error_is_a_failed_try_that_takes_a_slot(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    pipeline.fail[first] = ("measure", None)  # crashes, not an AnalysisError
    probed: list[str] = []

    def blocked(video_id: str) -> bool:
        probed.append(video_id)
        return False

    collector = make_collector(tmp_path, youtube, pipeline, clock, blocked=blocked)
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.tick()
    upload = collector.store.upload(first)
    assert upload is not None and upload.state == "eligible"
    assert collector.store.failures(first) == 1
    assert probed == []  # not YouTube: no block probe
    assert float(collector.store.get("next_download_at")) > clock.now  # the pace holds
    collector.tick()
    assert collector.store.attempts_since(0) == 1


def test_a_new_channels_list_that_fails_on_page_3_goes_on_from_page_3(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    good = "UC" + "g" * 22
    youtube.search[QUERIES[0]] = [good]
    youtube.channels = {good: ("Good Songs", 50_000, 300)}
    youtube.uploads[good] = [(f"good{i:07d}", "2024-05-01T00:00:00Z") for i in range(200)]
    pages: list[str] = []

    def fails(method: str, params: dict[str, str]) -> bool:
        if method != "playlistItems" or params["playlistId"] != "UU" + good[2:]:
            return False
        pages.append(params.get("pageToken", "0"))
        return params.get("pageToken") == "100" and pages.count("100") == 1

    youtube.fails = fails
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.discover(clock.now)
    store = collector.store
    row = store.db.execute("SELECT * FROM channels WHERE id = ?", (good,)).fetchone()
    assert (row["status"], row["full_listing"]) == ("in", "100")
    assert (
        store.db.execute("SELECT COUNT(*) FROM uploads WHERE channel_id = ?", (good,)).fetchone()[0]
        == 100
    )
    clock.now += 3600
    collector.finish_listings(clock.now)
    assert pages == ["0", "50", "100", "100", "150"]  # pages 1 and 2 not read again
    assert (
        store.db.execute("SELECT COUNT(*) FROM uploads WHERE channel_id = ?", (good,)).fetchone()[0]
        == 200
    )
    row = store.db.execute("SELECT * FROM channels WHERE id = ?", (good,)).fetchone()
    assert row["full_listing"] is None


def test_an_older_database_gets_the_new_columns_and_reads_new_channels_again(
    tmp_path: Path,
) -> None:
    import sqlite3

    path = tmp_path / "collector.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE channels (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', "
        "subscriber_count INTEGER, video_count INTEGER, tier TEXT NOT NULL DEFAULT '', "
        "status TEXT NOT NULL, source TEXT NOT NULL, queries TEXT NOT NULL DEFAULT '', "
        "joined_at TEXT, checked_at TEXT, listed_at REAL);"
        "CREATE TABLE uploads (id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, "
        "published_at TEXT NOT NULL, r REAL NOT NULL, state TEXT NOT NULL DEFAULT 'new', "
        "reason TEXT NOT NULL DEFAULT '', retry_at REAL NOT NULL DEFAULT 0, checked_at REAL, "
        "online_at REAL, title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', "
        "tags TEXT NOT NULL DEFAULT '', channel_title TEXT NOT NULL DEFAULT '', "
        "duration_s INTEGER);"
        "INSERT INTO channels (id, status, source, joined_at) VALUES "
        "('UCv2', 'in', 'v2', '2026-08-26'), ('UCnew', 'in', 'discovery', "
        "'2026-10-27T10:00:00Z'), ('UCnear', 'near_miss', 'v2', NULL);"
        "INSERT INTO uploads (id, channel_id, published_at, r) VALUES ('vid', 'UCv2', '2024', 0.5);"
    )
    old.close()
    store = Store(path)
    listing = dict(store.db.execute("SELECT id, full_listing FROM channels").fetchall())
    assert listing == {"UCv2": None, "UCnew": "", "UCnear": None}
    upload = store.upload("vid")
    assert upload is not None and (upload.unsure, upload.api_failures) == (0, 0)
    assert upload.pick == "sample"  # everything picked before the floor
    store.close()
    assert (
        dict(Store(path).db.execute("SELECT id, full_listing FROM channels").fetchall()) == listing
    )


def test_a_video_without_a_channel_name_waits_until_the_repair_fills_it(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    first = by_rank(youtube.uploads[CHANNEL])[0]
    youtube.video(first, snippet__channelTitle="")
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.update_channel(CHANNEL, title="")
    collector.store.add_uploads(CHANNEL, youtube.uploads[CHANNEL])
    collector.store.set("repaired_day", "2026-10-26")
    collector.tick()
    assert collector.store.upload(first).state == "measured"  # type: ignore[union-attr]
    assert collector.store.attempts_since(0) == 1  # measured: it took its slot
    assert first not in collected_ids(collector)
    exported = tmp_path / "data" / "collected" / "2026.tsv"
    assert not exported.exists() or first not in exported.read_text()
    youtube.channels[CHANNEL] = ("Found Name", 50_000, 300)
    clock.now += DAY_S
    collector.tick()  # the next day's repair
    upload = collector.store.upload(first)
    assert upload is not None and (upload.state, upload.channel_title) == (
        "collected",
        "Found Name",
    )
    row = next(r for r in collector.store.collected_rows() if r["video_id"] == first)
    assert row["added_at"] == sampling_time(clock.now)  # added when it went on the site
    assert first in exported.read_text()


def test_uploads_listed_without_a_date_are_looked_up(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    youtube.uploads[CHANNEL] = [("nodate00001", "")]
    youtube.video("nodate00001", snippet__publishedAt="2024-05-01T00:00:00Z")
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.update_channel(CHANNEL, listed_at=0)
    collector.tick()
    upload = collector.store.upload("nodate00001")
    assert upload is not None and upload.published_at == "2024-05-01T00:00:00Z"


def test_v2_channels_without_a_name_get_one_in_the_export(
    tmp_path: Path, youtube: FakeYouTube, pipeline: FakePipeline
) -> None:
    clock = Clock()
    collector = make_collector(tmp_path, youtube, pipeline, clock)
    collector.store.update_channel(CHANNEL, title="")
    collector.store.add_uploads(CHANNEL, [("pick0000001", "2020-01-01")])
    collector.store.set_state("pick0000001", "v2", online_at=clock.now)
    youtube.channels[CHANNEL] = ("Found Name", 50_000, 300)
    collector.repair(clock.now)
    names = (tmp_path / "data" / "collected" / "channel-names.tsv").read_text()
    assert names == f"channel_id\tchannel_title\n{CHANNEL}\tFound Name\n"
    assert youtube.calls.count("channels") == 1
    collector.repair(clock.now + DAY_S)
    assert youtube.calls.count("channels") == 1  # known now: not asked again
