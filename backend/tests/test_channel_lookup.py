from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.analysis import AnalysisError, parse_channel
from hyperstim_api.channel_lookup import Link, parse_link
from tests.conftest import FakePipeline, video_row, write_dataset

CHANNEL = "UCaaaaaaaaaaaaaaaaaaaaaa"
DATASET_CHANNEL = "UCdddddddddddddddddddddd"


@pytest.mark.parametrize(
    ("text", "link"),
    [
        (f"https://www.youtube.com/channel/{CHANNEL}", Link("channel", CHANNEL)),
        (f"youtube.com/channel/{CHANNEL}/videos", Link("channel", CHANNEL)),
        (
            "https://www.youtube.com/@KitAndKate",
            Link("page", "https://www.youtube.com/@KitAndKate"),
        ),
        ("m.youtube.com/@KitAndKate/featured", Link("page", "https://www.youtube.com/@KitAndKate")),
        (
            "https://www.youtube.com/c/KitAndKate",
            Link("page", "https://www.youtube.com/c/KitAndKate"),
        ),
        (
            "https://www.youtube.com/user/kitkate",
            Link("page", "https://www.youtube.com/user/kitkate"),
        ),
        ("https://www.youtube.com/watch?v=Bfy4GDe4-gI&t=3", Link("video", "Bfy4GDe4-gI")),
        ("https://youtu.be/Bfy4GDe4-gI", Link("video", "Bfy4GDe4-gI")),
        ("youtube.com/shorts/Bfy4GDe4-gI", Link("video", "Bfy4GDe4-gI")),
        ("kit and kate", None),
        ("https://example.com/@KitAndKate", None),
        ("https://www.youtube.com/channel/nope", None),
        ("https://www.youtube.com/", None),
    ],
)
def test_parse_link(text: str, link: Link | None) -> None:
    assert parse_link(text) == link


def test_parse_channel() -> None:
    assert parse_channel('{"channel_id": "UCx", "channel": "Kit"}\n') == ("UCx", "Kit")
    with pytest.raises(AnalysisError):
        parse_channel('{"channel_id": null}')


def lookup(client: TestClient, url: str) -> Any:  # the test client's response
    return client.get("/api/channel-lookup", params={"url": url})


@pytest.fixture
def real_ids(tmp_path: Path, make_client: Callable[..., TestClient]) -> TestClient:
    """A dataset with YouTube-shaped IDs, so links to it parse."""
    rows = [video_row(f"vidvidvid0{i}", DATASET_CHANNEL, float(i)) for i in range(3)]
    return make_client(write_dataset(tmp_path / "videos.tsv", rows))


def test_channel_link_needs_no_youtube(real_ids: TestClient, pipeline: FakePipeline) -> None:
    body = lookup(real_ids, f"https://www.youtube.com/channel/{DATASET_CHANNEL}").json()
    assert body == {
        "channelId": DATASET_CHANNEL,
        "name": f"Channel {DATASET_CHANNEL}",
        "inDataset": True,
    }
    # Not in the dataset: no name, and still no YouTube call.
    body = lookup(real_ids, f"https://www.youtube.com/channel/{CHANNEL}").json()
    assert body == {"channelId": CHANNEL, "name": None, "inDataset": False}
    assert pipeline.channel_calls == []


def test_dataset_video_gives_its_channel(real_ids: TestClient, pipeline: FakePipeline) -> None:
    body = lookup(real_ids, "https://youtu.be/vidvidvid01").json()
    assert body["channelId"] == DATASET_CHANNEL
    assert body["inDataset"] is True
    assert pipeline.channel_calls == []


def test_handle_asks_youtube_once_and_counts_toward_the_limit(
    dataset_path: Path, make_client: Callable[..., TestClient], pipeline: FakePipeline
) -> None:
    client = make_client(dataset_path, limit_per_ip=1)
    pipeline.links["https://www.youtube.com/@KitAndKate"] = (CHANNEL, "Kit and Kate")
    body = lookup(client, "https://www.youtube.com/@KitAndKate").json()
    assert body == {"channelId": CHANNEL, "name": "Kit and Kate", "inDataset": False}
    # Cached: no second call, and it doesn't count again.
    assert lookup(client, "youtube.com/@KitAndKate/videos").status_code == 200
    assert pipeline.channel_calls == ["https://www.youtube.com/@KitAndKate"]
    # The limit (1) is used up: a new lookup, or a new analysis, is refused.
    assert lookup(client, "https://www.youtube.com/@Other").status_code == 429
    assert client.post("/api/analyses/aaaaaaaaaaa").status_code == 429


def test_video_link_uses_the_videos_channel(
    dataset_path: Path, make_client: Callable[..., TestClient], pipeline: FakePipeline
) -> None:
    client = make_client(dataset_path)
    pipeline.links["https://www.youtube.com/watch?v=Bfy4GDe4-gI"] = ("chan-b", "Channel chan-b")
    body = lookup(client, "https://youtu.be/Bfy4GDe4-gI").json()
    # chan-b is in the dataset: its name from there.
    assert body == {"channelId": "chan-b", "name": "Channel chan-b", "inDataset": True}


def test_video_checked_live_gives_its_channel_without_asking_youtube(
    client: TestClient, pipeline: FakePipeline
) -> None:
    pipeline.channels["ccccccccccc"] = "chan-a"
    client.post("/api/analyses/ccccccccccc")
    client.app.state.analyzer.run_next()  # type: ignore[attr-defined]
    body = lookup(client, "https://youtu.be/ccccccccccc").json()
    assert body == {"channelId": "chan-a", "name": "Channel chan-a", "inDataset": True}
    assert pipeline.channel_calls == []


def test_unknown_channel_and_bad_links(client: TestClient) -> None:
    assert lookup(client, "https://www.youtube.com/@Nobody").status_code == 404
    assert lookup(client, "kit and kate").status_code == 422
    assert client.get("/api/channel-lookup").status_code == 422
