import os
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.thumbnails import KEEP_S, MISSING_S, Size, Thumbnails, Unavailable
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


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def youtube() -> FakeYouTube:
    fake = FakeYouTube()
    fake.images[(KNOWN, "hq")] = b"hq-image"
    fake.images[(KNOWN, "mq")] = b"mq-image"
    fake.images[(LIVE, "hq")] = b"live-image"
    return fake


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return tmp_path / "thumbnails"


@pytest.fixture
def client(
    tmp_path: Path,
    make_client: Callable[..., TestClient],
    youtube: FakeYouTube,
    clock: Clock,
    folder: Path,
) -> TestClient:
    dataset = write_dataset(tmp_path / "videos.tsv", [video_row(KNOWN, "UC-data", 1.0)])
    return make_client(dataset, thumbnails=Thumbnails(folder, youtube, clock))


def test_serves_a_dataset_videos_thumbnail_and_caches_it(
    client: TestClient, youtube: FakeYouTube
) -> None:
    for _ in range(2):
        response = client.get(f"/api/thumbnails/{KNOWN}")
        assert response.status_code == 200
        assert response.content == b"hq-image"
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["cache-control"] == "public, max-age=86400"
    assert client.get(f"/api/thumbnails/{KNOWN}?size=mq").content == b"mq-image"
    assert youtube.calls == [(KNOWN, "hq"), (KNOWN, "mq")]


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


def test_fetches_again_after_30_days(
    client: TestClient, youtube: FakeYouTube, clock: Clock
) -> None:
    client.get(f"/api/thumbnails/{KNOWN}")
    clock.now += KEEP_S - 1
    client.get(f"/api/thumbnails/{KNOWN}")
    assert len(youtube.calls) == 1
    youtube.images[(KNOWN, "hq")] = b"new-image"
    clock.now += 2
    assert client.get(f"/api/thumbnails/{KNOWN}").content == b"new-image"
    assert len(youtube.calls) == 2


def test_a_missing_thumbnail_is_remembered_for_a_day(
    client: TestClient, youtube: FakeYouTube, clock: Clock
) -> None:
    del youtube.images[(KNOWN, "hq")]
    for _ in range(2):
        assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 404
    assert len(youtube.calls) == 1
    clock.now += MISSING_S
    youtube.images[(KNOWN, "hq")] = b"hq-image"
    assert client.get(f"/api/thumbnails/{KNOWN}").content == b"hq-image"


def test_youtube_down_is_a_502_and_not_remembered(client: TestClient, youtube: FakeYouTube) -> None:
    youtube.down = True
    assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 502
    youtube.down = False
    assert client.get(f"/api/thumbnails/{KNOWN}").status_code == 200


def test_expired_files_are_deleted_even_if_never_asked_for_again(
    folder: Path, youtube: FakeYouTube, clock: Clock
) -> None:
    thumbnails = Thumbnails(folder, youtube, clock)
    thumbnails.get(KNOWN, "hq")
    old = folder / f"{KNOWN}_hq.jpg"
    stale = clock.now - KEEP_S
    os.utime(old, (stale, stale))
    clock.now += 3600  # the next sweep is due
    thumbnails.get(KNOWN, "mq")
    assert not old.exists()
    assert (folder / f"{KNOWN}_mq.jpg").exists()
