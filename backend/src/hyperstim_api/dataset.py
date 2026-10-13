"""The video dataset, loaded into memory once at startup and ranked."""

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hyperstim_api import scoring

log = logging.getLogger(__name__)

Sort = Literal["score_desc", "score_asc"]

REQUIRED_COLUMNS = ("video_id", "title", "channel_id", "channel_title", *scoring.FEATURES)


@dataclass(frozen=True)
class Video:
    id: str
    title: str
    channel_id: str
    channel: str
    score: float  # percentile of its composite among the dataset's, unrounded


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    score: float  # unrounded mean of its videos' scores
    video_count: int


@dataclass(frozen=True)
class Dataset:
    videos: tuple[Video, ...]  # highest score first; ties by id
    channels: tuple[Channel, ...]  # highest score first; ties by id
    updated_at: str  # ISO date

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    def ranked_videos(self, sort: Sort, limit: int) -> list[Video]:
        return _take(self.videos, sort, limit)

    def ranked_channels(self, sort: Sort, limit: int, min_videos: int) -> tuple[list[Channel], int]:
        eligible = tuple(c for c in self.channels if c.video_count >= min_videos)
        return _take(eligible, sort, limit), len(eligible)


def _take[T](ranked: tuple[T, ...], sort: Sort, limit: int) -> list[T]:
    # Ascending is the exact reverse of descending, so ranks counted back from
    # `total` agree with the descending ranks, ties included.
    if sort == "score_desc":
        return list(ranked[:limit])
    return list(reversed(ranked[-limit:]))


def meta_path(dataset_path: Path) -> Path:
    return dataset_path.with_suffix(".meta.json")


def _float(raw: str | None) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def load_dataset(path: Path) -> Dataset:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(missing)}")
        rows = list(reader)

    kept: list[tuple[dict[str, str], dict[str, float | None]]] = []
    skipped = 0
    for row in rows:
        features = {name: _float(row[name]) for name in scoring.FEATURES}
        if not row["video_id"].strip() or all(v is None for v in features.values()):
            skipped += 1
            continue
        kept.append((row, features))

    pools = scoring.build_pools(features for _, features in kept)
    composites = []
    for _, features in kept:
        value = scoring.composite(features, pools)
        assert value is not None  # every kept row has a feature value
        composites.append(value)
    composite_pool = sorted(composites)
    videos = []
    for (row, _), value in zip(kept, composites, strict=True):
        score = scoring.percentile_rank(value, composite_pool)
        assert score is not None  # the pool holds at least this video
        videos.append(
            Video(
                id=row["video_id"].strip(),
                title=row["title"],
                channel_id=row["channel_id"],
                channel=row["channel_title"],
                score=score,
            )
        )
    videos.sort(key=lambda v: (-v.score, v.id))

    by_channel: dict[str, list[Video]] = {}
    for video in videos:
        by_channel.setdefault(video.channel_id, []).append(video)
    channels = [
        Channel(
            id=channel_id,
            name=members[0].channel,
            score=sum(v.score for v in members) / len(members),
            video_count=len(members),
        )
        for channel_id, members in by_channel.items()
    ]
    channels.sort(key=lambda c: (-c.score, c.id))

    meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    log.info(
        "Loaded %d videos, %d channels from %s (%d rows skipped: no ID or no feature values)",
        len(videos),
        len(channels),
        path,
        skipped,
    )
    return Dataset(videos=tuple(videos), channels=tuple(channels), updated_at=meta["featuresDate"])
