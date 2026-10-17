from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.thumbnails import Size, Unavailable
from tests.conftest import video_row, write_dataset

KNOWN = "data0000000"
LIVE = "live0000000"
UNKNOWN = "else0000000"


class FakeYouTube:
    """Stands in for YouTube's image server: `images` maps (id, size) to bytes; anything else
    is missing, or raises Unavailable while `down` is set."""

    def __init__(self) -> None:
        self.images: dict[tuple[str, Size], bytes] = {}
        self.calls: list[tuple[str, Size]] = []
        self.down = False

    def __call__(self, video_id: str, size: Size) -> bytes | None:
        self.calls.append((video_id, size))
        if self.down:
            raise Unavailable
        return self.images.get((video_id, size))


@pytest.fixture
def youtube() -> FakeYouTube:
    fake = FakeYouTube()
    fake.images[(KNOWN, "hq")] = b"hq-image"
    fake.images[(KNOWN, "mq")] = b"mq-image"
    fake.images[(LIVE, "hq")] = b"live-image"
    return fake


@pytest.fixture
def client(
    tmp_path: Path, make_client: Callable[..., TestClient], youtube: FakeYouTube
) -> TestClient:
    dataset = write_dataset(tmp_path / "videos.tsv", [video_row(KNOWN, "UC-data", 1.0)])
    return make_client(dataset, fetch_thumbnail=youtube)


def test_serves_a_dataset_videos_thumbnail_fetched_each_time(
    client: TestClient, youtube: FakeYouTube
) -> None:
    for _ in range(2):
        response = client.get(f"/api/thumbnails/{KNOWN}")
        assert response.status_code == 200
        assert response.content == b"hq-image"
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["cache-control"] == "public, max-age=86400"
    assert client.get(f"/api/thumbnails/{KNOWN}?size=mq").content == b"mq-image"
    assert youtube.calls == [(KNOWN, "hq"), (KNOWN, "hq"), (KNOWN, "mq")]  # nothing stored


def test_serves_a_live_checked_video_but_no_unknown_one(
    client: TestClient, youtube: FakeYouTube
) -> None:
    assert client.get(f"/api/thumbnails/{LIVE}").status_code == 404
    client.post(f"/api/analyses/{LIVE}")
    assert client.get(f"/api/thumbnails/{LIVE}").content == b"live-image"
    assert client.get(f"/api/thumbnails/{UNKNOWN}").status_code == 404
    assert youtube.calls == [(LIVE, "hq")]  # unknown videos never reach YouTube


@pytest.mark.parametrize("path", [f"{KNOWN}?size=maxres", "../../etc/passwd", "short"])
def test_rejects_bad_sizes_and_ids(client: TestClient, path: str) -> None:
    assert client.get(f"/api/thumbnails/{path}").status_code in (404, 422)


def test_a_missing_thumbnail_is_a_404(client: TestClient, youtube: FakeYouTube) -> None:
    del youtube.images[(KNOWN, "hq")]
    assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 404


def test_youtube_down_is_a_502(client: TestClient, youtube: FakeYouTube) -> None:
    youtube.down = True
    assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 502
    youtube.down = False
    assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 200
