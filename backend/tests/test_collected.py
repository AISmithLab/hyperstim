"""The dataset grown by the collector (plan 013): added videos are scored against the
reference set, removed ones leave the lists, lists can be read as of an earlier version,
and the API reloads when the collector's files change."""

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.dataset import load_dataset
from hyperstim_api.reload import DatasetStore
from hyperstim_api.scoring import FEATURES
from tests.conftest import VIDEOS, Row, video_row

T1 = "2026-10-20T10:00:00Z"
T2 = "2026-10-21T10:00:00Z"
T3 = "2026-10-22T10:00:00Z"


def collected_row(
    video_id: str, channel_id: str, value: float, added_at: str, category: str = "music"
) -> Row:
    row = video_row(video_id, channel_id, value, category=category)
    row["added_at"] = added_at
    return row


def write_collected(directory: Path, rows: list[Row], removed: list[tuple[str, str]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    columns = [*video_row("x", "y", 1.0), "added_at"]
    with (directory / "2026.tsv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with (directory / "removed.tsv").open("w", newline="", encoding="utf-8") as fh:
        fh.write("video_id\tremoved_at\treason\n")
        fh.writelines(f"{vid}\t{at}\tgone\n" for vid, at in removed)
    (directory / "meta.json").write_text(json.dumps({"channelsCheckedAt": "2026-10-19"}))
    return directory


@pytest.fixture
def collected(tmp_path: Path) -> Path:
    return write_collected(
        tmp_path / "collected",
        [
            collected_row("new-high", "chan-a", 12.0, T1),  # above every reference video
            collected_row("new-mid", "chan-d", 5.5, T2, category=""),  # a new channel, no category
            collected_row("vid-a1", "chan-a", 0.0, T1),  # already in the reference set: ignored
        ],
        [("vid-b5", T3)],
    )


def test_added_videos_are_scored_against_the_reference_set(
    dataset_path: Path, collected: Path
) -> None:
    reference = load_dataset(dataset_path)
    grown = load_dataset(dataset_path, collected)
    # Every reference video keeps its score; an added one scores like a live check.
    for video in reference.videos:
        if video.id != "vid-b5":
            assert grown.videos_by_id[video.id].score == video.score
    features = dict.fromkeys(FEATURES, 5.5)
    live = reference.score_video("new-mid", "t", "chan-d", "c", features)
    assert live is not None
    assert grown.videos_by_id["new-mid"].score == live.score
    assert grown.videos_by_id["new-high"].score == 100
    assert grown.reference_count == len(VIDEOS)
    assert grown.pools == reference.pools


def test_counts_categories_and_removals(dataset_path: Path, collected: Path) -> None:
    grown = load_dataset(dataset_path, collected)
    assert len(grown.videos) == len(VIDEOS) + 2 - 1
    assert grown.channel_count == 4
    assert grown.videos_by_id["new-mid"].category is None
    assert grown.videos_by_id["new-mid"].added_at == T2
    assert grown.videos_by_id["vid-a1"].added_at is None  # the reference row wins
    # A removed video leaves the lists and its channel, but its page still works.
    assert all(v.id != "vid-b5" for v in grown.videos)
    assert grown.videos_by_id["vid-b5"].removed_at == T3
    assert grown.channels_by_id["chan-b"].video_count == 4
    assert grown.version == T3
    assert grown.updated_at == "2026-10-22"
    assert grown.added_since(T2) == 1
    assert grown.last_added_at() == T2
    assert grown.channel_count_at(T1) == 3
    assert grown.channel_count_at(T2) == 4


def test_unknown_category_in_the_collected_files_is_an_error(
    dataset_path: Path, tmp_path: Path
) -> None:
    folder = write_collected(tmp_path / "c", [collected_row("x1", "c", 1.0, T1, "dance")], [])
    with pytest.raises(ValueError, match="unknown category"):
        load_dataset(dataset_path, folder)


@pytest.fixture
def grown_client(
    dataset_path: Path,
    collected: Path,
    make_client: Callable[..., TestClient],
) -> TestClient:
    return make_client(dataset_path, collected_dir=collected)


def ids(body: dict[str, Any]) -> list[str]:
    items = body["items"]
    assert isinstance(items, list)
    return [item["id"] for item in items]


def test_lists_say_their_version_and_answer_as_of_an_earlier_one(
    grown_client: TestClient,
) -> None:
    now = grown_client.get("/api/videos", params={"limit": 100}).json()
    assert now["asOf"] == T3
    assert now["total"] == len(VIDEOS) + 1
    assert "new-mid" in ids(now) and "vid-b5" not in ids(now)
    # As of T1: new-mid not added yet, vid-b5 not removed yet.
    then = grown_client.get("/api/videos", params={"limit": 100, "asOf": T1}).json()
    assert then["asOf"] == T1
    assert "new-mid" not in ids(then) and "vid-b5" in ids(then) and "new-high" in ids(then)
    # Before any addition: exactly the reference set, ranked as it was.
    before = grown_client.get("/api/videos", params={"limit": 100, "asOf": "2026-01-01T00:00:00Z"})
    assert sorted(ids(before.json())) == sorted(v[0] for v in VIDEOS)
    # An asOf at or after the latest change is the current list.
    later = grown_client.get("/api/videos", params={"limit": 100, "asOf": "2027-01-01T00:00:00Z"})
    assert later.json() == now


def test_page_two_continues_page_one_across_changes(
    dataset_path: Path, tmp_path: Path, make_client: Callable[..., TestClient]
) -> None:
    folder = write_collected(tmp_path / "c", [], [])
    client = make_client(dataset_path, collected_dir=folder)
    first = client.get("/api/videos", params={"limit": 5}).json()
    assert first["asOf"] == "2026-09-01T00:00:00Z"  # nothing added yet: the reference set's date
    # The collector adds a video at the top and removes one from page 2, then the API reloads.
    write_collected(folder, [collected_row("new-top", "chan-a", 99.0, T2)], [("vid-a5", T3)])
    datasets = client.app.state.datasets  # type: ignore[attr-defined]
    assert datasets.reload_if_changed()
    second = client.get(
        "/api/videos", params={"limit": 5, "offset": 5, "asOf": first["asOf"]}
    ).json()
    assert second["asOf"] == first["asOf"]
    reference_order = [v[0] for v in sorted(VIDEOS, key=lambda v: (-v[2], v[0]))]
    assert ids(first) == reference_order[:5]
    assert ids(second) == reference_order[5:10]
    current = client.get("/api/videos", params={"limit": 5}).json()
    assert ids(current)[0] == "new-top" and current["asOf"] == T3


def test_channel_lists_as_of_an_earlier_version(grown_client: TestClient) -> None:
    def channels(**params: str) -> dict[str, Any]:
        query: dict[str, str | int] = {"minVideos": 1, "limit": 100, **params}
        body: dict[str, Any] = grown_client.get("/api/channels", params=query).json()
        return body

    now = channels()
    assert "chan-d" in ids(now)
    then = channels(asOf=T1)
    assert "chan-d" not in ids(then)
    chan_b = [c for c in then["items"] if c["id"] == "chan-b"]
    assert chan_b[0]["videoCount"] == 5  # vid-b5 not removed yet


def test_as_of_must_be_a_utc_timestamp(grown_client: TestClient) -> None:
    assert grown_client.get("/api/videos", params={"asOf": "yesterday"}).status_code == 422


def test_meta_reports_growth(grown_client: TestClient) -> None:
    meta = grown_client.get("/api/meta").json()
    assert meta["videoCount"] == len(VIDEOS) + 1
    assert meta["channelCount"] == 4
    assert meta["referenceCount"] == len(VIDEOS)
    assert meta["lastAddedAt"] == T2
    assert meta["channelsCheckedAt"] == "2026-10-19"
    assert meta["updatedAt"] == "2026-10-22"


def test_reload_only_when_the_files_change(dataset_path: Path, collected: Path) -> None:
    store = DatasetStore(dataset_path, collected, every_s=60)
    first = store.current
    assert not store.reload_if_changed()
    assert store.current is first
    rows = [collected_row("new-later", "chan-c", 3.0, "2026-10-23T00:00:00Z")]
    write_collected(collected, rows, [])
    assert store.reload_if_changed()
    assert "new-later" in store.current.videos_by_id
    assert "vid-b5" in [v.id for v in store.current.videos]  # no longer removed in the files


def test_a_bad_file_keeps_the_last_good_dataset(dataset_path: Path, collected: Path) -> None:
    store = DatasetStore(dataset_path, collected, every_s=60)
    (collected / "2026.tsv").write_text("video_id\nabc\n", encoding="utf-8")  # missing columns
    assert not store.reload_if_changed()
    assert "new-mid" in store.current.videos_by_id


def test_without_a_collected_folder_the_dataset_is_the_reference_set(
    dataset_path: Path, tmp_path: Path
) -> None:
    store = DatasetStore(dataset_path, tmp_path / "missing", every_s=60)
    assert len(store.current.videos) == len(VIDEOS)
    assert not store.reload_if_changed()
    assert store.channels_checked_at is None


def test_lists_show_only_what_was_added_in_a_window(grown_client: TestClient) -> None:
    def get(path: str, **params: str) -> dict[str, Any]:
        body: dict[str, Any] = grown_client.get(path, params={"limit": 100, **params}).json()
        return body

    everything = {item["id"]: item["rank"] for item in get("/api/videos")["items"]}
    added = get("/api/videos", addedFrom="2026-10-21T00:00:00Z")
    assert ids(added) == ["new-mid"] and added["total"] == 1
    assert added["items"][0]["rank"] == everything["new-mid"]  # the rank among all videos
    both = get("/api/videos", addedFrom=T1, addedBefore="2026-10-21T10:00:01Z")
    assert sorted(ids(both)) == ["new-high", "new-mid"]
    # The reference set counts as added on its date.
    reference = get("/api/videos", addedBefore="2026-09-02T00:00:00Z")
    assert reference["total"] == len(VIDEOS) - 1  # vid-b5 was removed
    # Channels: when their first video was added, so only channels new to the dataset.
    channels = get("/api/channels", minVideos="1", addedFrom="2026-10-01T00:00:00Z")
    assert ids(channels) == ["chan-d"]


def test_added_must_be_a_utc_timestamp(grown_client: TestClient) -> None:
    assert grown_client.get("/api/videos", params={"addedFrom": "2026-10-20"}).status_code == 422
