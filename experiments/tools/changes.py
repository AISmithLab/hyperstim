"""What changed between two aligned versions: color, which parts of the frame, and parts only
one version has."""

from __future__ import annotations

import cv2
import numpy as np

from align import Segment
from visual import flow_map, ssim

DELTA_E = 15.0       # Lab distance above which a pixel counts as changed
RESHAPE_SSIM = 0.5   # local gradient SSIM below which a changed pixel counts as reshaped


def _lab(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32) * np.array([100 / 255, 1, 1], np.float32) \
        - np.array([0, 128, 128], np.float32)


def _grad(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return np.clip(np.hypot(gx, gy), 0, 255).astype(np.uint8)


def pair_change(rgb_a: np.ndarray, rgb_b: np.ndarray, moving: np.ndarray) -> dict:
    """Per-pixel change of one aligned frame pair (same size): masks and shares."""
    la, lb = _lab(cv2.GaussianBlur(rgb_a, (5, 5), 1)), _lab(cv2.GaussianBlur(rgb_b, (5, 5), 1))
    de = np.linalg.norm(la - lb, axis=2)
    changed = de > DELTA_E
    ga, gb = cv2.cvtColor(rgb_a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(rgb_b, cv2.COLOR_RGB2GRAY)
    local = ssim(_grad(ga), _grad(gb), full=True)
    reshaped = changed & (local < RESHAPE_SSIM)
    recolored = changed & ~reshaped
    return {"delta_e": de, "changed": changed, "reshaped": reshaped, "recolored": recolored, "moving": moving}


def mask_image(rgb_a: np.ndarray, ch: dict) -> np.ndarray:
    """A's frame dimmed to gray, with recolored pixels tinted one color and reshaped another."""
    g = cv2.cvtColor(cv2.cvtColor(rgb_a, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB).astype(np.float32) * 0.45
    out = g.copy()
    out[ch["recolored"]] = 0.35 * g[ch["recolored"]] + 0.65 * np.array([235, 170, 40], np.float32)
    out[ch["reshaped"]] = 0.35 * g[ch["reshaped"]] + 0.65 * np.array([200, 60, 160], np.float32)
    return out.astype(np.uint8)


def hue_hist(rgb: np.ndarray, bins: int = 24) -> np.ndarray:
    """Hue histogram weighted by saturation x value (gray pixels count little)."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV_FULL).reshape(-1, 3).astype(np.float32)
    w = (hsv[:, 1] / 255) * (hsv[:, 2] / 255)
    h, _ = np.histogram(hsv[:, 0], bins=bins, range=(0, 256), weights=w)
    return h / (h.sum() + 1e-9)


def palette(rgbs: list[np.ndarray], k: int = 6, seed: int = 0) -> list[dict]:
    """Dominant colors (k-means on Lab) over a set of frames, largest first."""
    px = np.concatenate([im.reshape(-1, 3) for im in rgbs])
    rng = np.random.default_rng(seed)
    px = px[rng.choice(len(px), min(len(px), 40000), replace=False)]
    lab = cv2.cvtColor(px[None], cv2.COLOR_RGB2LAB)[0].astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    cv2.setRNGSeed(seed)
    _, labels, centers = cv2.kmeans(lab, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    rgb = cv2.cvtColor(centers.astype(np.uint8)[None], cv2.COLOR_LAB2RGB)[0]
    share = np.bincount(labels.ravel(), minlength=k) / len(labels)
    order = np.argsort(-share)
    return [{"hex": "#{:02x}{:02x}{:02x}".format(*(int(v) for v in rgb[i])), "share": float(share[i])}
            for i in order]


def color_summary(rgbs_a: list[np.ndarray], rgbs_b: list[np.ndarray]) -> dict:
    """Hue and saturation difference over aligned frame pairs."""
    sat = lambda im: cv2.cvtColor(im, cv2.COLOR_RGB2HSV)[..., 1].mean() / 255  # noqa: E731
    sa = np.array([sat(x) for x in rgbs_a])
    sb = np.array([sat(x) for x in rgbs_b])
    ha = np.mean([hue_hist(x) for x in rgbs_a], axis=0)
    hb = np.mean([hue_hist(x) for x in rgbs_b], axis=0)
    de = np.array([np.linalg.norm(_lab(a) - _lab(b), axis=2).mean()
                   for a, b in zip(rgbs_a, rgbs_b, strict=False)])
    lum = lambda im: _lab(im)[..., 0].mean()  # noqa: E731
    return {
        "saturation_a": float(sa.mean()), "saturation_b": float(sb.mean()),
        "saturation_diff": float((sb - sa).mean()),
        "lightness_diff": float(np.mean([lum(b) - lum(a) for a, b in zip(rgbs_a, rgbs_b, strict=False)])),
        "hue_hist_a": ha.tolist(), "hue_hist_b": hb.tolist(),
        "hue_hist_overlap": float(np.minimum(ha, hb).sum()),
        "delta_e_mean": float(de.mean()), "delta_e_curve": de.tolist(),
        "palette_a": palette(rgbs_a), "palette_b": palette(rgbs_b),
    }


def area_summary(changes: list[dict]) -> dict:
    """Shares of the frame that changed, split by type (recolored, reshaped) and by moving
    (characters, mostly) vs still (background, mostly) pixels."""
    tot = sum(c["changed"].size for c in changes)
    mov = sum(int(c["moving"].sum()) for c in changes)
    still = tot - mov

    def share(key: str, where: str | None = None) -> float:
        num = 0
        for c in changes:
            m = c[key]
            if where == "moving":
                m = m & c["moving"]
            elif where == "still":
                m = m & ~c["moving"]
            num += int(m.sum())
        den = {"moving": mov, "still": still}.get(where, tot)
        return num / den if den else float("nan")

    return {
        "changed": share("changed"), "recolored": share("recolored"), "reshaped": share("reshaped"),
        "moving_share": mov / tot,
        "moving": {"changed": share("changed", "moving"), "recolored": share("recolored", "moving"),
                   "reshaped": share("reshaped", "moving")},
        "still": {"changed": share("changed", "still"), "recolored": share("recolored", "still"),
                  "reshaped": share("reshaped", "still")},
        "changed_curve": [float(c["changed"].mean()) for c in changes],
        "reshaped_curve": [float(c["reshaped"].mean()) for c in changes],
        "recolored_curve": [float(c["recolored"].mean()) for c in changes],
    }


def only_parts(segs: list[Segment], dur_a: float, dur_b: float, min_len: float = 1.0) -> dict:
    """Stretches only one version has (from the alignment): intros, outros, inserted parts."""
    def gaps(spans, dur):
        out, t = [], 0.0
        for s0, s1 in sorted(spans):
            if s0 - t >= min_len:
                out.append([t, s0])
            t = max(t, s1)
        if dur - t >= min_len:
            out.append([t, dur])
        return out

    a_spans = [(s.a0, s.a1) for s in segs]
    b_spans = [(s.a0 + s.lag, s.a1 + s.lag) for s in segs]
    return {"only_a": gaps(a_spans, dur_a), "only_b": gaps(b_spans, dur_b),
            "matched_a": sorted([list(x) for x in a_spans]), "matched_b": sorted([list(x) for x in b_spans])}


def moving_mask(gray_small: np.ndarray, i: int, size: tuple[int, int]) -> np.ndarray:
    m = flow_map(gray_small[max(0, i - 1)], gray_small[i]) if i > 0 else np.zeros(gray_small.shape[1:], bool)
    return cv2.resize(m.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)
