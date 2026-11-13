import numpy as np
import pytest
from test_align import music

import audio
from align import SR, Segment


@pytest.fixture(scope="module")
def song():
    return music(16, 1)


def test_aligned_cuts_to_the_overlap():
    a = np.arange(10 * SR, dtype=float)
    b = np.arange(12 * SR, dtype=float) - 2 * SR  # B time = A time + 2
    xa, xb = audio._aligned(a, b, Segment(1, 9, 2.0, 1))
    assert len(xa) == 8 * SR and np.array_equal(xa, xb)
    xa, xb = audio._aligned(b, a, Segment(0, 9, -2.0, 1))  # lag points before B's start: clipped
    assert xa[0] == 0 and np.array_equal(xa, xb)


def test_gain_db():
    x = np.random.default_rng(0).standard_normal(1000)
    assert audio.gain_db(x, 2 * x) == pytest.approx(6.0206, abs=1e-3)
    assert audio.gain_db(x, x) == pytest.approx(0)


def test_window_curve_and_null(song):
    b = np.concatenate([np.zeros(SR, np.float32), song])
    segs = [Segment(0, 16, 1.0, 1)]
    times, c = audio.window_curve(song[:, None], b[:, None], segs, 16.0, SR)
    assert times.tolist() == list(range(14)) and np.nanmin(c) > 0.999
    _, shifted = audio.window_curve(song[:, None], b[:, None], segs, 16.0, SR, shift=0.3)
    assert np.nanmax(np.abs(shifted)) < 0.5
    _, none = audio.window_curve(song[:, None], b[:, None], [], 16.0, SR)
    assert np.isnan(none).all()
    null = audio.shifted_null(song[:, None], b[:, None], segs, 16.0, SR, n=4)
    assert not np.isnan(null).any() and np.abs(null).max() < 0.5


def test_longest_run():
    times = np.arange(10.0)
    curve = np.array([0.9, 0.9, 0.1, 0.9, 0.9, 0.9, np.nan, 0.9, 0.2, 0.2])
    assert audio.longest_run(times, curve, 0.5) == (3.0, 5.0 + audio.WIN, 2.0 + audio.WIN)
    assert audio.longest_run(times, np.zeros(10), 0.5) == (0.0, 0.0, 0.0)


def test_fingerprint_match_recovers_offset(song):
    b = np.concatenate([music(3, 7), song])
    fa, fb = audio.fingerprint(song), audio.fingerprint(b)
    m = audio.fingerprint_match(fa, fb)
    assert m["offset_s"] == pytest.approx(3.0, abs=512 / SR)
    other = audio.fingerprint_match(fa, audio.fingerprint(music(16, 9)))
    assert m["share"] > 0.3 > 10 * other["share"]
    assert audio.fingerprint_match({}, fb) == {"share": 0.0, "offset_s": None}


def test_stems_reads_cache(tmp_path, monkeypatch):
    np.savez_compressed(tmp_path / "abc.stems.npz", vocals=np.ones(3), drums=np.zeros(3))
    monkeypatch.setattr("builtins.__import__", _no_demucs(__import__))
    s = audio.stems(tmp_path / "abc.mp4", tmp_path)
    assert set(s) == {"vocals", "drums"} and s["vocals"].tolist() == [1, 1, 1]


def _no_demucs(real):
    def imp(name, *args, **kwargs):
        if name.startswith("demucs"):
            raise AssertionError("tests must not load demucs")
        return real(name, *args, **kwargs)
    return imp


def stems_of(y: np.ndarray, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    parts = {k: 0.25 * y for k in ("drums", "bass", "other")}
    parts["vocals"] = 0.1 * rng.standard_normal(len(y)).astype(np.float32)
    return parts


def test_analyze_levels():
    song = music(10, 1)
    segs = [Segment(0, 10, 0.0, 1)]
    st = stems_of(song, 1)
    same = audio.analyze(song, song.copy(), segs, st, st, 1.0)
    assert same["level"] == "exact" and same["waveform_corr"] == pytest.approx(1)
    assert same["gain_db"] == pytest.approx(0, abs=1e-6)
    assert [lv["key"] for lv in same["levels"]] == ["exact", "adjusted", "backing", "rerecorded"]
    assert same["levels"][0]["longest"][2] > 8
    assert set(same["curves"]) == {"times", "waveform", "spectrum", "chroma", "backing", "vocals"}

    louder = audio.analyze(song, 2 * song, segs, st, {k: 2 * v for k, v in st.items()}, 1.0)
    assert louder["level"] == "adjusted" and louder["gain_db"] == pytest.approx(6.02, abs=0.01)

    # Same backing, a different voice on top that drowns the waveform match.
    voice_a, voice_b = (music(10, s) for s in (11, 12))
    ya, yb = 0.3 * song + voice_a, 0.3 * song + voice_b
    sa = {"drums": 0.1 * song, "bass": 0.1 * song, "other": 0.1 * song, "vocals": voice_a}
    sb = {**sa, "vocals": voice_b}
    backing = audio.analyze(ya, yb, segs, sa, sb, 1.0)
    assert backing["level"] == "backing" and backing["backing_corr"] == pytest.approx(1)

    other = music(10, 5)
    unrelated = audio.analyze(song, other, segs, st, stems_of(other, 2), 1.0)
    assert unrelated["level"] == "none"


def test_analyze_a_silent_track_holds_no_level(song):
    # One version with its soundtrack muted (seen in the search): no baseline, no level, no crash.
    silent = np.zeros_like(song)
    r = audio.analyze(song, silent, [Segment(0.0, len(song) / SR, 0.0, 1.0)], None, None, 1.0)
    assert not any(lv["holds"] for lv in r["levels"] if lv["key"] in ("exact", "adjusted"))
