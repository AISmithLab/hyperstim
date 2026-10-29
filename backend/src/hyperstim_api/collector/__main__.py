"""The collector's commands (plan 013). Settings come from environment variables.

python -m hyperstim_api.collector seed <research-repo>   start from v2's lists, once
python -m hyperstim_api.collector run                    collect until stopped
python -m hyperstim_api.collector status                 what it has done, and its health
python -m hyperstim_api.collector export                 write the TSV files again
python -m hyperstim_api.collector alerts                 the hourly alert check (GitHub issues)
"""

import argparse
import logging
import os
import shutil
import signal
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from hyperstim_api import scoring
from hyperstim_api.analysis import ResearchPipeline
from hyperstim_api.collector import alerts, sampling
from hyperstim_api.collector import seed as seeding
from hyperstim_api.collector.collector import (
    RETRY_AFTER_S,
    Collector,
    Settings,
    export,
    load_classifier,
    probe_block,
    provenance,
    scorer,
    utc,
)
from hyperstim_api.collector.store import Store
from hyperstim_api.collector.youtube import DataApi, OutOfUnits, http_get, is_short, quota_day
from hyperstim_api.config import _limit, _required
from hyperstim_api.dataset import load_dataset

log = logging.getLogger("hyperstim_api.collector")


def settings() -> Settings:
    analysis = os.environ.get("ANALYSIS_DIR", "").strip()
    return Settings(
        data_dir=Path(_required("COLLECTOR_DATA_DIR")),
        clips_dir=Path(_required("COLLECTOR_CLIPS_DIR")),
        analysis_dir=Path(analysis) if analysis else None,
        per_day=_limit("COLLECT_PER_DAY", 150),
        units_per_day=_limit("COLLECTOR_UNITS_PER_DAY", 7000),
    )


def open_store(s: Settings) -> Store:
    return Store(s.data_dir / "collector.db")


def run(s: Settings) -> None:
    store = open_store(s)
    if not store.get("seeded"):
        sys.exit("Seed the collector first: python -m hyperstim_api.collector seed <research-repo>")
    s.provenance = provenance()
    # Downloads that failed before they were retried (plan 013, decision 7) get their retries.
    requeued = store.requeue_failed(len(RETRY_AFTER_S) + 1)
    if requeued:
        log.info("Trying %d failed downloads again", requeued)

    def spend(units: int) -> None:
        day = quota_day(time.time())
        if store.units_used(day) + units > s.units_per_day:
            raise OutOfUnits(f"budget of {s.units_per_day} units")
        store.add_units(day, units)

    reference = load_dataset(Path(_required("DATASET_PATH")))
    pipeline = ResearchPipeline(youtube_api_key=None, measure_cores=1)  # no cookies (plan 013)
    collector = Collector(
        s,
        store,
        DataApi(http_get(_required("YOUTUBE_API_KEY")), spend),
        pipeline,
        is_short,
        load_classifier(),
        probe_block,
        score=scorer(reference),
    )
    collector.fill_scores({v.id: v.score for v in reference.videos})
    stop = threading.Event()

    def on_signal(*_: object) -> None:
        stop.set()
        pipeline.cancel()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    collector.export()
    log.info("Collecting %d videos a day into %s", s.per_day, s.data_dir)
    while not stop.is_set():
        try:
            wait = collector.tick()
        except Exception:
            if stop.is_set():
                break
            log.exception("Collector tick failed; trying again in 10 minutes")
            wait = 600
        stop.wait(wait)
    store.close()


def status(s: Settings) -> str:
    store = open_store(s)
    now = time.time()
    states = dict(
        (r["state"], r["n"])
        for r in store.db.execute("SELECT state, COUNT(*) AS n FROM uploads GROUP BY state")
    )
    channels = dict(
        (r["status"], r["n"])
        for r in store.db.execute("SELECT status, COUNT(*) AS n FROM channels GROUP BY status")
    )
    added = [r["added_at"] for r in store.db.execute("SELECT added_at FROM collected")]
    attempts = Counter(
        r["outcome"]
        for r in store.db.execute("SELECT outcome FROM attempts WHERE at >= ?", (now - 86400,))
    )
    lines = [
        f"Channels: {channels.get('in', 0)} in, {channels.get('near_miss', 0)} near misses",
        "Uploads: " + ", ".join(f"{k} {v}" for k, v in sorted(states.items())),
        f"Added: {len(added)} in all, "
        f"{sum(a >= utc(now - 86400) for a in added)} in 24 h, "
        f"{sum(a >= utc(now - 7 * 86400) for a in added)} in 7 days",
        "Last 24 h: " + (", ".join(f"{k} {v}" for k, v in attempts.items()) or "nothing"),
        f"Cut-off: {store.cutoff():.6f}",
        floor_line(store),
        f"First videos today: {store.first_videos_today(now)} of "
        f"{sampling.FIRST_VIDEOS_PER_DAY} channels",
        left_out_line(store),
        f"Data API units today: {store.units_used(quota_day(now))} of {s.units_per_day}",
        f"Pace: {s.per_day}/day x {store.get('pace_factor', '1')}",
    ]
    blocked = float(store.get("blocked_until", "0"))
    if blocked > now:
        lines.append(f"Blocked by YouTube: waiting until {utc(blocked)}")
    paused = float(store.get("paused_until", "0"))
    if paused > now:
        lines.append(f"Paused after failed downloads in a row: until {utc(paused)}")
    retrying = store.retrying(now)
    lines.append(
        f"Failed downloads: {len(retrying)} waiting to be tried again"
        + (f" (next {utc(retrying[0])})" if retrying else "")
        + f", {states.get('failed', 0)} given up"
    )
    lines += health(store, now)
    next_at = float(store.get("next_download_at", "0"))
    lines.append(f"Next download: {utc(max(now, next_at))}")
    if s.clips_dir.exists():
        lines.append(f"Clips volume: {shutil.disk_usage(s.clips_dir).free / 1024**3:.0f} GB free")
    lines.append(f"Channels last fully searched: {store.get('channels_checked_at') or 'not yet'}")
    lines += scores_against_reference(store)
    store.close()
    return "\n".join(lines)


def floor_line(store: Store) -> str:
    """Channels below the floor, the videos they lack, and how many have no upload left to
    check (fewer than `FLOOR` eligible in all, until new ones come out)."""
    below = store.below_floor()
    done = sum(
        store.db.execute(
            "SELECT 1 FROM uploads WHERE channel_id = ? AND state = 'new' "
            "AND published_at >= ? LIMIT 1",
            (r["id"], f"{sampling.FIRST_YEAR}-01-01"),
        ).fetchone()
        is None
        for r in below
    )
    lacking = sum(sampling.FLOOR - r["have"] for r in below)
    line = (
        f"Below the floor of {sampling.FLOOR}: {len(below)} channels lacking {lacking} videos, "
        f"{done} of them with every upload checked"
    )
    levels = store.levels()  # the downloads fill those with 1 to 4 first, by score
    if levels:
        line += "; in the dataset: " + ", ".join(f"{n} with {k}" for k, n in sorted(levels.items()))
    return line


def left_out_line(store: Store) -> str:
    """The channels left out for their kids share at the last export, and their videos."""
    channels, videos = store.db.execute(
        "SELECT (SELECT COUNT(*) FROM left_out), (SELECT COUNT(*) FROM uploads "
        "WHERE state IN ('v2', 'collected') AND channel_id IN (SELECT channel_id FROM left_out))"
    ).fetchone()
    return (
        f"Left out (under {sampling.KIDS_PERCENT_MIN} % made for kids, of "
        f"{sampling.KIDS_ANSWERS_MIN}+ answers): {channels} channels, {videos} of their videos"
    )


def health(store: Store, now: float) -> list[str]:
    """What's waiting after a failure, what was given up, and when each job last worked
    (plan 013, decision 12)."""
    db = store.db

    def count(sql: str, *args: object) -> int:
        return int(db.execute(sql, args).fetchone()[0])

    month = now - 30 * 86400
    lines = [
        "Waiting after a Data API error: "
        f"{count('SELECT COUNT(*) FROM channels WHERE api_failures > 0')} channels' lists, "
        f"{count('SELECT COUNT(*) FROM uploads WHERE api_failures > 0 AND retry_at > ?', now)}"
        " uploads",
        "Asked again (no clear answer yet): "
        f"{count("SELECT COUNT(*) FROM uploads WHERE state = 'new' AND unsure > 0")} uploads, "
        f"{
            count("SELECT COUNT(*) FROM uploads WHERE state IN ('v2', 'collected') AND unsure > 0")
        } dataset videos possibly gone",
        "Given up in 30 days: "
        f"{
            count(
                "SELECT COUNT(*) FROM uploads WHERE state = 'ineligible' AND unsure > 3 "
                'AND COALESCE(checked_at, 0) >= ?',
                month,
            )
        } unclear uploads, "
        f"{
            count(
                "SELECT COUNT(*) FROM uploads WHERE state = 'failed' AND id IN "
                '(SELECT video_id FROM attempts WHERE at >= ?)',
                month,
            )
        } downloads",
        "Waiting for a title, channel name or date: "
        f"{count("SELECT COUNT(*) FROM uploads WHERE state = 'measured'")} measured videos",
        "Channels with uploads still to read: "
        f"{count('SELECT COUNT(*) FROM channels WHERE full_listing IS NOT NULL')}",
    ]
    last = db.execute("SELECT MAX(at) FROM attempts WHERE outcome = 'collected'").fetchone()[0]
    jobs = {
        "download": utc(last) if last else "",
        "upload lists": store.get("ok:refresh_uploads"),
        "offline check": store.get("ok:check_online"),
        "repair": store.get("ok:repair"),
        "backup": store.get("backed_up"),
        "export": store.get("ok:export"),
    }
    lines.append("Last worked: " + ", ".join(f"{k} {v or 'not yet'}" for k, v in jobs.items()))
    if int(store.get("backup_failures", "0")):
        lines.append(f"Backup: failed {store.get('backup_failures')} times in a row")
    if float(store.get("blocked_until", "0")) > now:
        since = float(store.get("blocked_since") or store.get("blocked_at", "0"))
        lines.append(f"Blocked for {(now - since) / 3600:.0f} h (since {utc(since)})")
    return lines


def scores_against_reference(store: Store) -> list[str]:
    """How added videos score against the reference set (plan 013, decision 4), and the share
    of the dataset from the 100 busiest channels."""
    dataset_path = os.environ.get("DATASET_PATH", "").strip()
    if not dataset_path:
        return []
    import json

    reference = load_dataset(Path(dataset_path))
    scores = []
    for row in store.db.execute("SELECT features FROM collected"):
        features = json.loads(row["features"])
        value = scoring.composite(features, reference.pools)
        if value is not None:
            score = scoring.percentile_rank(value, reference.composite_pool)
            if score is not None:
                scores.append(score)
    lines = []
    if scores:
        fifths = Counter(min(4, int(s // 20)) for s in scores)
        shares = " ".join(f"{100 * fifths[i] / len(scores):.0f}%" for i in range(5))
        lines.append(
            f"Added videos' scores: mean {sum(scores) / len(scores):.1f} (reference 50), "
            f"by fifth {shares} (reference 20% each)"
        )
    busiest = [
        r["channel_id"]
        for r in store.db.execute(
            "SELECT channel_id FROM uploads GROUP BY channel_id ORDER BY COUNT(*) DESC LIMIT 100"
        )
    ]
    in_dataset = store.db.execute(
        "SELECT channel_id FROM uploads WHERE state IN ('v2', 'collected')"
    ).fetchall()
    if in_dataset:
        top = sum(r["channel_id"] in set(busiest) for r in in_dataset)
        lines.append(f"Dataset from the 100 busiest channels: {100 * top / len(in_dataset):.0f}%")
    return lines


def check_alerts(s: Settings) -> None:
    """Plan 013, decision 12. Without ALERT_GITHUB_TOKEN, what would be posted is only logged."""
    token = os.environ.get("ALERT_GITHUB_TOKEN", "").strip()
    issues: alerts.Issues = (
        alerts.GitHubIssues(_required("ALERT_REPO"), token) if token else alerts.LogOnly()
    )
    store = open_store(s)
    posts = alerts.check(
        store,
        s.data_dir / "alerts.json",
        issues,
        time.time(),
        os.environ.get("ALERT_DATA_UNIT", "").strip() or None,
    )
    store.close()
    log.info("Alert check: %s", ", ".join(f"{p.action} {p.key}" for p in posts) or "all well")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m hyperstim_api.collector")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_cmd = commands.add_parser("seed", help="start from v2's lists (once)")
    seed_cmd.add_argument("research_repo", type=Path)
    commands.add_parser("run", help="collect until stopped")
    commands.add_parser("status", help="what the collector has done")
    commands.add_parser("export", help="write the TSV files again")
    commands.add_parser("alerts", help="the hourly alert check: open, comment on, close issues")
    args = parser.parse_args()
    s = settings()
    if args.command == "seed":
        store = open_store(s)
        print(seeding.seed(store, args.research_repo, Path(_required("DATASET_PATH"))))
        export(store, s.data_dir / "collected")
        store.close()
    elif args.command == "run":
        run(s)
    elif args.command == "status":
        print(status(s))
    elif args.command == "alerts":
        check_alerts(s)
    else:
        store = open_store(s)
        export(store, s.data_dir / "collected")
        store.close()


if __name__ == "__main__":
    main()
