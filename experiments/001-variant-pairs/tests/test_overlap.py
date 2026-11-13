import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import overlap  # noqa: E402

from align import Segment  # noqa: E402


def test_shared_s_counts_each_second_of_the_shorter_video_once():
    # B (a 60 s song) plays three times in A (a compilation): A 0-60, 100-160 and 200-260 all map
    # onto B 0-60. On B's clock that is 60 s, not 180 s.
    segs = [Segment(0, 60, 0, 1), Segment(100, 160, -100, 1), Segment(200, 260, -200, 1)]
    assert overlap.shared_s(segs, on_b=True) == 60
    assert overlap.shared_s(segs) == 180


def test_shared_s_merges_overlapping_spans():
    assert overlap.shared_s([Segment(0, 30, 5, 1), Segment(20, 50, 5, 1), Segment(70, 80, 0, 1)]) == 60


def test_align_pair_share_never_exceeds_the_shorter_video(monkeypatch):
    segs = [Segment(0, 60, 0, 1), Segment(100, 160, -100, 1), Segment(200, 260, -200, 1)]
    monkeypatch.setattr(overlap.align, "segments", lambda ya, yb: (segs, None))
    sr = overlap.align.SR
    r = overlap.align_pair(None, None, [0] * (300 * sr), [0] * (60 * sr))
    assert r["audio_share"] == 1.0 and r["share"] == 1.0
