"""Video thumbnails, fetched from YouTube by the server and cached on disk (plan 009).

The site shows thumbnails from here instead of YouTube's image server, so a visitor's browser
contacts YouTube only once they press play. Each image is kept for 30 days, so YouTube sees at
most one request per video and size in that time, however often it's shown; the visitor's
browser also keeps it for a day (the response's cache header).
"""

import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Literal

Size = Literal["hq", "mq"]  # hq 480×360 (4:3, letterboxed), mq 320×180 (16:9)
Fetch = Callable[[str, Size], bytes | None]

TIMEOUT_S = 10
KEEP_S = 30 * 24 * 3600  # a cached image is fetched again after this
MISSING_S = 24 * 3600  # "YouTube has none" is remembered this long


class Unavailable(Exception):
    """YouTube couldn't be reached, or answered with an error."""


def fetch_from_youtube(video_id: str, size: Size) -> bytes | None:
    """The thumbnail's JPEG bytes, or None if YouTube has none. Sends no visitor data.

    `video_id` must already be checked: it becomes part of the URL.
    """
    url = f"https://i.ytimg.com/vi/{video_id}/{size}default.jpg"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise Unavailable from exc
    except OSError as exc:
        raise Unavailable from exc


class ThumbnailCache:
    """Thumbnails on disk, one file per video and size; fetched from YouTube when missing or
    older than KEEP_S. Holds only public images, nothing about visitors."""

    def __init__(self, directory: Path, fetch: Fetch, clock: Callable[[], float] = time.time):
        self._dir = directory
        self._fetch = fetch
        self.clock = clock
        directory.mkdir(parents=True, exist_ok=True)

    def get(self, video_id: str, size: Size) -> bytes | None:
        """The JPEG bytes, or None if YouTube has none. Raises Unavailable only when YouTube
        can't be reached and nothing is cached; a stale image beats none.

        `video_id` must already be checked: it becomes part of the file name.
        """
        image = self._dir / f"{video_id}_{size}.jpg"
        missing = self._dir / f"{video_id}_{size}.missing"
        now = self.clock()
        if _age(image, now) < KEEP_S:
            return image.read_bytes()
        if _age(missing, now) < MISSING_S:
            return None
        try:
            data = self._fetch(video_id, size)
        except Unavailable:
            if image.exists():
                return image.read_bytes()
            raise
        if data is None:
            _write(missing, b"", now)
            image.unlink(missing_ok=True)
            return None
        _write(image, data, now)  # whole or not at all: written aside, then renamed
        missing.unlink(missing_ok=True)
        return data


def _age(path: Path, now: float) -> float:
    try:
        return now - path.stat().st_mtime
    except FileNotFoundError:
        return float("inf")


def _write(path: Path, data: bytes, now: float) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.utime(tmp, (now, now))
    os.replace(tmp, path)
