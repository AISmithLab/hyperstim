"""Filter 5 of the search (PLAN.md, Search): review sheets for gated pairs, for the agent.

    uv run python 001-variant-pairs/review.py next [--n 10]   # next batch: sheet + pair data
    uv run python 001-variant-pairs/review.py check FILE       # validate a labels file

`next` takes the strongest unreviewed gated pairs (then audit pairs), marks them sent, and
writes cache/search/review/batch-NNN.jpg (one row per pair: A's thumbnail and auto-frames at
1/4, 1/2, 3/4, then B's) and batch-NNN.json (titles, durations, dates, signals). The agent
writes results/search/labels/batch-NNN.json: [{"a", "b", "label", "confidence", "note"}], label
one of LABELS; search.py reads it within a minute.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

from search import DB, IMG_URL, OUT, crop_bars  # noqa: E402

import visual as vis  # noqa: E402
import yt  # noqa: E402

LABELS = ("re-upload", "re-skin", "same-song", "same-template", "shared-segments", "unrelated")
TILE = (240, 135)
HUB_LABELLED = 5
REVIEW = ROOT / "cache" / "search" / "review"


def image_path(v: str, kind: str) -> Path | None:
    import hashlib

    url = f"https://i.ytimg.com/vi/{v}/{IMG_URL[kind]}.jpg"
    p = ROOT / "cache" / "img" / f"{v}-{hashlib.sha1(url.encode()).hexdigest()[:12]}.jpg"
    return p if p.exists() else None


def tile(v: str, kind: str) -> np.ndarray:
    p = image_path(v, kind)
    if p is None:
        return np.full((TILE[1], TILE[0], 3), 40, np.uint8)
    return cv2.resize(crop_bars(vis.load_image(p)), TILE, interpolation=cv2.INTER_AREA)


def aligned_times(dur_a: float, dur_b: float, lag: float, n: int = 4) -> list[tuple[float, float]]:
    """n moments spread over the part both videos cover once B is shifted by `lag` (B time = A time
    + lag): (A time, B time) pairs at 1/(n+1) ... n/(n+1) of it."""
    lo, hi = max(0.0, -lag), min(dur_a, dur_b - lag)
    if hi <= lo:
        return []
    return [(lo + (hi - lo) * i / (n + 1), lo + (hi - lo) * i / (n + 1) + lag) for i in range(1, n + 1)]


def frame_at(p: Path, t: float) -> np.ndarray:
    """One frame of a downloaded video at t seconds, as a sheet tile."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
                          "-vf", f"scale={TILE[0]}:{TILE[1]}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    if len(raw) != TILE[0] * TILE[1] * 3:
        return np.full((TILE[1], TILE[0], 3), 40, np.uint8)
    return np.frombuffer(raw, np.uint8).reshape(TILE[1], TILE[0], 3)


def _text(img: np.ndarray, s: str, x: int) -> None:
    cv2.putText(img, s, (x, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def sheet(pairs: list[tuple[str, str]], out: Path, aligned: dict | None = None) -> None:
    """One row per pair from YouTube's images; with `aligned` ({(a, b): [(ta, tb), ...]}), a second
    row of frames from the downloaded videos at matching moments."""
    rows = []
    gap = np.full((TILE[1], 12, 3), 255, np.uint8)
    for k, (a, b) in enumerate(pairs, 1):
        tiles = [tile(a, x) for x in ("thumb", "hq1", "hq2", "hq3")] + \
                [tile(b, x) for x in ("thumb", "hq1", "hq2", "hq3")]
        row = np.hstack(tiles[:4] + [gap] + tiles[4:])
        head = np.full((22, row.shape[1], 3), 255, np.uint8)
        _text(head, f"pair {k}:  A = {a}  (thumb, 1/4, 1/2, 3/4)", 6)
        _text(head, f"B = {b}", 4 * TILE[0] + 18)
        rows += [head, row]
        times = (aligned or {}).get((a, b))
        if times:
            pa, pb = yt.video_path(a), yt.video_path(b)
            row2 = np.hstack([frame_at(pa, ta) for ta, _ in times] + [gap]
                             + [frame_at(pb, tb) for _, tb in times])
            head2 = np.full((22, row.shape[1], 3), 230, np.uint8)
            _text(head2, f"pair {k} matched moments, A at {', '.join(_mmss(ta) for ta, _ in times)}", 6)
            _text(head2, f"B at {', '.join(_mmss(tb) for _, tb in times)}", 4 * TILE[0] + 18)
            rows += [head2, row2]
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])


def overlap_of(con: sqlite3.Connection, a: str, b: str) -> dict | None:
    """The pair's frame-by-frame check (gate_check.py), if it had one."""
    try:
        r = con.execute("SELECT source, share, long_share, lag, dur_a, dur_b FROM gate_check "
                        "WHERE a = ? AND b = ? AND error IS NULL", (a, b)).fetchone()
    except sqlite3.OperationalError:   # no gate_check table yet
        return None
    if not r:
        return None
    return {"source": r[0], "share_of_shorter": round(r[1], 3), "share_of_longer": round(r[2], 3),
            "lag_s": None if r[3] is None else round(r[3], 2), "dur_a": r[4], "dur_b": r[5]}


def next_batch(n: int) -> None:
    con = sqlite3.connect(DB, timeout=120, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    # Hub videos (a series episode that matches every other episode) go last: a video already in
    # HUB_LABELLED pairs labelled same-template or shared-segments adds little but review time.
    hubs = Counter()
    for a, b in con.execute("SELECT a, b FROM pairs WHERE label IN ('same-template', 'shared-segments')"):
        hubs.update((a, b))
    q = ("SELECT a, b, type, score, sims, cand_fired, gate, gate_fired, review FROM pairs "
         "WHERE review = ? ORDER BY score DESC")
    queued = con.execute(q, ("queue",)).fetchall()
    queued.sort(key=lambda r: max(hubs[r[0]], hubs[r[1]]) >= HUB_LABELLED)  # stable: score order kept
    rows = queued[:n]
    if len(rows) < n:
        rows += con.execute(q, ("audit",)).fetchall()[:n - len(rows)]
    if not rows:
        con.execute("COMMIT")
        print("nothing to review")
        return
    con.executemany("UPDATE pairs SET review = 'sent' WHERE a = ? AND b = ?", [(r[0], r[1]) for r in rows])
    con.execute("COMMIT")
    REVIEW.mkdir(parents=True, exist_ok=True)
    k = 1 + max([int(p.stem.split("-")[1]) for p in REVIEW.glob("batch-*.json")], default=0)
    while True:  # claim the number: parallel reviewers never share a batch
        try:
            (REVIEW / f"batch-{k:03d}.json").open("x").close()
            break
        except FileExistsError:
            k += 1
    name = f"batch-{k:03d}"
    vids = {}
    for v in {x for r in rows for x in r[:2]}:
        t, pub, dur, views, side = con.execute(
            "SELECT title, published, duration, views, side FROM videos WHERE id = ?", (v,)).fetchone()
        vids[v] = {"title": t, "published": pub, "duration_s": dur, "views": views,
                   "channel": "Kids TV" if side == "A" else "Kids Channel"}
    data = {"batch": name, "labels": LABELS, "pairs": []}
    aligned = {}
    for i, (a, b, t, score, sims, cand, gate, gate_fired, review) in enumerate(rows, 1):
        item = {"n": i, "a": a, "b": b, "type": t, "score": round(score, 2),
                "signals": json.loads(sims), "candidate_fired": cand,
                "gate": json.loads(gate or "{}"), "gate_fired": gate_fired,
                "audit": review == "audit", "video_a": vids[a], "video_b": vids[b]}
        o = overlap_of(con, a, b)
        if o:
            item["overlap"] = {k: o[k] for k in ("source", "share_of_shorter", "share_of_longer", "lag_s")}
            if o["lag_s"] is not None and yt.video_path(a).exists() and yt.video_path(b).exists():
                aligned[(a, b)] = aligned_times(o["dur_a"], o["dur_b"], o["lag_s"])
        data["pairs"].append(item)
    sheet([(r[0], r[1]) for r in rows], REVIEW / f"{name}.jpg", aligned)
    (REVIEW / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(REVIEW / f"{name}.jpg")
    print(REVIEW / f"{name}.json")


def check(path: Path) -> None:
    data = json.loads(path.read_text())
    for it in data:
        assert it["label"] in LABELS, it
        assert 0 <= float(it["confidence"]) <= 1, it
        assert it["a"] and it["b"], it
    print(f"ok: {len(data)} labels")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("--n", type=int, default=10)
    c = sub.add_parser("check")
    c.add_argument("file", type=Path)
    a = ap.parse_args()
    if a.cmd == "next":
        next_batch(a.n)
    else:
        check(a.file)
    (OUT / "labels").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
