"""The gate's stopped pairs, checked frame by frame (PLAN.md, Search, filter 4: gate misses).

    uv run python 001-variant-pairs/gate_check.py --worker 0 --workers 3    # one of 3 processes
    uv run python 001-variant-pairs/gate_check.py --feed                    # todo list, imports, status
    uv run python 001-variant-pairs/gate_check.py --status                  # print the stage table

The gate (filter 4) judged pairs from YouTube's images alone, and stopped 3,978 of them; its audit
found a re-skin among them. Here every stopped pair the agent hasn't labelled gets the overlap
check that labelled pairs get (overlap.py's align_pair: audio, then frames), on the downloaded
videos. The feed process keeps cache/remote/todo.txt filled with the videos still needed (pairs with the
highest screen score first) for remote_download.py, and imports what arrives. Every worker
computes the frame embeddings of its share of the videos once (cache/features/emb/<id>.npy) and
checks its share of the pairs as soon as both videos are in. Results go to search.db's
`gate_check` table and results/search/gate_check.tsv; the feed writes the stage table to
results/search/gate_check.json and gate_check_status.txt every minute. Pairs that pass (at least
half of each video shared) go to the agent next, to tell re-skins from re-uploads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import import_downloads  # noqa: E402
import overlap  # noqa: E402
from report_selection import long_share  # noqa: E402
from search import DB, OUT, log_event, now  # noqa: E402

import media  # noqa: E402
import yt  # noqa: E402

EMB = ROOT / "cache" / "features" / "emb"
LOG = OUT / "gate_check.tsv"
STATUS = OUT / "gate_check.json"
STATUS_TXT = OUT / "gate_check_status.txt"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=120)
    con.execute("CREATE TABLE IF NOT EXISTS gate_check (a TEXT, b TEXT, source TEXT, audio_share REAL, "
                "frame_share REAL, share REAL, long_share REAL, lag REAL, dur_a REAL, dur_b REAL, "
                "error TEXT, at TEXT, PRIMARY KEY (a, b))")
    return con


def stopped(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """The gate's stopped pairs the agent hasn't labelled, highest screen score first. Live streams
    (duration 0) are left out: there is no fixed video to download."""
    return con.execute("SELECT a, b, type FROM pairs p WHERE gate_state = 'stop' AND label IS NULL "
                       "AND NOT EXISTS (SELECT 1 FROM videos v WHERE v.id IN (p.a, p.b) AND v.duration = 0) "
                       "ORDER BY score DESC").fetchall()


def needed(pairs: list[tuple[str, str, str]]) -> list[str]:
    """Videos still to download, in the pairs' order."""
    out, seen = [], set()
    for a, b, _ in pairs:
        for v in (a, b):
            if v not in seen:
                seen.add(v)
                if not yt.video_path(v).exists():
                    out.append(v)
    return out


def mine(key: str, worker: int, workers: int) -> bool:
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % workers == worker


def emb_path(v: str) -> Path:
    return EMB / f"{v}.npy"


def cached_embed(p: Path) -> np.ndarray:
    """The video's frame embeddings, computed once."""
    f = emb_path(p.stem)
    if f.exists():
        return np.load(f)
    e = overlap.embed_frames(p).astype(np.float32)
    EMB.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp.npy")
    np.save(tmp, e)
    tmp.replace(f)
    return e


def check(con: sqlite3.Connection, a: str, b: str, t: str) -> dict:
    pa, pb = yt.video_path(a), yt.video_path(b)
    try:
        r = overlap.align_pair(pa, pb, media.audio(pa), media.audio(pb), embed=cached_embed)
    except Exception as e:  # a broken download: logged, the pair stays unchecked-with-error
        con.execute("INSERT OR REPLACE INTO gate_check (a, b, error, at) VALUES (?,?,?,?)",
                    (a, b, str(e), now()))
        con.commit()
        log_event(f"gate check {t}-{a}-{b} failed: {e}")
        return {}
    r["long_share"] = long_share(r)
    lag = r["segs"][0].lag if r["segs"] else None
    con.execute("INSERT OR REPLACE INTO gate_check VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (a, b, r["source"], r["audio_share"], r["frame_share"], r["share"], r["long_share"], lag,
                 r["dur_a"], r["dur_b"], None, now()))
    con.commit()
    passes = r["share"] >= overlap.MIN_SHARE and (r["long_share"] or 0) >= overlap.MIN_SHARE
    new = not LOG.exists()
    with LOG.open("a") as f:
        if new:
            f.write("at\tname\tsource\taudio_share\tframe_share\tshare\tlong_share\tpasses\n")
        fs = "" if r["frame_share"] is None else f"{r['frame_share']:.3f}"
        f.write(f"{now()}\t{t}-{a}-{b}\t{r['source']}\t{r['audio_share']:.3f}\t{fs}\t{r['share']:.3f}\t"
                f"{r['long_share']:.3f}\t{int(passes)}\n")
    return r


def stages(con: sqlite3.Connection, pairs: list, todo: list[str]) -> dict:
    """x / y for each stage: downloads, embeddings, pairs ready, pairs checked, pairs passing."""
    vids = {v for a, b, _ in pairs for v in (a, b)}
    have = {v for v in vids if yt.video_path(v).exists()}
    embedded = {v for v in have if emb_path(v).exists()}
    done = {(a, b): (s, ls, err) for a, b, s, ls, err in con.execute(
        "SELECT a, b, share, long_share, error FROM gate_check")}
    ready = [(a, b) for a, b, _ in pairs if a in have and b in have]
    checked = [p for p in ready if p in done and done[p][2] is None]
    passing = [p for p in checked if (done[p][0] or 0) >= overlap.MIN_SHARE
               and (done[p][1] or 0) >= overlap.MIN_SHARE]
    errors = [p for p in ready if p in done and done[p][2] is not None]

    def row(x, y):
        return {"done": x, "of": y, "pct": round(100 * x / y, 1) if y else None}

    return {"at": now(), "stages": {
        "downloaded": row(len(have), len(vids)),
        "embedded": row(len(embedded), len(vids)),
        "pairs_ready": row(len(ready), len(pairs)),
        "pairs_checked": row(len(checked), len(ready)),
        "pairs_passing": row(len(passing), len(checked)),
    }, "errors": len(errors), "todo_for_laptop": len(todo)}


def write_status(st: dict) -> None:
    STATUS.write_text(json.dumps(st, indent=1))
    names = {"downloaded": "Videos downloaded", "embedded": "Videos with frame data",
             "pairs_ready": "Pairs with both videos", "pairs_checked": "Pairs checked",
             "pairs_passing": "Pairs passing (≥ half of each)"}
    lines = [f"Gate check, {st['at']}"]
    for k, r in st["stages"].items():
        pct = "–" if r["pct"] is None else f"{r['pct']:.1f}%"
        lines.append(f"  {names[k]:<32} {r['done']:>6} / {r['of']:<6} {pct:>7}")
    lines.append(f"  errors {st['errors']}; laptop todo {st['todo_for_laptop']}")
    STATUS_TXT.write_text("\n".join(lines) + "\n")


def step(con: sqlite3.Connection, pairs: list, worker: int, workers: int, failed: set) -> tuple[int, int]:
    """One video's frame embeddings, then up to 3 ready pairs: the two take turns, so the checks keep
    going while new videos keep arriving. Returns (videos left to embed, pairs ready) before the step."""
    vids = dict.fromkeys(v for a, b, _ in pairs for v in (a, b))
    left = [v for v in vids if mine(v, worker, workers) and v not in failed and yt.video_path(v).exists()
            and not emb_path(v).exists()]
    if left:
        try:
            cached_embed(yt.video_path(left[0]))
        except Exception as e:  # noqa: BLE001 - an unreadable video: its pairs stay unchecked
            failed.add(left[0])
            log_event(f"gate check: embedding {left[0]} failed: {e}")
    done = {(a, b) for a, b in con.execute("SELECT a, b FROM gate_check")}
    ready = [(a, b, t) for a, b, t in pairs if (a, b) not in done and mine(a + b, worker, workers)
             and emb_path(a).exists() and emb_path(b).exists()]
    for a, b, t in ready[:3]:
        check(con, a, b, t)
    return len(left), len(ready)


def finished(st: dict) -> bool:
    """Every video in, and every pair checked (or failed)."""
    s = st["stages"]
    return st["todo_for_laptop"] == 0 and s["pairs_checked"]["done"] + st["errors"] >= s["pairs_ready"]["of"]


def feed() -> None:
    """Keeps the laptop's todo list, the imports and the stage table current, every 20 s, in its own
    process: a worker's step can take minutes, and the inbox shouldn't wait for it."""
    con = connect()
    while True:
        pairs = stopped(con)
        todo = needed(pairs)
        import_downloads.write_todo(todo)
        import_downloads.run_once()
        st = stages(con, pairs, todo)
        write_status(st)
        if finished(st):
            log_event("gate check feed: done")
            return
        time.sleep(20)


def run(worker: int, workers: int) -> None:
    con = connect()
    failed = set()   # videos whose embedding failed: not tried again this run
    while True:
        pairs = stopped(con)
        left, ready = step(con, pairs, worker, workers, failed)
        if not left and not ready:
            if not needed(pairs):
                log_event(f"gate check worker {worker}: done")
                return
            time.sleep(20)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--status", action="store_true", help="print the stage table and exit")
    ap.add_argument("--feed", action="store_true", help="keep the todo list, imports and stage table current")
    args = ap.parse_args()
    if args.status:
        con = connect()
        pairs = stopped(con)
        write_status(stages(con, pairs, needed(pairs)))
        print(STATUS_TXT.read_text(), end="")
        return
    if args.feed:
        feed()
        return
    run(args.worker, args.workers)


if __name__ == "__main__":
    main()
