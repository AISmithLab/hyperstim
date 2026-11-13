"""Align two videos in time from their audio, before any frame-by-frame signal.

Times are seconds. A segment maps A's [a0, a1) onto B's [a0 + lag, a1 + lag): B time = A time + lag.
A pair can have several segments (an intro only one version has shifts everything after it).
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
import scipy.signal as ss

SR = 22050
HOP = 512
WIN_S = 2.0   # window for local matching
STEP_S = 0.5


@dataclass
class Segment:
    a0: float
    a1: float
    lag: float     # B time = A time + lag
    score: float   # mean local spectral correlation

    @property
    def length(self) -> float:
        return self.a1 - self.a0


def _z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-9)


def onset_env(y: np.ndarray) -> np.ndarray:
    return _z(librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP))


def logmel(y: np.ndarray) -> np.ndarray:
    """(frames, 64) log-mel, each band's mean removed: robust to gain and EQ differences."""
    m = librosa.power_to_db(librosa.feature.melspectrogram(y=y, sr=SR, hop_length=HOP, n_mels=64))
    return (m - m.mean(axis=1, keepdims=True)).T


def global_lag(a: np.ndarray, b: np.ndarray) -> float:
    """Best single lag (s): onset-envelope cross-correlation, refined on the waveform."""
    ea, eb = onset_env(a), onset_env(b)
    c = ss.correlate(eb, ea, mode="full")
    lags = np.arange(-len(ea) + 1, len(eb))
    coarse = int(lags[np.argmax(c)]) * HOP
    # Refine to the sample on a central chunk of A, searching ±2 hops around the coarse lag.
    pad = 2 * HOP
    lo_a, hi_a = max(0, pad - coarse), min(len(a), len(b) - coarse - pad)  # A range that fits in B
    n = min(20 * SR, hi_a - lo_a)
    if n < SR:
        return coarse / SR
    a0 = int(np.clip(len(a) // 2 - n // 2, lo_a, hi_a - n))
    seg = a[a0:a0 + n]
    lo_b = a0 + coarse - pad
    ref = b[lo_b: lo_b + n + 2 * pad]
    cc = ss.fftconvolve(ref, seg[::-1], mode="valid")
    norm = np.sqrt(np.convolve(ref**2, np.ones(n), "valid")) * np.linalg.norm(seg) + 1e-9
    r = cc / norm
    best = int(np.argmax(r))
    if r[best] < 0.5:  # no shared waveform (re-recorded): keep the onset lag
        return coarse / SR
    return (lo_b + best - a0) / SR


def window_scores(ma: np.ndarray, mb: np.ndarray, lag: float, times: np.ndarray) -> np.ndarray:
    """Spectral correlation of A's window at each time with B's window at time + lag (NaN where
    B has no audio)."""
    fps = SR / HOP
    w = int(WIN_S * fps)
    out = np.full(len(times), np.nan)
    for i, t in enumerate(times):
        ia, ib = int(t * fps), int((t + lag) * fps)
        if ia < 0 or ib < 0 or ia + w > len(ma) or ib + w > len(mb):
            continue
        x, y = ma[ia:ia + w].ravel(), mb[ib:ib + w].ravel()
        out[i] = np.corrcoef(x, y)[0, 1]
    return out


def null_scores(ma: np.ndarray, mb: np.ndarray, lag: float, times: np.ndarray,
                min_shift: float = 3.0, n_shifts: int = 40, seed: int = 0) -> np.ndarray:
    """Window scores at other moments (lag shifted by ≥ min_shift): the time-shift baseline."""
    rng = np.random.default_rng(seed)
    span = len(mb) * HOP / SR
    shifts = rng.uniform(min_shift, max(min_shift + 1, span / 2), n_shifts) * rng.choice([-1, 1], n_shifts)
    vals = np.concatenate([window_scores(ma, mb, lag + s, times) for s in shifts])
    return vals[~np.isnan(vals)]


def segments(a: np.ndarray, b: np.ndarray) -> tuple[list[Segment], dict]:
    """Matching segments of A in B, longest first, plus the curves behind them."""
    ma, mb = logmel(a), logmel(b)
    dur_a = len(a) / SR
    times = np.arange(0, max(0.0, dur_a - WIN_S), STEP_S)
    lag0 = global_lag(a, b)
    null = null_scores(ma, mb, lag0, times)
    # No baseline when every window is silent (no correlation): then only the floor.
    thr = float(max(np.percentile(null, 99), 0.5)) if len(null) else 0.5
    score0 = window_scores(ma, mb, lag0, times)
    matched = np.nan_to_num(score0, nan=-1) > thr
    dur_b = len(b) / SR
    segs = _runs(times, matched, score0, lag0, dur_a, dur_b)
    # Second pass: unmatched runs of ≥ 4 s may sit elsewhere in B (moved or a different intro).
    fps = SR / HOP
    w = int(WIN_S * fps)
    for t0, t1 in _gaps(times, matched, min_len=4.0):
        ia = int(t0 * fps)
        n = int((t1 - t0) * fps)
        if n < w:
            continue
        x = ma[ia:ia + n]
        best, best_lag = -1.0, 0.0
        for ib in range(0, len(mb) - n, 4):
            r = np.corrcoef(x.ravel(), mb[ib:ib + n].ravel())[0, 1]
            if r > best:
                best, best_lag = r, ib / fps - t0
        if best > thr:
            sel = (times >= t0) & (times < t1)
            sc = window_scores(ma, mb, best_lag, times[sel])
            segs += _runs(times[sel], np.nan_to_num(sc, nan=-1) > thr, sc, best_lag, dur_a, dur_b)
    segs.sort(key=lambda s: -s.length)
    curves = {"times": times, "score": score0, "threshold": thr, "lag": lag0,
              "null_p99": float(np.percentile(null, 99)) if len(null) else None,
              "null_median": float(np.median(null)) if len(null) else None}
    return segs, curves


def _runs(times: np.ndarray, mask: np.ndarray, score: np.ndarray, lag: float,
          dur_a: float, dur_b: float, min_len: float = 2.0) -> list[Segment]:
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            a0, a1 = float(times[start]), float(times[i - 1] + WIN_S)
            # Where the neighbouring window ran past either file's edge, the match runs to the edge.
            if start > 0 and np.isnan(score[start - 1]):
                a0 = max(float(times[start - 1]), -lag, 0.0)
            if start == 0:
                a0 = max(-lag, 0.0)
            if i < len(score) and np.isnan(score[i]) or i == len(score):
                a1 = min(dur_a, dur_b - lag)
            if a1 - a0 >= min_len:
                out.append(Segment(a0, a1, lag, float(np.nanmean(score[start:i]))))
            start = None
    return out


def _gaps(times: np.ndarray, mask: np.ndarray, min_len: float) -> list[tuple[float, float]]:
    out, start = [], None
    for i, m in enumerate(list(mask) + [True]):
        if not m and start is None:
            start = i
        elif m and start is not None:
            t0, t1 = float(times[start]), float(times[min(i, len(times) - 1)])
            if t1 - t0 >= min_len:
                out.append((t0, t1))
            start = None
    return out


def map_time(segs: list[Segment], t: float) -> float | None:
    """B time for A time t, or None where A has no match."""
    for s in segs:
        if s.a0 <= t < s.a1:
            return t + s.lag
    return None


def speed_ratio(a: np.ndarray, b: np.ndarray, seg: Segment) -> float:
    """B's speed relative to A within a segment, from how the best local lag drifts over time."""
    ea, eb = onset_env(a), onset_env(b)
    fps = SR / HOP
    w = int(4 * fps)
    ts, lags = [], []
    for t in np.arange(seg.a0, seg.a1 - 4, 2.0):
        ia = int(t * fps)
        ib = int((t + seg.lag) * fps)
        lo, hi = max(0, ib - 10), min(len(eb) - w, ib + 10)
        if hi <= lo:
            continue
        x = ea[ia:ia + w]
        r = [np.dot(x, eb[j:j + w]) for j in range(lo, hi)]
        ts.append(t)
        lags.append((lo + int(np.argmax(r)) - ib) / fps)
    if len(ts) < 3:
        return 1.0
    slope = np.polyfit(ts, lags, 1)[0]
    return float(1.0 / (1.0 + slope))
