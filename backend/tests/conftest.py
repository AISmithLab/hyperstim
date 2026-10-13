import csv
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyperstim_api.config import Settings
from hyperstim_api.dataset import REQUIRED_COLUMNS
from hyperstim_api.main import create_app
from hyperstim_api.scoring import FEATURES

ORIGIN = "http://localhost:3000"

# Synthetic videos: (id, channel_id, value of every feature). With all 12 features
# equal, a video's score is the percentile of that value among the scored videos.
VIDEOS = [
    ("vid-a1", "chan-a", 10.0),
    ("vid-a2", "chan-a", 9.0),
    ("vid-a3", "chan-a", 8.0),
    ("vid-a4", "chan-a", 7.0),
    ("vid-a5", "chan-a", 6.0),
    ("vid-b1", "chan-b", 5.0),
    ("vid-b2", "chan-b", 4.0),
    ("vid-b3", "chan-b", 3.0),
    ("vid-b4", "chan-b", 2.0),
    ("vid-b5", "chan-b", 1.0),
    ("vid-c1", "chan-c", 11.0),  # chan-c has 2 videos: below the default minVideos
    ("vid-c2", "chan-c", 0.0),
]

Row = dict[str, str]


def video_row(video_id: str, channel_id: str, value: float | None) -> Row:
    row = {
        "video_id": video_id,
        "title": f"Title of {video_id}",
        "channel_id": channel_id,
        "channel_title": f"Channel {channel_id}",
    }
    row.update({name: "" if value is None else str(value) for name in FEATURES})
    return row


def write_dataset(path: Path, rows: list[Row], features_date: str = "2026-09-01") -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, REQUIRED_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    path.with_suffix(".meta.json").write_text(json.dumps({"featuresDate": features_date}))
    return path


@pytest.fixture
def dataset_path(tmp_path: Path) -> Path:
    return write_dataset(tmp_path / "videos.tsv", [video_row(*v) for v in VIDEOS])


@pytest.fixture
def make_client() -> Iterator[Callable[[Path], TestClient]]:
    clients: list[TestClient] = []

    def make(path: Path) -> TestClient:
        client = TestClient(create_app(Settings(dataset_path=path, cors_origin=ORIGIN)))
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


@pytest.fixture
def client(dataset_path: Path, make_client: Callable[[Path], TestClient]) -> TestClient:
    return make_client(dataset_path)
