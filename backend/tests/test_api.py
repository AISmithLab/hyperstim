from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.config import load_settings
from hyperstim_api.scoring import FEATURES, build_pools, percentile_rank
from tests.conftest import ORIGIN, VIDEOS, Row, video_row, write_dataset

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
        {
            "id": "vid-c1",
            "title": "Title of vid-c1",
            "channelId": "chan-c",
            "channel": "Channel chan-c",
            "score": 100.0,
        },
        {
            "id": "vid-a1",
            "title": "Title of vid-a1",
            "channelId": "chan-a",
            "channel": "Channel chan-a",
            "score": pct(10),
        },
        {
            "id": "vid-a2",
            "title": "Title of vid-a2",
            "channelId": "chan-a",
            "channel": "Channel chan-a",
            "score": pct(9),
        },
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
        {"id": "chan-a", "name": "Channel chan-a", "score": pct(8), "videoCount": 5},
        {"id": "chan-b", "name": "Channel chan-b", "score": pct(3), "videoCount": 5},
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


DETAIL_IDS = ("aaaaaaaaaa1", "aaaaaaaaaa2", "aaaaaaaaaa3")


def detail_rows() -> list[Row]:
    """Feature i of video n is n * (i + 1); the last video has no motion_frac."""
    rows = []
    for n, video_id in enumerate(DETAIL_IDS, start=1):
        row = video_row(video_id, "UC-chan", 0.0)
        row.update({name: str(n * (i + 1)) for i, name in enumerate(FEATURES)})
        rows.append(row)
    rows[-1]["motion_frac"] = ""
    return rows


@pytest.fixture
def detail_client(tmp_path: Path, make_client: Callable[[Path], TestClient]) -> TestClient:
    return make_client(write_dataset(tmp_path / "videos.tsv", detail_rows()))


def test_video_detail(detail_client: TestClient) -> None:
    body = detail_client.get("/api/videos/aaaaaaaaaa2").json()
    assert {k: v for k, v in body.items() if k != "features"} == {
        "id": "aaaaaaaaaa2",
        "title": "Title of aaaaaaaaaa2",
        "channelId": "UC-chan",
        "channel": "Channel UC-chan",
        "score": 50.0,
    }
    assert [f["key"] for f in body["features"]] == list(FEATURES)
    assert body["features"][0] == {"key": "cuts_per_min", "value": 2.0, "percentile": 50.0}
    # motion_frac is missing for the third video, so the second is the pool's top.
    assert body["features"][4] == {"key": "motion_frac", "value": 10.0, "percentile": 100.0}


def test_video_detail_missing_value_is_null(detail_client: TestClient) -> None:
    features = detail_client.get("/api/videos/aaaaaaaaaa3").json()["features"]
    assert features[4] == {"key": "motion_frac", "value": None, "percentile": None}
    assert all(f["value"] is not None for i, f in enumerate(features) if i != 4)


def test_video_detail_percentiles_match_scoring(detail_client: TestClient) -> None:
    rows = detail_rows()
    pools = build_pools({k: float(row[k]) if row[k] else None for k in FEATURES} for row in rows)
    for row in rows:
        features = detail_client.get(f"/api/videos/{row['video_id']}").json()["features"]
        for f in features:
            expected = None if f["value"] is None else percentile_rank(f["value"], pools[f["key"]])
            assert f["percentile"] == (None if expected is None else round(expected, 1))


def test_video_detail_unknown_id(detail_client: TestClient) -> None:
    response = detail_client.get("/api/videos/zzzzzzzzzzz")
    assert response.status_code == 404
    assert response.json() == {"detail": "Video not found"}


@pytest.mark.parametrize("video_id", ["short", "aaaaaaaaaa12", "aaaaaaaaa.1", "aaaaaaaaa%201"])
def test_video_detail_malformed_id(detail_client: TestClient, video_id: str) -> None:
    assert detail_client.get(f"/api/videos/{video_id}").status_code == 422
