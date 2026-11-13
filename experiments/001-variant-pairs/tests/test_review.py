import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import review  # noqa: E402


def test_aligned_times_fall_inside_both_videos():
    # B starts 10 s later in its own video (B time = A time + 10): A 0-50 meets B 10-60.
    times = review.aligned_times(100.0, 60.0, 10.0)
    assert len(times) == 4
    for ta, tb in times:
        assert 0 <= ta <= 50 and tb == pytest.approx(ta + 10) and 10 <= tb <= 60
    assert times[0][0] == pytest.approx(10.0) and times[-1][0] == pytest.approx(40.0)


def test_aligned_times_empty_when_the_videos_do_not_meet():
    assert review.aligned_times(30.0, 30.0, 40.0) == []


def test_overlap_of_reads_the_gate_check_and_tolerates_its_absence():
    con = sqlite3.connect(":memory:")
    assert review.overlap_of(con, "a", "b") is None
    con.execute("CREATE TABLE gate_check (a, b, source, audio_share, frame_share, share, long_share, lag, "
                "dur_a, dur_b, error, at)")
    con.execute("INSERT INTO gate_check VALUES ('a','b','audio',0.9,NULL,0.91234,0.8,-2.5,60,70,NULL,'t')")
    want = {"source": "audio", "share_of_shorter": 0.912, "share_of_longer": 0.8, "lag_s": -2.5,
            "dur_a": 60, "dur_b": 70}
    assert review.overlap_of(con, "a", "b") == want
    assert review.overlap_of(con, "b", "a") is None
