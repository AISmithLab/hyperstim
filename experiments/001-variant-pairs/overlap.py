"""Filter 6b of the search (PLAN.md, Search): does the pair's main content overlap?

    uv run python 001-variant-pairs/overlap.py

Aligns each downloaded pair labelled re-skin or re-upload (confidence ≥ 0.7): by the audio, and
by the frames (DINOv2 at 2 fps) when the audio covers less than half of the shorter video, since a
re-skin may have new audio. The pair's share is the larger of the two; it passes at MIN_SHARE.
Saves each pair in search.db's `overlap` table and results/search/overlap.tsv. `align_pair` is
also how prepare_pair.py and score_pair.py align a pair.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

from search import DB, OUT, log_event, now  # noqa: E402

import align  # noqa: E402
import media  # noqa: E402
import visual as vis  # noqa: E402
import yt  # noqa: E402

MIN_SHARE = 0.5   # of the shorter video
LABELS = ("re-skin", "re-upload")
MIN_CONFIDENCE = 0.7
RATE = 2.0
LOG = OUT / "overlap.tsv"


def shared_s(segs: list[align.Segment], on_b: bool = False) -> float:
    """Seconds of one video the segments cover (A's clock, or B's when `on_b`), each second once:
    a compilation that plays the other video's song three times still covers that song once."""
    spans = sorted((s.a0 + s.lag, s.a1 + s.lag) if on_b else (s.a0, s.a1) for s in segs)
    total, end = 0.0, float("-inf")
    for lo, hi in spans:
        lo = max(lo, end)
        if hi > lo:
            total += hi - lo
            end = hi
    return total


def embed_frames(p: Path) -> np.ndarray:
    """A video's frame embeddings for the frame alignment (DINOv2, RATE a second, 224 × 126)."""
    return vis.embed(list(media.frames(p, (224, 126), fps=RATE)), size=(224, 126))


def align_pair(pa: Path, pb: Path, ya, yb, embed=embed_frames) -> dict:
    """Audio segments, or the frames' segment when the audio covers under MIN_SHARE and the frames
    match over more of the shorter video. `embed` gives a video's frame embeddings (gate_check.py
    passes a cached one)."""
    dur_a, dur_b = len(ya) / align.SR, len(yb) / align.SR
    short = min(dur_a, dur_b) or 1.0
    segs, curves = align.segments(ya, yb)
    out = {"segs": segs, "curves": curves, "source": "audio",
           "audio_share": shared_s(segs, dur_b < dur_a) / short, "frame_share": None}
    if out["audio_share"] < MIN_SHARE:
        ea, eb = embed(pa), embed(pb)
        seg = vis.frame_alignment(ea, eb, RATE, dur_a, dur_b)
        if seg is not None:
            out["frame_share"] = min(1.0, vis.frame_overlap(ea, eb, RATE, seg) / short)
            if out["frame_share"] > out["audio_share"]:
                out["segs"], out["source"] = [seg], "frames"
    out["share"] = max(out["audio_share"], out["frame_share"] or 0.0)
    out["dur_a"], out["dur_b"] = dur_a, dur_b
    return out


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=120)
    con.execute("CREATE TABLE IF NOT EXISTS overlap (a TEXT, b TEXT, source TEXT, audio_share REAL, "
                "frame_share REAL, share REAL, lag REAL, dur_a REAL, dur_b REAL, at TEXT, "
                "PRIMARY KEY (a, b))")
    return con


def todo(con: sqlite3.Connection, labels: tuple[str, ...] = LABELS) -> list[tuple[str, str, str]]:
    """Pairs to align, re-skins first: both videos in, not aligned yet."""
    rows = con.execute(
        f"SELECT a, b, type FROM pairs WHERE label IN ({','.join('?' * len(labels))}) AND confidence >= ? "
        "AND NOT EXISTS (SELECT 1 FROM overlap o WHERE o.a = pairs.a AND o.b = pairs.b) "
        "ORDER BY label = 're-skin' DESC, score DESC",
        (*labels, MIN_CONFIDENCE)).fetchall()
    return [r for r in rows if yt.video_path(r[0]).exists() and yt.video_path(r[1]).exists()]


def run(con: sqlite3.Connection) -> int:
    """Aligns every pair that's ready; returns how many."""
    n = 0
    for a, b, t in todo(con):
        pa, pb = yt.video_path(a), yt.video_path(b)
        try:
            r = align_pair(pa, pb, media.audio(pa), media.audio(pb))
        except Exception as e:  # a broken download: logged, and the pair stays out
            log_event(f"overlap {t}-{a}-{b} failed: {e}")
            continue
        lag = r["segs"][0].lag if r["segs"] else None
        con.execute("INSERT OR REPLACE INTO overlap VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a, b, r["source"], r["audio_share"], r["frame_share"], r["share"], lag,
                     r["dur_a"], r["dur_b"], now()))
        con.commit()
        new = not LOG.exists()
        with LOG.open("a") as f:
            if new:
                f.write("at\tname\tsource\taudio_share\tframe_share\tshare\tpasses\n")
            fs = "" if r["frame_share"] is None else f"{r['frame_share']:.3f}"
            f.write(f"{now()}\t{t}-{a}-{b}\t{r['source']}\t{r['audio_share']:.3f}\t{fs}\t{r['share']:.3f}\t"
                    f"{int(r['share'] >= MIN_SHARE)}\n")
        n += 1
    return n


if __name__ == "__main__":
    print(f"{run(connect())} pairs aligned")
