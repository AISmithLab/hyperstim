"""Video thumbnails, fetched from YouTube by the server and cached on disk (plan 009).

The site shows thumbnails from here instead of YouTube's image server, so a visitor's browser
contacts YouTube only once they press play. A thumbnail is kept at most 30 days (YouTube's API
terms), then fetched again; one YouTube doesn't have is remembered for a day, so a missing image
doesn't cost a request on every page view.
"""

import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Literal

Size = Literal["hq", "mq"]  # hq 480×360 (4:3, letterboxed), mq 320×180 (16:9)

KEEP_S = 30 * 24 * 3600
MISSING_S = 24 * 3600
SWEEP_EVERY_S = 3600
TIMEOUT_S = 10


class Unavailable(Exception):
    """YouTube couldn't be reached, or answered with an error."""


def fetch_from_youtube(video_id: str, size: Size) -> bytes | None:
    """The thumbnail's JPEG bytes, or None if YouTube has none. Sends no visitor data."""
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


class Thumbnails:
    def __init__(
        self,
        directory: Path,
        fetch: Callable[[str, Size], bytes | None] = fetch_from_youtube,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._dir = directory
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._swept = 0.0
        directory.mkdir(parents=True, exist_ok=True)

    def get(self, video_id: str, size: Size) -> Path | None:
        """The cached file (fetched first if needed), or None if YouTube has no thumbnail.

        `video_id` must already be checked: it becomes part of a file name.
        """
        self._sweep()
        image = self._dir / f"{video_id}_{size}.jpg"
        missing = image.with_suffix(".missing")
        now = self._clock()
        if self._fresh(image, KEEP_S, now):
            return image
        if self._fresh(missing, MISSING_S, now):
            return None
        data = self._fetch(video_id, size)
        if data is None:
            image.unlink(missing_ok=True)
            missing.touch()
            os.utime(missing, (now, now))
            return None
        # Written to a temporary file and renamed, so a reader never sees half an image.
        partial = image.with_suffix(f".{threading.get_ident()}.part")
        partial.write_bytes(data)
        os.utime(partial, (now, now))
        partial.replace(image)
        missing.unlink(missing_ok=True)
        return image

    @staticmethod
    def _fresh(path: Path, max_age_s: float, now: float) -> bool:
        try:
            return now - path.stat().st_mtime < max_age_s
        except FileNotFoundError:
            return False

    def _sweep(self) -> None:
        """Deletes expired files, at most once an hour, so nothing is kept past its time even
        if it's never asked for again."""
        now = self._clock()
        with self._lock:
            if now - self._swept < SWEEP_EVERY_S:
                return
            self._swept = now
        for path in self._dir.iterdir():
            max_age = MISSING_S if path.suffix == ".missing" else KEEP_S
            if not self._fresh(path, max_age, now):
                path.unlink(missing_ok=True)
