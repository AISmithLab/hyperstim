"""The video dataset, loaded into memory once at startup and ranked."""

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from hyperstim_api import scoring
from hyperstim_api.ranking import Order, Ranked, Ranking

log = logging.getLogger(__name__)

# The dataset's categories by their API key (the frontend's `lib/categories.ts`).
CATEGORIES: dict[str, str] = {
    "music": "music",
    "narrative": "narrative",
    "play & activity": "play",
    "educational": "educational",
    "gaming": "gaming",
}

# Per-minute counts (plan 004). A count of 0 is the calmest value there is, so it shows as
# percentile 0: in the pool thousands of videos tie at 0, and "at or below" puts them in the
# middle (e.g. 60). Shown values only; the score uses the pool percentiles (scoring.py).
EVENT_FEATURES = frozenset(
    {
        "cuts_per_min",
        "palette_change_per_min",
        "lstar_flash_per_min",
        "loudness_jumps_per_min",
        "build_resolve_per_min",
        "loudness_jump_at_cut_per_min",
    }
)

REQUIRED_COLUMNS = (
    "video_id",
    "title",
    "channel_id",
    "channel_title",
    "category",
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
    category: str | None  # a CATEGORIES key; None for a video analyzed live
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
    categories: frozenset[str]  # its videos' categories

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
    video_ranking: Ranking[Video]
    channel_ranking: Ranking[Channel]

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    def ranked_videos(
        self,
        sort: str,
        order: Order,
        category: str | None,
        query: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Ranked[Video]], int]:
        """A page of videos by `sort` (score or a feature), ranked within `category`."""
        return self.video_ranking.page(
            sort, order, lambda v: category is None or v.category == category, query, offset, limit
        )

    def ranked_channels(
        self,
        sort: str,
        order: Order,
        category: str | None,
        query: str | None,
        offset: int,
        limit: int,
        min_videos: int,
    ) -> tuple[list[Ranked[Channel]], int]:
        """A page of channels with `min_videos`+ videos and at least one in `category`."""
        return self.channel_ranking.page(
            sort,
            order,
            lambda c: (
                c.video_count >= min_videos and (category is None or category in c.categories)
            ),
            query,
            offset,
            limit,
        )

    def score_video(
        self, id: str, title: str, channel_id: str, channel: str, features: scoring.Features
    ) -> Video | None:
        """A video outside the dataset, scored against it; the dataset is unchanged.

        None if it has no feature value.
        """
        return _video(
            id, title, channel_id, channel, None, None, features, self.pools, self.composite_pool
        )


def _video(
    id: str,
    title: str,
    channel_id: str,
    channel: str,
    category: str | None,
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
        category=category,
        score=score,
        features=tuple(_shown(name, features, percentiles) for name in scoring.FEATURES),
        published_at=published_at,
    )


def _shown(name: str, features: scoring.Features, percentiles: dict[str, float | None]) -> Feature:
    """A feature as the site shows it (see EVENT_FEATURES)."""
    value = features.get(name)
    # A clip without sound has no loudness (2.3 blank), so no loudness jumps either.
    if name == "loudness_jumps_per_min" and value is None and features.get("lufs") is None:
        value = 0.0
    if value == 0 and name in EVENT_FEATURES:
        return Feature(key=name, value=value, percentile=0.0)
    return Feature(key=name, value=value, percentile=percentiles[name])


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
        categories=frozenset(v.category for v in members if v.category is not None),
    )


def _category(path: Path, raw: str) -> str:
    key = CATEGORIES.get(raw.strip())
    if key is None:
        raise ValueError(f"{path}: unknown category {raw!r}")
    return key


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
            _category(path, row["category"]),
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
        video_ranking=Ranking(videos, lambda v: (v.title, v.channel)),
        channel_ranking=Ranking(channels, lambda c: (c.name,)),
    )
