"""The rest of the search after the agent review (PLAN.md, Search, filters 6-7), as one resumable job.

    uv run python 001-variant-pairs/run_reports.py [--jobs 4] [--min-free-gb 6]

Three loops at once, each resuming from what's saved:
- Downloads: both videos of every confident re-skin and re-upload pair (re-skins first), within
  the day's player budget (waits for the next UTC day, or while the collector is blocked); stops
  at the first failed download.
- Overlap (overlap.py): aligns each pair once both videos are in.
- Reports: regroups (report_selection.py) and runs the selected pairs' prepare_pair.py,
  score_pair.py (every 10th pair with --all-signals, to check the signal order) and
  build_report.py, up to --jobs at once, starting a pair only while --min-free-gb of memory is
  free. A pair's report is named <type>-<A>-<B>; each step's time and peak memory go to
  results/search/reports.tsv, and a failed pair is logged and skipped.
Progress: results/search/finish.json (latest) and finish.jsonl (every few minutes).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import import_downloads  # noqa: E402
import overlap  # noqa: E402
import report_selection  # noqa: E402
from search import DB, EXP, OUT, log_event, now  # noqa: E402

import yt  # noqa: E402

LOG = OUT / "reports.tsv"
COLUMNS = "at\tname\tstate\tall_signals\tprepare_s\tscore_s\treport_s\tnote\tprepare_mb\tscore_mb\treport_mb"
STEPS = ("prepare", "score", "report")


def name_of(a: str, b: str, t: str) -> str:
    return f"{t}-{a}-{b}"


def done_names(states=("ok", "failed")) -> set[str]:
    """Reports whose latest state is one of `states` (an aborted run is taken up again)."""
    if not LOG.exists():
        return set()
    last = {}
    for ln in LOG.read_text().splitlines()[1:]:
        f = ln.split("\t")
        last[f[1]] = f[2]
    return {n for n, s in last.items() if s in states}


def write_log(name: str, state: str, all_signals: bool, times: dict[str, float], note: str = "",
              mb: dict[str, float] | None = None) -> None:
    if not LOG.exists():
        LOG.write_text(COLUMNS + "\n")
    elif not LOG.read_text().startswith(COLUMNS):  # the first run's log had no memory columns
        lines = LOG.read_text().splitlines()
        LOG.write_text("\n".join([COLUMNS, *lines[1:]]) + "\n")
    mb = mb or {}
    with LOG.open("a") as f:
        f.write(f"{now()}\t{name}\t{state}\t{int(all_signals)}\t"
                + "\t".join(f"{times.get(k, 0):.0f}" for k in STEPS) + f"\t{note[:300]}\t"
                + "\t".join(f"{mb[k]:.0f}" if k in mb else "" for k in STEPS) + "\n")


def peak_mb(path: Path) -> float | None:
    """The peak memory /usr/bin/time wrote (its last line, in kB)."""
    try:
        return int(path.read_text().split()[-1]) / 1024
    except (OSError, ValueError, IndexError):
        return None


def run_pair(a: str, b: str, t: str, k: int) -> None:
    name = name_of(a, b, t)
    all_signals = k % 10 == 9
    times: dict[str, float] = {}
    mb: dict[str, float] = {}
    py = [sys.executable]
    # "--" ends the options: a video ID can start with "-".
    steps = [("prepare", py + [str(HERE / "prepare_pair.py"), "--name", name, "--", a, b]),
             ("score", py + [str(HERE / "score_pair.py"), "--name", name, "--features",
                             str(ROOT / "cache" / "features" / "pairs" / name)]
              + (["--all-signals"] if all_signals else []) + ["--", a, b]),
             ("report", py + [str(HERE / "build_report.py"), name])]
    write_log(name, "start", all_signals, {})
    for step, cmd in steps:
        t0 = time.time()
        with tempfile.NamedTemporaryFile("r", suffix=".time") as tf:
            res = subprocess.run(["/usr/bin/time", "-f", "%M", "-o", tf.name, *cmd],
                                 capture_output=True, text=True, cwd=ROOT, check=False)
            if (m := peak_mb(Path(tf.name))) is not None:
                mb[step] = m
        times[step] = time.time() - t0
        logf = ROOT / "cache" / "report" / f"{name}.{step}.log"
        logf.parent.mkdir(parents=True, exist_ok=True)
        logf.write_text(res.stdout + "\n" + res.stderr)
        if res.returncode != 0:
            lines = [ln for ln in res.stderr.splitlines() if ln.strip() and not ln.startswith("Command ")]
            err = next((ln for ln in reversed(lines) if "Error" in ln or "error" in ln),
                       lines[-1] if lines else "")
            if res.returncode in (-9, 137) or "signal 9" in res.stderr:
                err = "killed (out of memory?)"
            write_log(name, "failed", all_signals, times, f"{step}: {err}", mb)
            log_event(f"report {name} failed at {step}: {err}")
            return
    write_log(name, "ok", all_signals, times, "", mb)
    log_event(f"report {name} done in {sum(times.values()) / 60:.1f} min, "
              f"peak {max(mb.values(), default=0):.0f} MB")


# --- Downloads and overlap ---------------------------------------------------------------


def needed(con: sqlite3.Connection) -> list[str]:
    """Videos still to download: re-skin pairs' first, then re-upload pairs', strongest pairs first."""
    out = []
    for label in ("re-skin", "re-upload"):
        for a, b in con.execute("SELECT a, b FROM pairs WHERE label = ? AND confidence >= ? "
                                "ORDER BY score DESC", (label, overlap.MIN_CONFIDENCE)):
            out += [v for v in (a, b) if v not in out and not yt.video_path(v).exists()]
    return out


def seconds_to_next_utc_day() -> float:
    t = dt.datetime.now(dt.UTC)
    return (dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(), dt.UTC) - t).total_seconds()


class Downloads(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.state = "running"

    def run(self) -> None:
        con = sqlite3.connect(DB, timeout=120)
        while todo := needed(con):
            v = todo[0]
            try:
                yt.download(v, EXP, "search: download")
                log_event(f"download {v}: ok")
            except yt.BudgetError as e:
                msg = str(e)
                if "player budget" in msg:
                    self.state = f"waiting for the next UTC day ({msg})"
                    time.sleep(seconds_to_next_utc_day() + random.uniform(60, 600))
                elif "blocked by YouTube" in msg:
                    self.state = f"waiting: {msg}"
                    time.sleep(600)
                else:
                    self.state = f"stopped: {v}: {msg}"
                    log_event(f"downloads stopped: {self.state}")
                    return
                self.state = "running"
                continue
            except Exception as e:  # stop at the first failed download (PLAN.md, Constraints)
                self.state = f"stopped: {v}: {e}"
                log_event(f"downloads stopped: {self.state}")
                return
        self.state = "done"


class Imports(threading.Thread):
    """Videos downloaded on another machine (import_downloads.py): keeps its todo list current."""

    def __init__(self):
        super().__init__(daemon=True)

    def run(self) -> None:
        con = sqlite3.connect(DB, timeout=120)
        while True:
            import_downloads.write_todo(needed(con))
            import_downloads.run_once()
            time.sleep(30)


class Overlaps(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.busy = False

    def run(self) -> None:
        con = overlap.connect()
        while True:
            self.busy = True
            n = overlap.run(con)
            self.busy = False
            if n:
                log_event(f"overlap: {n} pairs aligned")
            time.sleep(60)


# --- Reports ------------------------------------------------------------------------------


def mem_free_gb() -> float:
    for ln in Path("/proc/meminfo").read_text().splitlines():
        if ln.startswith("MemAvailable:"):
            return int(ln.split()[1]) / 1024 ** 2
    return 0.0


def latest_states() -> dict[str, list[str]]:
    if not LOG.exists():
        return {}
    last = {}
    for ln in LOG.read_text().splitlines()[1:]:
        f = ln.split("\t")
        last[f[1]] = f
    return last


def stage(name: str, done: int, of: int, passed: int | None = None, note: str = "") -> dict:
    """One filter's row: done of the items that reached it, and how many it passed on."""
    row = {"stage": name, "done": done, "of": of, "pct_done": round(100 * done / of, 1) if of else 100.0}
    if passed is not None:
        row |= {"passed": passed, "pct_passed": round(100 * passed / done, 1) if done else 0.0}
    return row | ({"note": note} if note else {})


def stages(con: sqlite3.Connection, sel: list[dict], last: dict[str, list[str]], running: int) -> list[dict]:
    """Every filter as done / reached and passed / done. Filters 0-5 come from the search's final
    progress.json (search.py has finished); 6-7 from now."""
    pr = json.loads((OUT / "progress.json").read_text())
    tot = lambda d: sum(d.values())  # noqa: E731 - pair-type dicts
    inv, img, cand, sc, gate, rev = (
        pr[k] for k in ("inventory", "images", "candidates", "score", "gate", "review"))
    audit = con.execute(
        "SELECT count(*) FROM pairs WHERE gate_state = 'stop' AND label IS NOT NULL").fetchone()[0]
    labelled = tot(rev["labelled"])
    unrelated = sum(n for k, n in rev["labels"].items() if k.endswith("|unrelated"))
    vids = {v for a, b in con.execute("SELECT a, b FROM pairs WHERE label IN ('re-skin', 're-upload') "
                                      "AND confidence >= ?", (overlap.MIN_CONFIDENCE,)) for v in (a, b)}
    have = {v for v in vids if yt.video_path(v).exists()}
    n_pairs = con.execute("SELECT count(*) FROM pairs WHERE label IN ('re-skin', 're-upload') "
                          "AND confidence >= ?", (overlap.MIN_CONFIDENCE,)).fetchone()[0]
    ov = con.execute("SELECT count(*), sum(share >= ?) FROM overlap", (overlap.MIN_SHARE,)).fetchone()
    names = [name_of(p["a"], p["b"], p["type"]) for p in sel]
    st = [last.get(n, [""] * 3)[2] for n in names]
    return [
        stage("0 inventory", inv["videos"], inv["videos"], inv["eligible"], "passed = not compilations"),
        stage("1 images", img["videos_done"], img["videos_total"], img["videos_done"]),
        stage("2 candidates", tot(cand["pairs_compared"]), tot(cand["pairs_total"]), tot(cand["passed"])),
        stage("3 score", tot(sc["in"]), tot(sc["in"]), tot(sc["passed"])),
        stage("4 gate", tot(gate["passed"]) + tot(gate["stopped"]), tot(gate["in"]), tot(gate["passed"]),
              f"+{audit} stopped pairs reviewed as an audit"),
        stage("5 review", labelled, labelled + tot(rev["queued"]), labelled - unrelated,
              "passed = any label but unrelated"),
        stage("6 download", len(have), len(vids), None, "videos of confident re-skin and re-upload pairs"),
        stage("6b overlap", ov[0], n_pairs, ov[1] or 0, "pairs; passed = at least half of the shorter video"),
        stage("7 reports", st.count("ok") + st.count("failed"), len(names), st.count("ok"),
              f"{running} running"),
    ]


def stage_table(rows: list[dict]) -> str:
    out = [f"{'stage':14} {'done / reached':>22} {'%':>6} {'passed':>10} {'pass %':>7}"]
    for r in rows:
        p = f"{r['passed']:>10,} {r['pct_passed']:>6.1f}%" if "passed" in r else ""
        out.append(f"{r['stage']:14} {r['done']:>10,} / {r['of']:<10,} {r['pct_done']:>5.1f}% {p}".rstrip()
                   + (f"   {r['note']}" if r.get("note") else ""))
    return "\n".join(out) + "\n"


def progress(dl: Downloads, ov: Overlaps, sel: list[dict], running: dict, t0: float, jobs: int) -> dict:
    con = sqlite3.connect(DB, timeout=120)
    need = needed(con)
    ov_rows = con.execute("SELECT share FROM overlap").fetchall()
    groups = json.loads((OUT / "groups.json").read_text()) if (OUT / "groups.json").exists() else {}
    last = latest_states()
    names = [name_of(p["a"], p["b"], p["type"]) for p in sel]
    states = [last.get(n, [""] * 3)[2] for n in names]
    ok = [last[n] for n in names if n in last and last[n][2] == "ok"]
    mins = [sum(float(x or 0) for x in f[4:7]) / 60 for f in last.values() if f[2] == "ok"]
    mean = sum(mins) / len(mins) if mins else 13.0
    left = len(names) - len(ok)
    return {
        "stages": stages(con, sel, last, len(running)),
        "at": now(), "elapsed_h": round((time.time() - t0) / 3600, 2),
        "mem_free_gb": round(mem_free_gb(), 1),
        "downloads": {"state": dl.state, "videos_left": len(need),
                      "player_used_today": yt.player_used_today(),
                      "player_per_day": yt.PLAYER_PER_DAY},
        "overlap": {"aligned": len(ov_rows), "pass": sum(1 for (s,) in ov_rows if s >= overlap.MIN_SHARE),
                    "busy": ov.busy},
        "groups": {k: {"groups": len(g["groups"]), "videos": sum(len(x["videos"]) for x in g["groups"]),
                       "little_shared": len(g["little_shared"]), "waiting": len(g["waiting"])}
                   for k, g in groups.items()},
        "reports": {"selected": len(names), "ok": len(ok), "failed": states.count("failed"),
                    "running": sorted(running), "mean_min": round(mean, 1),
                    "eta_h_if_videos_in": round(left * mean / 60 / jobs, 1)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-download", action="store_true",
                    help="no downloads here (after a failed one, or when another machine downloads)")
    ap.add_argument("--min-free-gb", type=float, default=6.0,
                    help="start a pair only while this much is free")
    ap.add_argument("--status", action="store_true", help="print each stage from finish.json and exit")
    args = ap.parse_args()
    if args.status:
        pr = json.loads((OUT / "finish.json").read_text())
        print(pr["at"])
        print(stage_table(pr["stages"]), end="")
        return
    # A "start" left by a stopped run is run again; ok and failed pairs are not.
    done = done_names(("ok", "failed"))
    k = len(done)
    dl, ov, im = Downloads(), Overlaps(), Imports()
    if args.no_download:
        dl.state = "off here (another machine downloads)"
    else:
        dl.start()
    ov.start()
    im.start()
    t0, last_progress = time.time(), 0.0
    running: dict[str, object] = {}
    with ThreadPoolExecutor(args.jobs) as pool:
        while True:
            running = {n: f for n, f in running.items() if not f.done()}
            groups, sel = report_selection.build(overlap.connect())
            (OUT / "groups.json").write_text(json.dumps(groups, indent=1))
            (OUT / "report_selection.json").write_text(json.dumps(sel, indent=1))
            # Groups settle once every downloaded pair is aligned: until then the selection can change.
            for p in [] if overlap.todo(overlap.connect(), ("re-skin",)) else sel:
                name = name_of(p["a"], p["b"], p["type"])
                if len(running) >= args.jobs or mem_free_gb() < args.min_free_gb:
                    break
                if name in done or name in running:
                    continue
                if not (yt.video_path(p["a"]).exists() and yt.video_path(p["b"]).exists()):
                    continue
                running[name] = pool.submit(run_pair, p["a"], p["b"], p["type"], k)
                done.add(name)
                k += 1
                time.sleep(20)  # let its memory show before the next check
            if time.time() - last_progress > 60:
                pr = progress(dl, ov, sel, running, t0, args.jobs)
                (OUT / "finish.json").write_text(json.dumps(pr, indent=1))
                (OUT / "status.txt").write_text(f"updated {pr['at']}\n" + stage_table(pr["stages"]))
                with (OUT / "finish.jsonl").open("a") as f:
                    f.write(json.dumps(pr) + "\n")
                last_progress = time.time()
            if dl.state != "running" and not dl.state.startswith("waiting") and not ov.busy and not running \
                    and not overlap.todo(overlap.connect()) and all(
                        name_of(p["a"], p["b"], p["type"]) in done for p in sel
                        if yt.video_path(p["a"]).exists() and yt.video_path(p["b"]).exists()):
                pr = progress(dl, ov, sel, running, t0, args.jobs)
                (OUT / "finish.json").write_text(json.dumps(pr, indent=1))
                log_event("run_reports: all done")
                return
            time.sleep(30)


if __name__ == "__main__":
    main()
