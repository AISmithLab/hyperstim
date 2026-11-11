import librosa
import numpy as np
import pytest

import align
from align import SR, Segment


def music(dur: float, seed: int) -> np.ndarray:
    """Random decaying notes (distinct onsets and pitches) plus a little noise."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(dur * SR), np.float32)
    t = 0.0
    while t < dur:
        n = rng.uniform(0.1, 0.4)
        f = 110 * 2 ** (rng.integers(0, 36) / 12)
        i0, i1 = int(t * SR), min(len(y), int((t + n) * SR))
        tt = np.arange(i1 - i0) / SR
        y[i0:i1] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 8)).astype(np.float32)
        t += n
    return y + 0.01 * np.random.default_rng(seed + 100).standard_normal(len(y)).astype(np.float32)


@pytest.fixture(scope="module")
def song():
    return music(20, 1)


# global_lag's waveform refinement costs O(chunk x 4 hops): short clips keep these tests fast.


def test_global_lag_recovers_offset():
    a = music(6, 1)
    b = np.concatenate([music(2.5, 2), a])  # B has a 2.5 s intro
    assert align.global_lag(a, b) == pytest.approx(2.5, abs=1 / SR)
    assert align.global_lag(b, a) == pytest.approx(-2.5, abs=1 / SR)


def test_global_lag_keeps_onset_lag_without_shared_waveform():
    a = music(6, 1)
    b = np.concatenate([np.zeros(SR, np.float32), -a])  # inverted: no positive waveform match
    assert abs(align.global_lag(a, b) - 1.0) < 3 * align.HOP / SR


def test_segments_one_shift(song):
    b = np.concatenate([music(2, 2), 0.5 * song])  # quieter: spectral match ignores gain
    segs, curves = align.segments(song, b)
    assert len(segs) == 1
    s = segs[0]
    assert s.lag == pytest.approx(2.0, abs=1e-3)
    assert s.a0 == 0.0 and s.a1 == pytest.approx(20.0)
    assert s.score > 0.9 and s.length == pytest.approx(20.0)
    assert curves["lag"] == s.lag and curves["threshold"] >= 0.5


def test_segments_finds_a_moved_part():
    x, y = music(12, 3), music(12, 4)
    a = np.concatenate([x, y])
    b = np.concatenate([y, music(3, 5), x])  # the two halves swapped, with a gap between
    segs, _ = align.segments(a, b)
    lags = sorted(round(s.lag, 1) for s in segs if s.length >= 8)
    assert lags == [-12.0, 15.0]


def test_map_time():
    segs = [Segment(0, 10, 2.0, 1), Segment(15, 20, -1.0, 1)]
    assert align.map_time(segs, 5) == 7.0
    assert align.map_time(segs, 10) is None  # end is exclusive
    assert align.map_time(segs, 16) == 15.0
    assert align.map_time([], 1) is None


@pytest.mark.parametrize("speed", [1.0, 1.005, 0.995, 1.01])
def test_speed_ratio_recovers_speed(song, speed):
    longer = np.concatenate([song, music(10, 6)])
    b = longer if speed == 1.0 else librosa.resample(longer, orig_sr=SR, target_sr=SR / speed)
    b = np.concatenate([np.zeros(SR, np.float32), b])
    assert align.speed_ratio(longer, b, Segment(0, 20, 1.0, 1)) == pytest.approx(speed, abs=1.5e-3)


def test_speed_ratio_short_segment_is_one(song):
    assert align.speed_ratio(song, song, Segment(0, 6, 0.0, 1)) == 1.0


def test_runs_and_gaps():
    times = np.arange(0, 10, 0.5)
    mask = (times >= 2) & (times < 6)
    score = np.where(mask, 0.9, 0.1)
    runs = align._runs(times, mask, score, 1.0, 12.0, 13.0)
    assert len(runs) == 1
    assert (runs[0].a0, runs[0].a1, runs[0].score) == (2.0, 5.5 + align.WIN_S, pytest.approx(0.9))
    assert align._gaps(times, mask, min_len=1.0) == [(0.0, 2.0), (6.0, 9.5)]
    # A run that starts at the first window runs to where B starts.
    edge = align._runs(times, times < 3, score, -0.5, 12.0, 13.0)
    assert edge[0].a0 == 0.5
