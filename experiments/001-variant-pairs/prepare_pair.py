"""Filter 7 of the search, first half: get a downloaded pair ready for score_pair.py.

    uv run python 001-variant-pairs/prepare_pair.py A B --name N

Aligns the two downloads, cuts each video's dataset-style clip (from 0:30, up to 5 min) into
cache/clips/ and the pair's shared part (the main aligned segment, from 0:30 on A's clock) into
cache/clips-shared/<name>/, then runs the backend pipeline's extract/derive into
cache/features/pairs/<name>/ (features.tsv, features-shared.tsv). Stills and clips stay in cache/.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import overlap  # noqa: E402

import align  # noqa: E402
import media  # noqa: E402
import yt  # noqa: E402

CLIP_START, CLIP_LEN = 30.0, 300.0


def cut(src: Path, out: Path, start: float, length: float) -> None:
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src),
                    "-t", f"{length:.3f}",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
                    str(out)], check=True)


def pipeline(ids: list[str], clips: Path, cache: Path, out: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = out.parent / f"manifest-{out.stem}.tsv"
    manifest.write_text("video_id\n" + "\n".join(ids) + "\n")
    script = REPO / "backend" / "pipeline" / "04_extract_features_v2.py"
    base = ["uv", "run", "--project", str(REPO / "backend"), "python", str(script)]
    subprocess.run(base + ["extract", "--manifest", str(manifest), "--clips-dir", str(clips),
                           "--cache-dir", str(cache)], check=True, cwd=REPO / "backend")
    subprocess.run(base + ["derive", "--manifest", str(manifest), "--cache-dir", str(cache),
                           "--out", str(out)],
                   check=True, cwd=REPO / "backend")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--name", required=True)
    ap.add_argument("--b-file", type=Path,
                    help="B's video file instead of its download (a sped-up copy slowed to 1x, speed.py); "
                         "its clips and features then stay in the pair's own folders")
    args = ap.parse_args()
    va, vb = args.a, args.b
    pa, pb = yt.video_path(va), args.b_file or yt.video_path(vb)
    assert pa.exists() and pb.exists(), "download both videos first"
    ya, yb = media.audio(pa), media.audio(pb)
    dur_a, dur_b = len(ya) / align.SR, len(yb) / align.SR
    segs = overlap.align_pair(pa, pb, ya, yb)["segs"]  # as score_pair.py aligns it
    assert segs, "no alignment from audio or frames"
    main_seg = segs[0]
    # A changed B mustn't land in the shared clip and feature caches under B's own video ID.
    clips = ROOT / "cache" / "clips-pair" / args.name if args.b_file else ROOT / "cache" / "clips"
    feat = ROOT / "cache" / "features" / "pairs" / args.name
    npz = feat / "npz" if args.b_file else ROOT / "cache" / "features" / "npz"
    for v, p, d in ((va, pa, dur_a), (vb, pb, dur_b)):
        start = CLIP_START if d > CLIP_START + 10 else 0.0
        cut(p, clips / f"{v}.mp4", start, min(CLIP_LEN, d - start))
    # Shared part: A's [max(a0, 0:30), a1) and B's same moments.
    a0 = max(main_seg.a0, CLIP_START if main_seg.a1 - CLIP_START > 20 else main_seg.a0)
    a1 = min(main_seg.a1, a0 + CLIP_LEN)
    shared = ROOT / "cache" / "clips-shared" / args.name
    cut(pa, shared / f"{va}.mp4", a0, a1 - a0)
    cut(pb, shared / f"{vb}.mp4", a0 + main_seg.lag, a1 - a0)
    pipeline([va, vb], clips, npz, feat / "features.tsv")
    pipeline([va, vb], shared, feat / "npz-shared", feat / "features-shared.tsv")
    print(f"{args.name}: main segment A {a0:.1f}-{a1:.1f} s, lag {main_seg.lag:+.2f} s; features in {feat}")


if __name__ == "__main__":
    main()
