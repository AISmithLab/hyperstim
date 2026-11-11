"""Audio signals: how close two videos' sound is, as levels from most to least similar.

Levels (PLAN.md, Audio): exact same audio > same audio, adjusted (gain, EQ, speed) > same backing,
different overlay (stems) > same song, re-recorded (chroma). A pair's level is the closest one
that holds. Each level also gets its longest matching segment, measured on A's timeline.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import maximum_filter

from align import SR, Segment, map_time

STEP = 1.0  # seconds between window measurements
WIN = 2.0

# Absolute floors that define the levels; each must also beat the time-shift baseline's p99.
EXACT_CORR, EXACT_GAIN_DB = 0.99, 0.5
ADJUSTED_CORR = 0.9
BACKING_CORR = 0.8


def _aligned(a: np.ndarray, b: np.ndarray, seg: Segment) -> tuple[np.ndarray, np.ndarray]:
    ia0 = int(seg.a0 * SR)
    ia1 = int(seg.a1 * SR)
    ib0 = ia0 + int(round(seg.lag * SR))
    ib0c = max(0, ib0)
    ia0 += ib0c - ib0
    n = min(ia1 - ia0, len(b) - ib0c)
    return a[ia0:ia0 + n], b[ib0c:ib0c + n]


def gain_db(a: np.ndarray, b: np.ndarray) -> float:
    """B's level relative to A over the same aligned samples (positive = B louder)."""
    return float(20 * np.log10((np.std(b) + 1e-9) / (np.std(a) + 1e-9)))


def window_curve(fa, fb, segs: list[Segment], dur_a: float, rate: float,
                 shift: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Per-window similarity on A's timeline. `fa`/`fb` are (time, dims) arrays at `rate` frames a
    second (dims=1 for waveforms); `shift` offsets B for the time-shift baseline."""
    times = np.arange(0, max(0.0, dur_a - WIN), STEP)
    out = np.full(len(times), np.nan)
    w = int(WIN * rate)
    for i, t in enumerate(times):
        tb = map_time(segs, t + WIN / 2)
        if tb is None:
            continue
        ia, ib = int(t * rate), int((tb - WIN / 2 + shift) * rate)
        if ib < 0 or ia + w > len(fa) or ib + w > len(fb):
            continue
        x, y = fa[ia:ia + w].ravel(), fb[ib:ib + w].ravel()
        if x.std() < 1e-6 or y.std() < 1e-6:
            continue
        out[i] = np.corrcoef(x, y)[0, 1]
    return times, out


def shifted_null(fa, fb, segs, dur_a, rate, n: int = 30, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    shifts = rng.uniform(3, 30, n) * rng.choice([-1, 1], n)
    vals = np.concatenate([window_curve(fa, fb, segs, dur_a, rate, s)[1] for s in shifts])
    return vals[~np.isnan(vals)]


def longest_run(times: np.ndarray, curve: np.ndarray, thr: float) -> tuple[float, float, float]:
    """Longest stretch (start, end, length s) where the curve stays above thr."""
    best, start = (0.0, 0.0, 0.0), None
    ok = list(np.nan_to_num(curve, nan=-9) > thr) + [False]
    for i, m in enumerate(ok):
        if m and start is None:
            start = i
        elif not m and start is not None:
            t0, t1 = float(times[start]), float(times[i - 1] + WIN)
            if t1 - t0 > best[2]:
                best = (t0, t1, t1 - t0)
            start = None
    return best


# --- Fingerprint ------------------------------------------------------------------------


def fingerprint(y: np.ndarray) -> dict[int, list[int]]:
    """Landmark hashes: pairs of spectrogram peaks (f1, f2, dt) -> frames where they occur."""
    s = np.log(np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) + 1e-6)
    peaks = (s == maximum_filter(s, size=(20, 20))) & (s > np.percentile(s, 80))
    f_idx, t_idx = np.nonzero(peaks)
    order = np.argsort(t_idx)
    f_idx, t_idx = f_idx[order], t_idx[order]
    out: dict[int, list[int]] = {}
    for i in range(len(t_idx)):
        fan = 0
        for j in range(i + 1, len(t_idx)):
            dt = t_idx[j] - t_idx[i]
            if dt > 40:
                break
            if dt < 1 or abs(int(f_idx[j]) - int(f_idx[i])) > 100:
                continue
            h = (int(f_idx[i]) << 20) | (int(f_idx[j]) << 8) | int(dt)
            out.setdefault(h, []).append(int(t_idx[i]))
            fan += 1
            if fan >= 5:
                break
    return out


def fingerprint_match(fa: dict, fb: dict) -> dict:
    """Share of A's hashes that B has at one consistent offset, and that offset (s)."""
    offsets: dict[int, int] = {}
    for h, ta in fa.items():
        tb = fb.get(h)
        if not tb:
            continue
        for x in ta:
            for y in tb:
                offsets[y - x] = offsets.get(y - x, 0) + 1
    total = min(sum(map(len, fa.values())), sum(map(len, fb.values())))
    if not offsets or not total:
        return {"share": 0.0, "offset_s": None}
    off, count = max(offsets.items(), key=lambda kv: kv[1])
    return {"share": count / total, "offset_s": off * 512 / SR}


# --- Stems ------------------------------------------------------------------------------


def stems(path: Path, cache_dir: Path) -> dict[str, np.ndarray]:
    """Demucs (htdemucs) stems, mono at SR, cached as .npz next to the clip cache."""
    out = cache_dir / f"{path.stem}.stems.npz"
    if out.exists():
        d = np.load(out)
        return {k: d[k] for k in d.files}
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    from media import audio as load_audio

    model = get_model("htdemucs")
    model.eval()
    y = load_audio(path, sr=model.samplerate)
    wav = torch.tensor(np.stack([y, y]))[None]
    ref = wav.mean(1)
    wav = (wav - ref.mean()) / (ref.std() + 1e-9)
    with torch.no_grad():
        src = apply_model(model, wav, device="cpu", progress=False)[0]
    src = src * (ref.std() + 1e-9) + ref.mean()
    res = {name: librosa.resample(src[i].mean(0).numpy(), orig_sr=model.samplerate, target_sr=SR)
           for i, name in enumerate(model.sources)}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **res)
    return res


# --- Levels -----------------------------------------------------------------------------


def chroma(y: np.ndarray) -> np.ndarray:
    return librosa.feature.chroma_cens(y=y, sr=SR, hop_length=512).T


def logmel(y: np.ndarray) -> np.ndarray:
    m = librosa.power_to_db(librosa.feature.melspectrogram(y=y, sr=SR, hop_length=512, n_mels=64))
    return (m - m.mean(axis=1, keepdims=True)).T


KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def key_of(y: np.ndarray) -> str:
    prof = librosa.feature.chroma_cqt(y=y, sr=SR).mean(axis=1)
    best = max(((np.corrcoef(prof, np.roll(p, k))[0, 1], f"{KEYS[k]} {m}")
                for p, m in ((_MAJOR, "major"), (_MINOR, "minor")) for k in range(12)))
    return best[1]


def tempo_of(y: np.ndarray) -> float:
    return float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=SR)[0])[0])


def analyze(a: np.ndarray, b: np.ndarray, segs: list[Segment], stems_a: dict, stems_b: dict,
            speed: float) -> dict:
    """All audio levels for a pair: summary values, per-window curves, baselines and the level."""
    dur_a = len(a) / SR
    main = segs[0]
    xa, xb = _aligned(a, b, main)
    fr = SR / 512
    feats = {
        "waveform": (a[:, None], b[:, None], SR),
        "spectrum": (logmel(a), logmel(b), fr),
        "chroma": (chroma(a), chroma(b), fr),
    }
    backing = {k: sum(v[s] for s in ("drums", "bass", "other")) for k, v in (("a", stems_a), ("b", stems_b))}
    feats["backing"] = (backing["a"][:, None], backing["b"][:, None], SR)
    feats["vocals"] = (stems_a["vocals"][:, None], stems_b["vocals"][:, None], SR)
    curves, nulls = {}, {}
    times = None
    for name, (fa, fb, rate) in feats.items():
        times, curves[name] = window_curve(fa, fb, segs, dur_a, rate)
        nulls[name] = shifted_null(fa, fb, segs, dur_a, rate, n=12 if rate == SR else 30)

    def summary(name: str) -> dict:
        c = curves[name]
        p99 = float(np.percentile(nulls[name], 99))
        return {"median": float(np.nanmedian(c)), "baseline_p99": p99,
                "baseline_median": float(np.median(nulls[name])),
                "longest": longest_run(times, c, p99)}

    wave_corr = float(np.corrcoef(xa, xb)[0, 1])
    g = gain_db(xa, xb)
    fp = fingerprint_match(fingerprint(a), fingerprint(b))
    stem_corr = {}
    stem_gain = {}
    for s in stems_a:
        sa, sb = _aligned(stems_a[s], stems_b[s], main)
        stem_corr[s] = float(np.corrcoef(sa, sb)[0, 1]) if sa.std() > 1e-4 and sb.std() > 1e-4 else None
        stem_gain[s] = gain_db(sa, sb)
    ba, bb = _aligned(backing["a"], backing["b"], main)
    backing_corr = float(np.corrcoef(ba, bb)[0, 1])
    s_wave, s_spec, s_chroma = summary("waveform"), summary("spectrum"), summary("chroma")
    s_back, s_voc = summary("backing"), summary("vocals")

    levels = [
        {"key": "exact", "name": "Exact same audio",
         "holds": wave_corr >= EXACT_CORR and abs(g) < EXACT_GAIN_DB and abs(speed - 1) < 1e-3
         and wave_corr > s_wave["baseline_p99"],
         "evidence": {"waveform_corr": wave_corr, "gain_db": g, "fingerprint_share": fp["share"]},
         "longest": longest_run(times, curves["waveform"], max(EXACT_CORR, s_wave["baseline_p99"]))},
        {"key": "adjusted", "name": "Same audio, adjusted",
         "holds": wave_corr >= ADJUSTED_CORR and wave_corr > s_wave["baseline_p99"],
         "evidence": {"waveform_corr": wave_corr, "gain_db": g, "speed": speed,
                      "spectrum_median": s_spec["median"]},
         "longest": longest_run(times, curves["waveform"], max(ADJUSTED_CORR, s_wave["baseline_p99"]))},
        {"key": "backing", "name": "Same backing, different overlay",
         "holds": backing_corr >= BACKING_CORR and backing_corr > s_back["baseline_p99"],
         "evidence": {"backing_corr": backing_corr, "vocals_corr": stem_corr.get("vocals"),
                      "stem_corr": stem_corr, "stem_gain_db": stem_gain},
         "longest": longest_run(times, curves["backing"], max(BACKING_CORR, s_back["baseline_p99"]))},
        {"key": "rerecorded", "name": "Same song, re-recorded",
         "holds": s_chroma["median"] > s_chroma["baseline_p99"],
         "evidence": {"chroma_median": s_chroma["median"], "key_a": key_of(a), "key_b": key_of(b),
                      "tempo_a": tempo_of(a), "tempo_b": tempo_of(b)},
         "longest": s_chroma["longest"]},
    ]
    level = next((lv["key"] for lv in levels if lv["holds"]), "none")
    return {
        "level": level, "levels": levels, "offset_s": main.lag, "speed": speed, "gain_db": g,
        "fingerprint": fp, "waveform_corr": wave_corr, "backing_corr": backing_corr,
        "stem_corr": stem_corr, "stem_gain_db": stem_gain,
        "summaries": {"waveform": s_wave, "spectrum": s_spec, "chroma": s_chroma,
                      "backing": s_back, "vocals": s_voc},
        "curves": {"times": times, **curves},
    }
