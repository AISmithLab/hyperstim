"""The collector's work, one small job at a time (plan 013, decisions 2-7).

`Collector.tick()` does whatever is due and says how long to wait before the next tick:
read channels' newest uploads (daily), run a few discovery searches (each query weekly),
re-check near misses (monthly) and dataset videos (monthly), check the next uploads by
number, and download and measure the next eligible one when the pace allows.
"""

import contextlib
import csv
import functools
import importlib.util
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hyperstim_api import scoring
from hyperstim_api.analysis import BLOCK_MARKER, PIPELINE_DIR, AnalysisError, Pipeline
from hyperstim_api.collector import sampling
from hyperstim_api.collector.seed import tier
from hyperstim_api.collector.store import Store, Upload
from hyperstim_api.collector.youtube import DataApi, OutOfUnits, quota_day

log = logging.getLogger(__name__)

DAY_S = 24 * 3600
# v2's discovery queries (56_channel_yield_probe.py), run each once a week.
QUERIES: tuple[str, ...] = (
    "nursery rhymes", "kids songs", "children's songs", "sing along songs for kids",
    "kids music videos", "toddler songs",
    "cartoons for kids", "kids animation series", "stories for children",
    "kids cartoon full episodes", "storytime for kids", "fairy tales for kids",
    "preschool cartoon show",
    "learning videos for kids", "educational videos for children", "kids science experiments",
    "learn colors and shapes", "phonics for kids", "math for kids", "stem for kids",
    "preschool learning",
    "kids gaming", "minecraft for kids", "roblox gameplay for kids", "family friendly gaming",
    "kids game commentary", "video games for kids",
    "toy play for kids", "kids crafts", "diy for kids", "kids challenge videos",
    "play doh videos for kids", "arts and crafts for children", "sensory play for toddlers",
    "outdoor activities for kids", "kids exercise",
)  # fmt: skip
QUERIES_PER_DAY = math.ceil(len(QUERIES) / 7)
MIN_SUBSCRIBERS = 10_000  # v2's channel rules
MIN_VIDEOS = 100  # more than this many
CHANNELS_PER_TICK = 25  # newest-uploads reads per tick, so other work isn't held up
MAX_PAGES = 200  # a channel's uploads read in one go (50 a page)
CANDIDATE_BUFFER = 5  # eligible uploads kept ready for download
OFFLINE_EVERY_S = 30 * DAY_S
BLOCK_WAIT_S = 6 * 3600
MAX_BLOCK_WAIT_S = 48 * 3600
FREE_SPACE_MIN = 50 * 1024**3
# The classifier's names → the dataset's category keys (dataset.CATEGORIES).
CATEGORY_NAMES = {
    "music": "music",
    "narrative": "narrative",
    "play": "play & activity",
    "educational": "educational",
    "gaming": "gaming",
}
LIVE_RUNNING = {"queued", "lookup", "download", "measure"}


@functools.cache
def load_classifier() -> Callable[[dict[str, str]], str | None]:
    """v2's keyword classifier (`pipeline/63_classify_categories.py`, unchanged): title, then
    tags, then description; None when no keyword fires."""
    path = PIPELINE_DIR / "63_classify_categories.py"
    spec = importlib.util.spec_from_file_location("classify_categories", path)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def classify(row: dict[str, str]) -> str | None:
        category = module.classify(row)[0]
        return CATEGORY_NAMES[category] if category else None

    return classify


def utc(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


@dataclass
class Settings:
    data_dir: Path  # collector.db and the exported files (collected/)
    clips_dir: Path  # clips/, cache/ and a work/ folder, on the clips volume
    analysis_dir: Path | None  # the live analysis's results and block marker
    per_day: int = 150
    units_per_day: int = 7000
    provenance: dict[str, str] = field(default_factory=dict)


class Collector:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        api: DataApi,
        pipeline: Pipeline,
        is_short: Callable[[str], bool | None],
        classify: Callable[[dict[str, str]], str | None],
        probe_block: Callable[[str], bool],
        clock: Callable[[], float] = time.time,
        rng: random.Random | None = None,
    ) -> None:
        self.s = settings
        self.store = store
        self.api = api
        self.pipeline = pipeline
        self.is_short = is_short
        self.classify = classify
        self.probe_block = probe_block  # after a failed download: is YouTube blocking us?
        self.clock = clock
        self.rng = rng or random.Random()

    # --- the loop --------------------------------------------------------------------

    def tick(self) -> float:
        """Do what's due; returns the seconds to wait before the next tick."""
        now = self.clock()
        out_of_units = self.store.get("out_of_units") == quota_day(now)
        if not out_of_units:
            try:
                self.refresh_uploads(now)
                self.discover(now)
                self.check_near_misses(now)
                self.check_online(now)
                self.check_candidates(now)
            except OutOfUnits as exc:
                log.warning("Data API units used up for today: %s", exc)
                self.store.set("out_of_units", quota_day(now))
        wait = self.maybe_download(self.clock())
        return max(5.0, min(wait, 60.0))

    # --- upload lists ----------------------------------------------------------------

    def refresh_uploads(self, now: float) -> None:
        """Read the newest uploads of channels not read in the last day."""
        due = self.store.db.execute(
            "SELECT id FROM channels WHERE status = 'in' AND COALESCE(listed_at, 0) < ? "
            "ORDER BY COALESCE(listed_at, 0), id LIMIT ?",
            (now - DAY_S, CHANNELS_PER_TICK),
        ).fetchall()
        for row in due:
            added = self.list_uploads(row["id"], stop_at_known=True)
            self.store.update_channel(row["id"], listed_at=now)
            if added:
                log.info("Channel %s: %d new uploads", row["id"], added)

    def list_uploads(self, channel_id: str, stop_at_known: bool) -> int:
        """Pages through the channel's uploads (newest first); with `stop_at_known`, only back
        to the first one we already have."""
        added, token = 0, None
        for _ in range(MAX_PAGES):
            uploads, token = self.api.uploads_page(channel_id, token)
            known = stop_at_known and any(self.store.known(vid) for vid, _ in uploads)
            added += self.store.add_uploads(channel_id, uploads)
            if known or not token:
                break
        return added

    # --- channels --------------------------------------------------------------------

    def discover(self, now: float) -> None:
        """Run today's share of v2's discovery queries (each query once a week)."""
        today = utc(now)[:10]
        if self.store.get("discovery_day") == today:
            return
        start = int(self.store.get("discovery_next", "0"))
        for i in range(start, min(start + QUERIES_PER_DAY, len(QUERIES))):
            found = [c for c in self.api.search_channels(QUERIES[i]) if c.startswith("UC")]
            self.admit(found, QUERIES[i], now)
            self.store.set("discovery_next", i + 1)
        if int(self.store.get("discovery_next")) >= len(QUERIES):
            self.store.set("discovery_next", 0)
            self.store.set("channels_checked_at", today)
        self.store.set("discovery_day", today)

    def admit(self, channel_ids: list[str], query: str, now: float) -> None:
        """Channels found by a query: add new ones that meet v2's rules, note the others."""
        new = [c for c in dict.fromkeys(channel_ids) if self.store.channel_status(c) is None]
        for i in range(0, len(new), 50):
            stats = self.api.channels(new[i : i + 50])
            for channel_id in new[i : i + 50]:
                found = stats.get(channel_id)
                if found is None:
                    continue
                self.judge(channel_id, found.title, found.subscriber_count, found.video_count,
                           now, query)  # fmt: skip

    def judge(
        self, channel_id: str, title: str, subscribers: int, videos: int, now: float, query: str
    ) -> None:
        if title.strip().endswith("- Topic"):
            status = "rejected"  # made by YouTube from a music catalogue (v2's rule)
        elif subscribers >= MIN_SUBSCRIBERS and videos > MIN_VIDEOS:
            status = "in"
        else:
            status = "near_miss"
        fields: dict[str, Any] = {
            "title": title,
            "subscriber_count": subscribers,
            "video_count": videos,
            "tier": tier(subscribers),
            "status": status,
            "joined_at": utc(now) if status == "in" else None,
            "checked_at": utc(now),
        }
        if self.store.channel_status(channel_id) is None:
            self.store.upsert_channel(id=channel_id, source="discovery", queries=query, **fields)
        else:  # a near miss read again: it keeps its source and queries
            self.store.update_channel(channel_id, **fields)
        if status == "in":
            added = self.list_uploads(channel_id, stop_at_known=False)
            self.store.update_channel(channel_id, listed_at=now)
            log.info("New channel %s (%s): %d uploads", channel_id, title, added)

    def check_near_misses(self, now: float) -> None:
        """Channels found before but under v2's bar, read again monthly."""
        due = self.store.db.execute(
            "SELECT id, queries, checked_at FROM channels WHERE status = 'near_miss' "
            "AND COALESCE(checked_at, '') < ? ORDER BY checked_at LIMIT 50",
            (utc(now - 30 * DAY_S),),
        ).fetchall()
        if not due:
            return
        stats = self.api.channels([r["id"] for r in due])
        for row in due:
            found = stats.get(row["id"])
            if found is None:
                self.store.update_channel(row["id"], checked_at=utc(now))
                continue
            self.judge(row["id"], found.title, found.subscriber_count, found.video_count, now,
                       row["queries"])  # fmt: skip

    # --- the dataset's videos still online -------------------------------------------

    def check_online(self, now: float) -> None:
        """Re-check dataset videos not checked in a month; take out the ones gone."""
        due = self.store.in_dataset(now - OFFLINE_EVERY_S, 50)
        if not due:
            return
        details = self.api.videos(due)
        for video_id in due:
            found = details.get(video_id)
            if found is None or found.region_blocked:
                reason = "gone" if found is None else "region"
                self.store.set_state(video_id, "removed", reason)
                self.store.add_removed(video_id, utc(now), reason)
                log.info("Took out %s: %s", video_id, reason)
                self.export()
            else:
                self.store.db.execute(
                    "UPDATE uploads SET online_at = ? WHERE id = ?", (now, video_id)
                )

    # --- picking ---------------------------------------------------------------------

    def check_candidates(self, now: float) -> None:
        """Check uploads below the cut-off that are new to us (new uploads, new channels) at
        once, then the next ones by number until a few eligible ones are ready."""
        settled = utc(now - sampling.SETTLE_S)
        while True:
            below = self.store.cutoff()
            ids = self.store.next_unchecked(now, sampling.FIRST_YEAR, settled, 50, below)
            if not ids and self.store.count("eligible") < CANDIDATE_BUFFER:
                ids = self.store.next_unchecked(now, sampling.FIRST_YEAR, settled, 50)
            if not ids:
                return
            self.check(ids, now)

    def check(self, ids: list[str], now: float) -> None:
        """Eligibility of up to 50 uploads, by v2's checks."""
        details = self.api.videos(ids)
        for video_id in ids:
            found = details.get(video_id)
            short = None
            if found is not None and sampling.needs_shorts_probe(found):
                short = self.is_short(video_id)
            verdict = sampling.verdict(found, short)
            if verdict == "wait":  # a premiere or stream not over yet
                self.store.db.execute(
                    "UPDATE uploads SET retry_at = ? WHERE id = ?", (now + DAY_S, video_id)
                )
                continue
            fields: dict[str, Any] = {"checked_at": now}
            if found is not None:
                fields.update(
                    title=found.title,
                    description=found.description,
                    tags=found.tags,
                    channel_title=found.channel_title,
                    duration_s=found.duration_s,
                )
            state = "eligible" if verdict == "eligible" else "ineligible"
            self.store.set_state(video_id, state, "" if state == "eligible" else verdict,
                                 **fields)  # fmt: skip

    # --- downloading and measuring ---------------------------------------------------

    def per_day(self, now: float) -> float:
        """The pace, halved after repeated blocks and doubled back after a week without one."""
        factor = float(self.store.get("pace_factor", "1"))
        if factor < 1 and now - float(self.store.get("blocked_at", "0")) > 7 * DAY_S:
            factor = min(1.0, factor * 2)
            self.store.set("pace_factor", factor)
            self.store.set("blocked_at", now)  # the next doubling a week later
        return self.s.per_day * factor

    def maybe_download(self, now: float) -> float:
        """Download and measure one video if it's time; returns the seconds until the next."""
        blocked_until = float(self.store.get("blocked_until", "0"))
        if now < blocked_until:
            return blocked_until - now
        if self.live_blocked(now):
            return 600
        next_at = float(self.store.get("next_download_at", "0"))
        if now < next_at:
            return next_at - now
        if self.store.attempts_since(now - DAY_S) >= self.per_day(now):
            return 600
        if self.live_running() or self.low_on_space():
            return 60
        upload = self.store.next_eligible()
        if upload is None:
            return 60
        self.collect(upload, now)
        gap = self.rng.expovariate(self.per_day(now) / DAY_S)  # random spacing, on average even
        self.store.set("next_download_at", self.clock() + gap)
        return gap

    def collect(self, upload: Upload, now: float) -> None:
        reused = self.live_result(upload.id)
        work = self.s.clips_dir / "work" / upload.id
        shutil.rmtree(work, ignore_errors=True)
        try:
            if reused is not None:
                features, source = reused, "live analysis"
            else:
                work.mkdir(parents=True)
                self.pipeline.download(upload.id, work)
                features = self.pipeline.measure(upload.id, work)
                source = "collector"
                self.keep_clip(upload.id, work)
        except AnalysisError as exc:
            self.failed(upload, now, str(exc))
            return
        finally:
            shutil.rmtree(work, ignore_errors=True)
        category = self.classify(
            {"title": upload.title, "tag": upload.tags, "desc": upload.description}
        )
        added_at = utc(self.clock())
        with self.store.transaction():
            self.store.add_collected(
                upload.id,
                added_at,
                category,
                features,
                self.store.cutoff(),
                {**self.s.provenance, "measured_by": source},
            )
            self.store.set_state(upload.id, "collected", online_at=now)
            self.store.log_attempt(upload.id, now, "collected")
        self.export()
        self.store.set("block_wait", 0)
        log.info("Added %s (%s, %s)", upload.id, category or "no category", upload.title[:60])

    def failed(self, upload: Upload, now: float, message: str) -> None:
        if self.probe_block(upload.id):
            wait = min(
                MAX_BLOCK_WAIT_S, max(BLOCK_WAIT_S, 2 * int(self.store.get("block_wait", "0")))
            )
            if int(self.store.get("block_wait", "0")):  # blocked again right after a wait
                factor = float(self.store.get("pace_factor", "1"))
                self.store.set("pace_factor", max(0.125, factor / 2))
            self.store.set("block_wait", wait)
            self.store.set("blocked_until", now + wait)
            self.store.set("blocked_at", now)
            self.store.log_attempt(upload.id, now, "blocked", message)
            log.warning("YouTube is blocking downloads; waiting %.0f h", wait / 3600)
            return  # the video stays eligible and is tried again
        self.store.set_state(upload.id, "failed", message[-300:])
        self.store.log_attempt(upload.id, now, "failed", message)
        log.warning("Couldn't collect %s: %s", upload.id, message[-200:])

    def keep_clip(self, video_id: str, work: Path) -> None:
        """Keep the clip and its feature cache on the clips volume (plan 013, decision 6)."""
        for name, folder in (
            (f"clips/{video_id}.mp4", "clips"),
            (f"cache/{video_id}.npz", "cache"),
        ):
            source = work / name
            if source.exists():
                (self.s.clips_dir / folder).mkdir(parents=True, exist_ok=True)
                os.replace(source, self.s.clips_dir / folder / source.name)

    def live_result(self, video_id: str) -> dict[str, float | None] | None:
        """Features of the video if a live check already measured it."""
        if self.s.analysis_dir is None:
            return None
        path = self.s.analysis_dir / f"{video_id}.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        features = record.get("features")
        if record.get("status") == "done" and isinstance(features, dict):
            return {k: features.get(k) for k in scoring.FEATURES}
        return None

    def live_running(self) -> bool:
        """A live check waiting or running: it goes first."""
        if self.s.analysis_dir is None or not self.s.analysis_dir.is_dir():
            return False
        for path in self.s.analysis_dir.glob("*.json"):
            with contextlib.suppress(OSError, ValueError):
                if json.loads(path.read_text(encoding="utf-8")).get("status") in LIVE_RUNNING:
                    return True
        return False

    def live_blocked(self, now: float) -> bool:
        """The live analysis saw a block in the last 6 hours."""
        if self.s.analysis_dir is None:
            return False
        try:
            at = float((self.s.analysis_dir / BLOCK_MARKER).read_text().strip())
        except (OSError, ValueError):
            return False
        return now - at < BLOCK_WAIT_S

    def low_on_space(self) -> bool:
        self.s.clips_dir.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.s.clips_dir).free
        if free < FREE_SPACE_MIN:
            log.warning("Paused: %.0f GB free on the clips volume", free / 1024**3)
            return True
        return False

    # --- export ----------------------------------------------------------------------

    def export(self) -> None:
        export(self.store, self.s.data_dir / "collected")


COLUMNS = (
    "video_id", "title", "channel_id", "channel_title", "category", "published_at",
    "duration_s", *scoring.FEATURES, "added_at", "r", "cutoff", "rule_version",
    "measured_by", "ytdlp_version", "ffmpeg_version", "pipeline_commit", "cache_version",
)  # fmt: skip


def export(store: Store, directory: Path) -> None:
    """The added videos (one file per year of adding, in the order added), the removed ones and
    a little metadata, each written whole and renamed into place, for the API to reload."""
    directory.mkdir(parents=True, exist_ok=True)
    by_year: dict[str, list[dict[str, object]]] = {}
    for row in store.collected_rows():
        features = json.loads(row["features"])
        provenance = json.loads(row["provenance"])
        out: dict[str, object] = {
            "video_id": row["video_id"],
            "title": row["title"],
            "channel_id": row["channel_id"],
            "channel_title": row["channel_title"],
            "category": row["category"] or "",
            "published_at": row["published_at"][:10],
            "duration_s": row["duration_s"] if row["duration_s"] is not None else "",
            "added_at": row["added_at"],
            "r": f"{row['r']:.9f}",
            "cutoff": f"{row['cutoff']:.9f}",
            "rule_version": sampling.RULE_VERSION,
        }
        out.update({k: "" if features.get(k) is None else features[k] for k in scoring.FEATURES})
        out.update({k: provenance.get(k, "") for k in COLUMNS if k not in out})
        by_year.setdefault(row["added_at"][:4], []).append(out)
    for year, rows in by_year.items():
        _write_tsv(directory / f"{year}.tsv", COLUMNS, rows)
    removed = [dict(r) for r in store.removed_rows()]
    _write_tsv(directory / "removed.tsv", ("video_id", "removed_at", "reason"), removed)
    _write_tsv(directory / "CHANGELOG.tsv", CHANGELOG_COLUMNS, changelog(store))
    meta = {"channelsCheckedAt": store.get("channels_checked_at") or None}
    _replace(directory / "meta.json", json.dumps(meta) + "\n")


CHANGELOG_COLUMNS = ("date", "added", "removed", "channels_added", "videos", "channels")


def changelog(store: Store) -> list[dict[str, object]]:
    """One line per UTC day with a change: videos added and removed, channels that got their
    first video, and the totals at the end of the day (the release notes read the last line)."""
    channel_of = {
        r["id"]: r["channel_id"]
        for r in store.db.execute(
            "SELECT id, channel_id FROM uploads WHERE state IN ('v2', 'collected', 'removed')"
        )
    }
    collected = {r["video_id"]: r["added_at"] for r in store.db.execute(
        "SELECT video_id, added_at FROM collected")}  # fmt: skip
    events = [(at, "add", vid) for vid, at in collected.items()]
    events += [(r["removed_at"], "remove", r["video_id"]) for r in store.removed_rows()]
    # The reference set: v2's picks, also the ones removed since.
    visible = Counter(channel_of[v] for v in channel_of if v not in collected)
    videos = sum(visible.values())
    channels = len(visible)
    lines: list[dict[str, object]] = []
    for at, kind, video_id in sorted(events):
        day = at[:10]
        if not lines or lines[-1]["date"] != day:
            lines.append(dict.fromkeys(CHANGELOG_COLUMNS, 0) | {"date": day})
        line = lines[-1]
        channel = channel_of.get(video_id, "")
        if kind == "add":
            line["added"] = int(str(line["added"])) + 1
            if visible[channel] == 0:
                line["channels_added"] = int(str(line["channels_added"])) + 1
                channels += 1
            visible[channel] += 1
            videos += 1
        elif visible[channel] > 0:
            line["removed"] = int(str(line["removed"])) + 1
            visible[channel] -= 1
            videos -= 1
            channels -= visible[channel] == 0
        line["videos"] = videos
        line["channels"] = channels
    return lines


def _write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    tmp = path.with_suffix(".tsv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: str(v).replace("\t", " ").replace("\n", " ") for k, v in row.items()}
            )
    os.replace(tmp, path)


def _replace(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# --- provenance and the block probe --------------------------------------------------------


def provenance() -> dict[str, str]:
    """What measured the videos, recorded with each one."""

    def run(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    extract = (PIPELINE_DIR / "04_extract_features_v2.py").read_text(encoding="utf-8")
    cache = re.search(r"^CACHE_VERSION = (\d+)", extract, re.M)
    commit = run(["git", "-C", str(PIPELINE_DIR), "rev-parse", "--short", "HEAD"])
    dirty = run(["git", "-C", str(PIPELINE_DIR), "status", "--porcelain", "--", "."])
    return {
        "ytdlp_version": run([sys.executable, "-m", "yt_dlp", "--version"]),
        "ffmpeg_version": (run(["ffmpeg", "-version"]).split() + ["", "", ""])[2],
        "pipeline_commit": commit + ("+changes" if dirty else ""),
        "cache_version": cache.group(1) if cache else "",
    }


def probe_block(video_id: str) -> bool:
    """Ask yt-dlp once, with its full error text, whether YouTube is blocking us. (The
    download script keeps only the error's last 180 characters, which cut the reason off.)"""
    cmd = [sys.executable, "-m", "yt_dlp", "--simulate", "--no-warnings"]
    cmd += ["--remote-components", "ejs:github", f"https://www.youtube.com/watch?v={video_id}"]
    path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env={**os.environ, "PATH": path}
        )
    except subprocess.TimeoutExpired:
        return False
    return "not a bot" in proc.stderr
