from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.config import load_settings
from tests.conftest import ORIGIN, VIDEOS, video_row, write_dataset

N = len(VIDEOS)


def pct(rank_from_bottom: int) -> float:
    """Expected score of the video with the given 0-based rank from the lowest value."""
    return round(100 * rank_from_bottom / (N - 1), 1)


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta(client: TestClient) -> None:
    assert client.get("/api/meta").json() == {
        "videoCount": N,
        "channelCount": 3,
        "updatedAt": "2026-09-01",
    }


def test_videos_most_stimulating_first(client: TestClient) -> None:
    body = client.get("/api/videos", params={"sort": "score_desc", "limit": 3}).json()
    assert body["total"] == N
    assert body["items"] == [
        {"id": "vid-c1", "title": "Title of vid-c1", "channel": "Channel chan-c", "score": 100.0},
        {"id": "vid-a1", "title": "Title of vid-a1", "channel": "Channel chan-a", "score": pct(10)},
        {"id": "vid-a2", "title": "Title of vid-a2", "channel": "Channel chan-a", "score": pct(9)},
    ]


def test_videos_least_stimulating_first(client: TestClient) -> None:
    body = client.get("/api/videos", params={"sort": "score_asc", "limit": 3}).json()
    assert [v["id"] for v in body["items"]] == ["vid-c2", "vid-b5", "vid-b4"]
    assert [v["score"] for v in body["items"]] == [0.0, pct(1), pct(2)]


def test_videos_default_sort_and_limit(client: TestClient) -> None:
    body = client.get("/api/videos").json()
    assert len(body["items"]) == N  # fewer than the default limit of 20
    assert body["items"][0]["id"] == "vid-c1"


def test_video_ties_keep_a_stable_order(
    tmp_path: Path, make_client: Callable[[Path], TestClient]
) -> None:
    rows = [video_row(v, "chan", 1.0) for v in ("vid-y", "vid-x", "vid-z")]
    client = make_client(write_dataset(tmp_path / "ties.tsv", rows))
    desc = [v["id"] for v in client.get("/api/videos").json()["items"]]
    asc = [v["id"] for v in client.get("/api/videos", params={"sort": "score_asc"}).json()["items"]]
    assert desc == ["vid-x", "vid-y", "vid-z"]
    assert asc == list(reversed(desc))


def test_scores_are_percentiles_of_the_composite(
    tmp_path: Path, make_client: Callable[[Path], TestClient]
) -> None:
    # Only cuts_per_min differs; the 11 equal features put every video at 100 for them,
    # so the composites bunch up (91.7, 95.8, 100) while the scores still span 0-100.
    rows = []
    for video_id, cuts in (("vid-1", 1.0), ("vid-2", 2.0), ("vid-3", 3.0)):
        row = video_row(video_id, "chan", 5.0)
        row["cuts_per_min"] = str(cuts)
        rows.append(row)
    client = make_client(write_dataset(tmp_path / "videos.tsv", rows))
    items = client.get("/api/videos", params={"sort": "score_asc"}).json()["items"]
    assert [v["score"] for v in items] == [0.0, 50.0, 100.0]


def test_channels_ranked_by_mean_score(client: TestClient) -> None:
    body = client.get("/api/channels", params={"sort": "score_desc", "limit": 3}).json()
    assert body["total"] == 2  # chan-c has only 2 videos
    assert body["items"] == [
        {"name": "Channel chan-a", "score": pct(8), "videoCount": 5},
        {"name": "Channel chan-b", "score": pct(3), "videoCount": 5},
    ]


def test_channels_least_stimulating_first(client: TestClient) -> None:
    body = client.get("/api/channels", params={"sort": "score_asc", "limit": 1}).json()
    assert [c["name"] for c in body["items"]] == ["Channel chan-b"]
    assert body["total"] == 2


def test_channels_min_videos(client: TestClient) -> None:
    body = client.get("/api/channels", params={"minVideos": 1}).json()
    assert body["total"] == 3
    assert [c["name"] for c in body["items"]][1] == "Channel chan-c"  # mean of 100 and 0 = 50


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/videos", {"sort": "score"}),
        ("/api/videos", {"limit": 0}),
        ("/api/videos", {"limit": 101}),
        ("/api/videos", {"limit": "many"}),
        ("/api/channels", {"sort": "name"}),
        ("/api/channels", {"minVideos": 0}),
        ("/api/channels", {"minVideos": 1001}),
    ],
)
def test_bad_params_are_rejected(
    client: TestClient, path: str, params: dict[str, str | int]
) -> None:
    assert client.get(path, params=params).status_code == 422


def test_rows_without_id_or_features_are_skipped(
    tmp_path: Path, make_client: Callable[[Path], TestClient]
) -> None:
    rows = [
        video_row("vid-1", "chan", 1.0),
        video_row("vid-2", "chan", 2.0),
        video_row("", "chan", 3.0),
        video_row("vid-empty", "chan", None),
    ]
    client = make_client(write_dataset(tmp_path / "videos.tsv", rows))
    assert client.get("/api/meta").json()["videoCount"] == 2


def test_cors_allows_only_the_configured_origin(client: TestClient) -> None:
    allowed = client.get("/api/meta", headers={"Origin": ORIGIN})
    other = client.get("/api/meta", headers={"Origin": "https://example.org"})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-origin" not in other.headers


def test_settings_require_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATASET_PATH", raising=False)
    monkeypatch.setenv("CORS_ORIGIN", ORIGIN)
    with pytest.raises(RuntimeError, match="DATASET_PATH"):
        load_settings()


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATASET_PATH", "data/videos.tsv")
    monkeypatch.setenv("CORS_ORIGIN", ORIGIN + "/")
    settings = load_settings()
    assert settings.dataset_path == Path("data/videos.tsv")
    assert settings.cors_origin == ORIGIN
