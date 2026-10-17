"""Video thumbnails, fetched from YouTube by the server on each request (plan 009).

The site shows thumbnails from here instead of YouTube's image server, so a visitor's browser
contacts YouTube only once they press play. Nothing is stored on the server; the visitor's
browser keeps the image for a day (the response's cache header).
"""

import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Literal

Size = Literal["hq", "mq"]  # hq 480×360 (4:3, letterboxed), mq 320×180 (16:9)
Fetch = Callable[[str, Size], bytes | None]

TIMEOUT_S = 10


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
