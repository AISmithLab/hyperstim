"""Pipeline features for every downloaded group video that has none yet (for the group tables).

    uv run python 001-variant-pairs/video_features.py

A video's features come from the dataset, or from a full report's features.tsv
(cache/features/pairs/*/). For the rest (mostly re-uploads, which get no report), this cuts the
same dataset-style clip as prepare_pair.py (from 0:30, up to 5 min) and runs the backend
pipeline's extract/derive on all of them at once into cache/features/videos/features.tsv.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

from prepare_pair import CLIP_LEN, CLIP_START, cut, pipeline  # noqa: E402
from search import DB  # noqa: E402

import baselines as bl  # noqa: E402
import media  # noqa: E402
import yt  # noqa: E402

OUT = ROOT / "cache" / "features" / "videos" / "features.tsv"


def measured() -> set[str]:
    """Videos that already have features: the dataset's and the full reports'."""
    have = set(bl.load_dataset())
    for p in [*(ROOT / "cache" / "features" / "pairs").glob("*/features.tsv"), OUT]:
        if p.exists():
            with p.open(newline="") as f:
                have |= {r["video_id"] for r in csv.DictReader(f, delimiter="\t")}
    return have


def main() -> None:
    con = sqlite3.connect(DB, timeout=120)
    vids = sorted({v for a, b in con.execute("SELECT a, b FROM pairs WHERE label IN ('re-skin', 're-upload') "
                                             "AND confidence >= 0.7") for v in (a, b)})
    todo = [v for v in vids if yt.video_path(v).exists() and v not in measured()]
    print(f"{len(todo)} videos to measure")
    if not todo:
        return
    clips = ROOT / "cache" / "clips"
    for v in todo:
        d = media.probe(yt.video_path(v))["duration"]
        start = CLIP_START if d > CLIP_START + 10 else 0.0
        cut(yt.video_path(v), clips / f"{v}.mp4", start, min(CLIP_LEN, d - start))
    # Earlier rows are kept: derive writes only this run's videos, so merge them.
    old = OUT.read_text().splitlines() if OUT.exists() else []
    pipeline(todo, clips, ROOT / "cache" / "features" / "npz", OUT)
    new = OUT.read_text().splitlines()
    if old:
        OUT.write_text("\n".join([new[0], *old[1:], *new[1:]]) + "\n")
    print(f"measured {len(todo)} videos into {OUT}")


if __name__ == "__main__":
    main()
