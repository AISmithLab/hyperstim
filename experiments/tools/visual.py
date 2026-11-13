"""Visual signals: thumbnails and storyboards (image tier), and frame-by-frame signals on the
aligned downloads (cuts, motion, structure, content).

Every frame signal is measured at the aligned time and against the time-shift baseline (B moved
by 3-30 s: the same videos at other moments). A repetitive song makes that baseline strict.
"""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from align import Segment, map_time

SHIFTS_SEED = 0


def shifts(n: int = 12, lo: float = 3.0, hi: float = 30.0, seed: int = SHIFTS_SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(lo, hi, n) * rng.choice([-1, 1], n)


# --- Image helpers ----------------------------------------------------------------------


def edges(gray: np.ndarray) -> np.ndarray:
    """Soft edge map, independent of color: Canny on gray with thresholds from its median."""
    med = float(np.median(gray))
    e = cv2.Canny(gray, int(max(10, 0.66 * med)), int(min(255, max(30, 1.33 * med))))
    return cv2.GaussianBlur(e, (5, 5), 1.5)


def ssim(x: np.ndarray, y: np.ndarray, full: bool = False):
    """Mean SSIM of two uint8 gray images (Gaussian window, standard constants)."""
    x, y = x.astype(np.float64), y.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    blur = lambda z: cv2.GaussianBlur(z, (11, 11), 1.5)  # noqa: E731
    mx, my = blur(x), blur(y)
    vx, vy, cxy = blur(x * x) - mx * mx, blur(y * y) - my * my, blur(x * y) - mx * my
    m = ((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
    return m if full else float(m.mean())


def dhash(img: np.ndarray, size: int = 8) -> np.ndarray:
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (size + 1, size), interpolation=cv2.INTER_AREA)
    return (g[:, 1:] > g[:, :-1]).ravel()


def hash_similarity(h1: np.ndarray, h2: np.ndarray) -> float:
    return float(1 - np.count_nonzero(h1 != h2) / h1.size)


def load_image(path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


# --- DINOv2 -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _dino():
    import os

    import torch

    torch.set_num_threads(int(os.environ.get("EXP_TORCH_THREADS", "8")))
    model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", verbose=False)
    model.eval()
    return model


def embed(images: list[np.ndarray] | np.ndarray, size: tuple[int, int] = (392, 224),
          batch: int = 32) -> np.ndarray:
    """L2-normalised DINOv2 (ViT-S/14) CLS embeddings of RGB uint8 images, resized to size (w, h)."""
    import torch

    if len(images) == 0:
        return np.zeros((0, 384), np.float32)
    model = _dino()
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)
    out = []
    for i in range(0, len(images), batch):
        x = np.stack([cv2.resize(im, size, interpolation=cv2.INTER_AREA) for im in images[i:i + batch]])
        x = ((x.astype(np.float32) / 255 - mean) / std).transpose(0, 3, 1, 2)
        with torch.no_grad():
            f = model(torch.from_numpy(x)).numpy()
        out.append(f / np.linalg.norm(f, axis=1, keepdims=True))
    return np.concatenate(out)


# --- Thumbnail --------------------------------------------------------------------------


def thumbnail_similarity(img_a: np.ndarray, img_b: np.ndarray, emb_a: np.ndarray, emb_b: np.ndarray) -> dict:
    return {"embedding": float(emb_a @ emb_b), "hash": hash_similarity(dhash(img_a), dhash(img_b))}


# --- Storyboard -------------------------------------------------------------------------


def storyboard_format(info: dict) -> dict | None:
    """The largest storyboard format in a yt-dlp info JSON."""
    sbs = [f for f in info.get("formats", []) if f.get("format_note") == "storyboard"]
    return max(sbs, key=lambda f: f["width"], default=None)


def storyboard_frames(fmt: dict, sprites: list[np.ndarray],
                      duration: float) -> tuple[np.ndarray, list[np.ndarray]]:
    """Slice sprite sheets into frames; returns (frame times, frames).

    Tile k shows the video at k x interval, interval = max(1 s, duration / tiles). Not yt-dlp's
    fragment durations: matching the seed pair's tiles to their downloads put every tile at a
    whole second (yt-dlp's durations implied 0.983 s, drifting 2 s by the end)."""
    w, h, rows, cols = fmt["width"], fmt["height"], fmt["rows"], fmt["columns"]
    tiles = []
    for sheet in sprites:
        for k in range(rows * cols):
            r, c = divmod(k, cols)
            tile = sheet[r * h:(r + 1) * h, c * w:(c + 1) * w]
            if tile.shape[:2] == (h, w):  # the last sheet can be partly filled
                tiles.append(tile)
    interval = max(1.0, duration / len(tiles))
    n = min(len(tiles), int(np.ceil(duration / interval)))
    return np.arange(n) * interval, tiles[:n]


def storyboard_signal(times_a, frames_a, times_b, frames_b, audio_lag: float | None) -> dict:
    """Sequence similarity of two storyboards and their own best offset (no download needed):
    mean DINOv2 cosine of frame pairs at each candidate offset; plus rough cut positions."""
    # The two may come in different tile sizes: compare at the smaller one.
    w = min(frames_a[0].shape[1], frames_b[0].shape[1])
    h = min(frames_a[0].shape[0], frames_b[0].shape[0])
    frames_a = [cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA) for f in frames_a]
    frames_b = [cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA) for f in frames_b]
    ea, eb = embed(frames_a), embed(frames_b)
    step = float(np.median(np.diff(times_a)))
    cands = np.arange(-30, 30 + 1e-9, step / 2)
    scores = []
    for lag in cands:
        sims = []
        for i, t in enumerate(times_a):
            j = int(np.argmin(np.abs(times_b - (t + lag))))
            if abs(times_b[j] - (t + lag)) <= step / 2:
                sims.append(float(ea[i] @ eb[j]))
        # Enough overlap for a mean: a share of the SHORTER storyboard (a short vs a compilation).
        scores.append(np.mean(sims) if len(sims) >= max(5, 0.3 * min(len(times_a), len(times_b))) else np.nan)
    scores = np.array(scores)
    if np.all(np.isnan(scores)):
        scores = np.nan_to_num(scores, nan=0.0)
    best = int(np.nanargmax(scores))
    lag = float(cands[best])
    far = np.abs(cands - lag) >= 3
    edge_sims, seq = [], []
    for i, t in enumerate(times_a):
        j = int(np.argmin(np.abs(times_b - (t + lag))))
        if abs(times_b[j] - (t + lag)) <= step / 2:
            ga = cv2.cvtColor(frames_a[i], cv2.COLOR_RGB2GRAY)
            gb = cv2.cvtColor(frames_b[j], cv2.COLOR_RGB2GRAY)
            edge_sims.append(ssim(edges(ga), edges(gb)))
            seq.append({"t_a": float(t), "t_b": float(times_b[j]), "embedding": float(ea[i] @ eb[j])})

    def rough_cuts(fr, ts):
        d = np.array([np.abs(fr[k].astype(int) - fr[k - 1].astype(int)).mean() for k in range(1, len(fr))])
        thr = max(np.median(d) * 3, 20)
        return [float(ts[k + 1]) for k in range(len(d)) if d[k] > thr]

    return {"lag": lag, "audio_lag": audio_lag, "embedding": float(scores[best]),
            "baseline_p99": float(np.nanpercentile(scores[far], 99)),
            "baseline_median": float(np.nanmedian(scores[far])),
            "edge_ssim": float(np.mean(edge_sims)) if edge_sims else None,
            "offsets": {"lags": cands.tolist(), "scores": scores.tolist()},
            "sequence": seq, "rough_cuts_a": rough_cuts(frames_a, times_a),
            "rough_cuts_b": rough_cuts(frames_b, times_b), "step_s": step}


# --- Frame signals on the downloads ------------------------------------------------------


def frame_alignment(ea: np.ndarray, eb: np.ndarray, rate: float, dur_a: float, dur_b: float,
                    min_share: float = 0.3) -> Segment | None:
    """Fallback when the audio finds no shared segment (e.g. new audio): the single time offset
    where the two videos' frame embeddings (L2-normalised, `rate` a second) agree best, over at
    least `min_share` of the shorter video. B time = A time + lag, as for audio segments."""
    if len(ea) == 0 or len(eb) == 0:
        return None
    sim = ea @ eb.T
    n = min(len(ea), len(eb))
    best = None
    for k in range(-(len(ea) - 1), len(eb)):  # B index = A index + k
        d = np.diagonal(sim, offset=k)
        if len(d) >= max(3, min_share * n) and (best is None or d.mean() > best[1]):
            best = (k, float(d.mean()))
    if best is None:
        return None
    lag = best[0] / rate
    a0, a1 = max(0.0, -lag), min(dur_a, dur_b - lag)
    return Segment(a0, a1, lag, best[1]) if a1 > a0 else None


def frame_overlap(ea: np.ndarray, eb: np.ndarray, rate: float, seg: Segment, win_s: float = 10.0,
                  step_s: float = 5.0, tol_s: float = 3.0) -> float:
    """Seconds of A that really match B near `seg`'s lag (from frame_alignment): A's 10 s windows,
    every 5 s, whose own best lag over all of B is within `tol_s` of it. A run of frames is unique
    even where single scenes repeat (a song's verses), and the tolerance lets a re-edit drift a little;
    a shared intro covers only its own windows' middles. The segment itself spans the whole overlap at its
    best lag, matched or not."""
    k = round(seg.lag * rate)
    sim = ea @ eb.T
    n, m = sim.shape
    w = min(int(win_s * rate), n, m)
    if w < 1:
        return 0.0
    step, tol = max(1, int(step_s * rate)), int(tol_s * rate)
    covered = np.zeros(n, bool)
    starts = list(range(0, n - w + 1, step))
    if starts[-1] != n - w:
        starts.append(n - w)   # the last window reaches A's end
    for i in starts:
        # Mean similarity along each diagonal through A's window: B frames j0 .. j0 + w - 1.
        acc = np.zeros(m - w + 1)
        for t in range(w):
            acc += sim[i + t, t:t + m - w + 1]
        if abs(int(np.argmax(acc)) - i - k) <= tol:
            # Only the window's middle counts (to its file's edge for the first and last), so a
            # window that only partly overlaps the shared part adds at most half of itself.
            lo = 0 if i == starts[0] else i + (w - step) // 2
            hi = n if i == starts[-1] else i + (w + step) // 2
            covered[lo:hi] = True
    return float(covered.sum() / rate)


def frame_diff(gray: np.ndarray) -> np.ndarray:
    """Per-frame change score from structure (edges) and brightness; index i = change into frame i."""
    out = np.zeros(len(gray))
    prev_e = edges(gray[0]).astype(np.float32)
    for i in range(1, len(gray)):
        e = edges(gray[i]).astype(np.float32)
        out[i] = 0.5 * np.abs(e - prev_e).mean() + np.abs(gray[i].astype(np.float32) - gray[i - 1]).mean()
        prev_e = e
    return out


def cuts(diff: np.ndarray, fps: float) -> np.ndarray:
    """Hard cuts: change spikes well above the local level, at least 0.3 s apart."""
    k = int(fps)
    out = []
    for i in range(1, len(diff)):
        lo, hi = max(1, i - k), min(len(diff), i + k + 1)
        local = np.median(diff[lo:hi])
        if (diff[i] == diff[lo:hi].max() and diff[i] > max(4 * local, 12)
                and (not out or i - out[-1] > 0.3 * fps)):
            out.append(i)
    return np.array(out, int)


def cut_match(cuts_a: np.ndarray, cuts_b: np.ndarray, segs: list[Segment], fps: float,
              shift: float = 0.0, tol: int = 1) -> tuple[float, int]:
    """Share of A's cuts (inside matched segments) with a B cut within ±tol frames."""
    hit = n = 0
    for c in cuts_a:
        tb = map_time(segs, c / fps)
        if tb is None:
            continue
        n += 1
        fb = round((tb + shift) * fps)
        hit += bool(len(cuts_b)) and int(np.min(np.abs(cuts_b - fb))) <= tol
    return (hit / n if n else float("nan")), n


def flow_curves(gray_small: np.ndarray) -> dict[str, np.ndarray]:
    """Farneback optical flow per frame: mean dx, dy (camera pan) and mean magnitude."""
    n = len(gray_small)
    dx, dy, mag, fg = (np.zeros(n) for _ in range(4))
    for i in range(1, n):
        f = cv2.calcOpticalFlowFarneback(gray_small[i - 1], gray_small[i], None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mdx, mdy = np.median(f[..., 0]), np.median(f[..., 1])
        dx[i], dy[i] = mdx, mdy
        m = np.hypot(f[..., 0], f[..., 1])
        mag[i] = m.mean()
        fg[i] = (np.hypot(f[..., 0] - mdx, f[..., 1] - mdy) > 1.0).mean()  # moving apart from camera
    return {"dx": dx, "dy": dy, "magnitude": mag, "object": fg}


def flow_map(prev: np.ndarray, cur: np.ndarray) -> np.ndarray:
    """Mask of pixels moving apart from the camera (characters, mostly)."""
    f = cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mdx, mdy = np.median(f[..., 0]), np.median(f[..., 1])
    return np.hypot(f[..., 0] - mdx, f[..., 1] - mdy) > 1.0


def curve_corr(ca: np.ndarray, cb: np.ndarray, segs: list[Segment], fps: float, shift: float = 0.0) -> float:
    """Pearson correlation of a per-frame curve of A with B's at the aligned frames."""
    xs, ys = [], []
    for i in range(len(ca)):
        tb = map_time(segs, i / fps)
        if tb is None:
            continue
        j = round((tb + shift) * fps)
        if 0 <= j < len(cb):
            xs.append(ca[i])
            ys.append(cb[j])
    if len(xs) < 10 or np.std(xs) < 1e-9 or np.std(ys) < 1e-9:
        return float("nan")
    return float(np.corrcoef(xs, ys)[0, 1])


def sample_pairs(segs: list[Segment], dur_a: float, fps: float, n_b: int, rate: float = 2.0,
                 shift: float = 0.0) -> list[tuple[float, int, int]]:
    """(A time, A frame, B frame) at `rate` a second over A's matched time."""
    out = []
    for t in np.arange(0, dur_a, 1 / rate):
        tb = map_time(segs, t)
        if tb is None:
            continue
        i, j = round(t * fps), round((tb + shift) * fps)
        if 0 <= j < n_b:
            out.append((float(t), i, j))
    return out


def structure(gray_a: np.ndarray, gray_b: np.ndarray, pairs) -> dict[str, np.ndarray]:
    g, e = [], []
    for _, i, j in pairs:
        if i >= len(gray_a):
            g.append(np.nan)
            e.append(np.nan)
            continue
        g.append(ssim(gray_a[i], gray_b[j]))
        e.append(ssim(edges(gray_a[i]), edges(gray_b[j])))
    return {"gray_ssim": np.array(g), "edge_ssim": np.array(e)}
