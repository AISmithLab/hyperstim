"""Which uploads the dataset takes (plan 013, decision 1).

Every upload has a fixed random number `rank(video_id)` in [0, 1). The dataset is v2's
picks plus every eligible upload (2015 onwards) whose number is below a cut-off that only
rises, so each eligible upload has the same chance, whenever it came out; plus each channel's
eligible uploads with the lowest numbers until it has `FLOOR` (its floor: the videos the
cut-off would take first for it, taken sooner). Eligibility is
v2's: made for kids, 2-60 minutes, not a Short, online and not blocked in the US.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

RULE_VERSION = "v1"
FIRST_YEAR = 2015  # v2's first year (YouTube Kids' launch)
SETTLE_S = 24 * 3600  # an upload is checked once it's a day old
REGION = "US"
FLOOR = 5  # each channel's lowest-numbered eligible uploads taken until it has this many
# v2's duration rules (57_enumerate_and_sample.py): <= 60 s is a Short without asking,
# 60-180 s may be one (asked at /shorts/<id>), > 180 s can't be.
MIN_DURATION_S, MAX_DURATION_S = 120, 3600
SHORT_CERTAIN_S, SHORT_POSSIBLE_S = 60, 180

Verdict = Literal["eligible", "gone", "region", "not_for_kids", "duration", "short", "wait"]


def rank(video_id: str) -> float:
    """The upload's fixed random number in [0, 1); anyone can recompute it."""
    digest = hashlib.sha256(f"hyperstim-sample-{RULE_VERSION}:{video_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def duration_s(iso: str | None) -> int | None:
    """An ISO 8601 duration from the Data API ("PT1H2M3S") in seconds; None if unreadable."""
    m = _DURATION.match(iso or "")
    if not m or not any(m.groups()):
        return None
    days, hours, minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


@dataclass(frozen=True)
class Details:
    """What the Data API says about one upload (`videos.list`), or None if it's gone."""

    made_for_kids: bool | None
    duration_s: int | None
    live: bool  # still upcoming or live: can't be measured yet
    region_blocked: bool
    title: str
    description: str
    tags: str  # joined with " | ", as v2's snippets
    channel_title: str
    published_at: str = ""


def region_blocked(content_details: dict[str, object], region: str = REGION) -> bool:
    """v2's check (68_wide_pool_resample.py): blocked in `region`, or allowed elsewhere only."""
    restriction = content_details.get("regionRestriction")
    if not isinstance(restriction, dict):
        return False
    if region in (restriction.get("blocked") or []):
        return True
    allowed = restriction.get("allowed")
    return allowed is not None and region not in allowed


def needs_shorts_probe(details: Details) -> bool:
    d = details.duration_s
    return d is not None and MIN_DURATION_S <= d <= SHORT_POSSIBLE_S


def verdict(details: Details | None, is_short: bool | None = None) -> Verdict:
    """v2's checks in v2's order. `is_short` is the /shorts/ probe's answer, asked only when
    `needs_shorts_probe`; undecided counts as a Short, as in v2."""
    if details is None:
        return "gone"
    if details.live:
        return "wait"
    if details.region_blocked:
        return "region"
    if details.made_for_kids is not True:
        return "not_for_kids"
    d = details.duration_s
    if d is None or d <= SHORT_CERTAIN_S or d < MIN_DURATION_S or d > MAX_DURATION_S:
        return "duration"
    if needs_shorts_probe(details) and is_short is not False:
        return "short"
    return "eligible"
