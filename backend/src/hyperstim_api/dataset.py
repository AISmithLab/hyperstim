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

REQUIRED_COLUMNS = (
    "video_id",
    "title",
    "channel_id",
    "channel_title",
    "published_at",
    *scoring.FEATURES,
)


@dataclass(frozen=True)
class Feature:
    key: str  # one of scoring.FEATURES
    value: float | None  # raw value; None if not measured
    percentile: float | None  # within the dataset, unrounded; None when value is


@dataclass(frozen=True)
class Video:
    id: str
    title: str
    channel_id: str
    channel: str
    score: float  # percentile of its composite among the dataset's, unrounded
    features: tuple[Feature, ...]  # the 12, in scoring.FEATURES order
    published_at: str | None  # ISO date; None for a video analyzed live


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    score: float  # unrounded mean of its videos' scores
    features: tuple[Feature, ...]  # the 12: mean raw value and mean percentile of its videos
    videos: tuple[Video, ...]  # oldest first; ties by id

    @property
    def video_count(self) -> int:
        return len(self.videos)


@dataclass(frozen=True)
class Dataset:
    videos: tuple[Video, ...]  # highest score first; ties by id
    channels: tuple[Channel, ...]  # highest score first; ties by id
    updated_at: str  # ISO date
    videos_by_id: dict[str, Video]
    channels_by_id: dict[str, Channel]
    pools: scoring.Pools  # the dataset's sorted values per feature
    composite_pool: list[float]  # the dataset's composites, sorted

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    def ranked_videos(self, sort: Sort, limit: int) -> list[Video]:
        return _take(self.videos, sort, limit)

    def ranked_channels(self, sort: Sort, limit: int, min_videos: int) -> tuple[list[Channel], int]:
        eligible = tuple(c for c in self.channels if c.video_count >= min_videos)
        return _take(eligible, sort, limit), len(eligible)

    def score_video(
        self, id: str, title: str, channel_id: str, channel: str, features: scoring.Features
    ) -> Video | None:
        """A video outside the dataset, scored against it; the dataset is unchanged.

        None if it has no feature value.
        """
        return _video(
            id, title, channel_id, channel, None, features, self.pools, self.composite_pool
        )


def _video(
    id: str,
    title: str,
    channel_id: str,
    channel: str,
    published_at: str | None,
    features: scoring.Features,
    pools: scoring.Pools,
    composite_pool: list[float],
) -> Video | None:
    value = scoring.composite(features, pools)
    if value is None:
        return None
    score = scoring.percentile_rank(value, composite_pool)
    if score is None:
        return None
    percentiles = scoring.feature_percentiles(features, pools)
    return Video(
        id=id,
        title=title,
        channel_id=channel_id,
        channel=channel,
        score=score,
        features=tuple(
            Feature(key=name, value=features.get(name), percentile=percentiles[name])
            for name in scoring.FEATURES
        ),
        published_at=published_at,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _channel(members: list[Video]) -> Channel:
    """A channel from its videos; each feature is the mean over the videos that have it."""
    features = []
    for i, name in enumerate(scoring.FEATURES):
        measured = [v.features[i] for v in members if v.features[i].value is not None]
        features.append(
            Feature(
                key=name,
                value=_mean([f.value for f in measured if f.value is not None]),
                percentile=_mean([f.percentile for f in measured if f.percentile is not None]),
            )
        )
    return Channel(
        id=members[0].channel_id,
        name=members[0].channel,
        score=sum(v.score for v in members) / len(members),
        features=tuple(features),
        videos=tuple(sorted(members, key=lambda v: (v.published_at or "", v.id))),
    )


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
    for row, features in kept:
        video = _video(
            row["video_id"].strip(),
            row["title"],
            row["channel_id"],
            row["channel_title"],
            row["published_at"].strip() or None,
            features,
            pools,
            composite_pool,
        )
        assert video is not None  # every kept row has a feature value
        videos.append(video)
    videos.sort(key=lambda v: (-v.score, v.id))

    by_channel: dict[str, list[Video]] = {}
    for video in videos:
        by_channel.setdefault(video.channel_id, []).append(video)
    channels = [_channel(members) for members in by_channel.values()]
    channels.sort(key=lambda c: (-c.score, c.id))

    meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    log.info(
        "Loaded %d videos, %d channels from %s (%d rows skipped: no ID or no feature values)",
        len(videos),
        len(channels),
        path,
        skipped,
    )
    return Dataset(
        videos=tuple(videos),
        channels=tuple(channels),
        updated_at=meta["featuresDate"],
        videos_by_id={v.id: v for v in videos},
        channels_by_id={c.id: c for c in channels},
        pools=pools,
        composite_pool=composite_pool,
    )
