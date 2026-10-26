"""The collector's commands (plan 013). Settings come from environment variables.

python -m hyperstim_api.collector seed <research-repo>   start from v2's lists, once
python -m hyperstim_api.collector run                    collect until stopped
python -m hyperstim_api.collector status                 what it has done, and its health
python -m hyperstim_api.collector export                 write the TSV files again
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
from hyperstim_api.collector import seed as seeding
from hyperstim_api.collector.collector import (
    Collector,
    Settings,
    export,
    load_classifier,
    probe_block,
    provenance,
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

    def spend(units: int) -> None:
        day = quota_day(time.time())
        if store.units_used(day) + units > s.units_per_day:
            raise OutOfUnits(f"budget of {s.units_per_day} units")
        store.add_units(day, units)

    pipeline = ResearchPipeline(youtube_api_key=None, measure_cores=1)  # no cookies (plan 013)
    collector = Collector(
        s,
        store,
        DataApi(http_get(_required("YOUTUBE_API_KEY")), spend),
        pipeline,
        is_short,
        load_classifier(),
        probe_block,
    )
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
        f"Data API units today: {store.units_used(quota_day(now))} of {s.units_per_day}",
        f"Pace: {s.per_day}/day x {store.get('pace_factor', '1')}",
    ]
    blocked = float(store.get("blocked_until", "0"))
    if blocked > now:
        lines.append(f"Blocked by YouTube: waiting until {utc(blocked)}")
    next_at = float(store.get("next_download_at", "0"))
    lines.append(f"Next download: {utc(max(now, next_at))}")
    if s.clips_dir.exists():
        lines.append(f"Clips volume: {shutil.disk_usage(s.clips_dir).free / 1024**3:.0f} GB free")
    lines.append(f"Channels last fully searched: {store.get('channels_checked_at') or 'not yet'}")
    lines += scores_against_reference(store)
    store.close()
    return "\n".join(lines)


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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m hyperstim_api.collector")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_cmd = commands.add_parser("seed", help="start from v2's lists (once)")
    seed_cmd.add_argument("research_repo", type=Path)
    commands.add_parser("run", help="collect until stopped")
    commands.add_parser("status", help="what the collector has done")
    commands.add_parser("export", help="write the TSV files again")
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
    else:
        store = open_store(s)
        export(store, s.data_dir / "collected")
        store.close()


if __name__ == "__main__":
    main()
