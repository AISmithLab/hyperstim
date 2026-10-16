"""The channel behind a YouTube channel or video link (plan 008).

The compare page's channel field takes links as well as names. A link we can answer from
what we have (a channel ID, a video in the dataset or checked live) costs nothing; anything
else asks YouTube through the pipeline, counts toward the live check's per-IP limit, and is
remembered for a day.
"""

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from hyperstim_api.analysis import AnalysisError, Analyzer, Pipeline
from hyperstim_api.dataset import Dataset

CACHE_S = 24 * 3600

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
HOSTS = {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "youtu.be"}
VIDEO_PREFIXES = {"shorts", "embed", "live", "v"}
NAMED_PREFIXES = {"c", "user"}


@dataclass(frozen=True)
class Link:
    """A parsed link: a channel ID, a channel page we must ask YouTube about, or a video."""

    kind: Literal["channel", "page", "video"]
    value: str  # the channel ID, the page's canonical URL, or the video ID


@dataclass(frozen=True)
class Found:
    channel_id: str
    name: str | None  # None when only YouTube knows it and we didn't need to ask
    in_dataset: bool


class NotALink(Exception):
    """Not a YouTube channel or video link."""


class NotFound(Exception):
    """YouTube has no channel for the link (removed, private, unknown handle)."""


def parse_link(text: str) -> Link | None:
    """A YouTube channel link (`/channel/UC…`, `/@handle`, `/c/…`, `/user/…`) or video link."""
    text = text.strip()
    if not text:
        return None
    url = urlsplit(text if re.match(r"^https?://", text, re.I) else f"https://{text}")
    host = (url.hostname or "").lower().removeprefix("www.")
    if host not in HOSTS:
        return None
    parts = [p for p in url.path.split("/") if p]
    if host == "youtu.be":
        return Link("video", parts[0]) if parts and VIDEO_ID.match(parts[0]) else None
    if not parts:
        return None
    first = parts[0]
    if first == "watch":
        video = parse_qs(url.query).get("v", [""])[0]
        return Link("video", video) if VIDEO_ID.match(video) else None
    if first in VIDEO_PREFIXES:
        return Link("video", parts[1]) if len(parts) > 1 and VIDEO_ID.match(parts[1]) else None
    if first == "channel":
        return Link("channel", parts[1]) if len(parts) > 1 and CHANNEL_ID.match(parts[1]) else None
    if first.startswith("@") and len(first) > 1:
        return Link("page", f"https://www.youtube.com/{first}")
    if first in NAMED_PREFIXES and len(parts) > 1:
        return Link("page", f"https://www.youtube.com/{first}/{parts[1]}")
    return None


class ChannelLookup:
    def __init__(
        self,
        dataset: Dataset,
        analyzer: Analyzer,
        pipeline: Pipeline,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._dataset = dataset
        self._analyzer = analyzer
        self._pipeline = pipeline
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[Link, tuple[float, str, str]] = {}  # link -> (when, channel ID, name)

    def find(self, text: str, ip: str) -> Found:
        """Raises NotALink, NotFound, or TooManyRequests (over the live check's limit)."""
        link = parse_link(text)
        if link is None:
            raise NotALink
        if link.kind == "channel":
            return self._found(link.value, None)
        if link.kind == "video":
            known = self._known_video(link.value)
            if known is not None:
                return self._found(*known)
        now = self._clock()
        with self._lock:
            cached = self._cache.get(link)
        if cached is not None and now - cached[0] < CACHE_S:
            return self._found(cached[1], cached[2])
        self._analyzer.count_request(ip)
        url = (
            f"https://www.youtube.com/watch?v={link.value}" if link.kind == "video" else link.value
        )
        try:
            channel_id, name = self._pipeline.channel(url)
        except AnalysisError as exc:
            raise NotFound from exc
        with self._lock:
            self._cache[link] = (now, channel_id, name)
        return self._found(channel_id, name)

    def _known_video(self, video_id: str) -> tuple[str, str | None] | None:
        video = self._dataset.videos_by_id.get(video_id)
        if video is not None:
            return video.channel_id, video.channel
        found = self._analyzer.snapshot(video_id)
        if found is not None and found[0].channel_id:
            return found[0].channel_id, found[0].channel
        return None

    def _found(self, channel_id: str, name: str | None) -> Found:
        channel = self._dataset.channels_by_id.get(channel_id)
        if channel is not None:
            return Found(channel_id, channel.name, True)
        return Found(channel_id, name or None, False)
