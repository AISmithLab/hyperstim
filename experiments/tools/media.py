"""Decode a cached video's frames and audio into numpy arrays (ffmpeg pipes, no temp files)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(path)], capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    return {"fps": num / den, "width": int(v["width"]), "height": int(v["height"]),
            "duration": float(d["format"]["duration"])}


def frames(path: Path, size: tuple[int, int], fps: float | None = None, gray: bool = False) -> np.ndarray:
    """All frames (or `fps` frames a second) scaled to `size` (w, h): uint8, (n, h, w[, 3]) RGB."""
    w, h = size
    vf = f"scale={w}:{h}:flags=area"
    if fps:
        vf = f"fps={fps}," + vf
    fmt, ch = ("gray", 1) if gray else ("rgb24", 3)
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", fmt, "-"], capture_output=True, check=True).stdout
    arr = np.frombuffer(out, np.uint8)
    n = arr.size // (w * h * ch)
    arr = arr[: n * w * h * ch]
    return arr.reshape((n, h, w) if gray else (n, h, w, 3))


def audio(path: Path, sr: int = 22050) -> np.ndarray:
    """Mono float32 samples at `sr`."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()
