import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import speed  # noqa: E402


def test_fast_titles():
    assert speed.is_fast_title("Wheels on the Bus - Kids Song - X2 Speed Bus Song")
    assert speed.is_fast_title("Wheels On The Bus - 2x speed #shorts")
    assert not speed.is_fast_title("Mozart for Babies: Fall Asleep Fast")
    assert not speed.is_fast_title("Wheels on the Bus | 3x2 blocks")


def test_to_1x_doubles_the_aligned_time():
    # the candidate at 2x is lag seconds ahead: 2x time 10 s with lag 1.5 is 1x time 23 s
    assert speed.to_1x(10.0, 1.5) == 23.0 and speed.to_1x(0.0, 0.0) == 0.0


def test_parts_split_a_looped_video_and_keep_a_short_tail_with_the_last():
    assert speed.parts(490, 164) == [(0, 164), (164, 328), (328, 490)]
    assert speed.parts(400, 164) == [(0, 164), (164, 400)]     # a 72-frame tail joins the last part
    assert speed.parts(100, 164) == [(0, 100)]


def test_song_is_the_titles_first_four_words():
    assert speed.song("Wheels On The Bus | Baby Bao Panda") == "wheels on the bus"
    assert speed.song("Wheels on the Bus Christmas Ride") == "wheels on the bus"


def test_families_group_2x_videos_by_their_original_and_count_loops():
    res = {"fast": [
        {"fast": "f1", "parts": [{"cand": "o1", "pixel_diff": 3.0, "from_s": 0}]},
        {"fast": "f2", "parts": [{"cand": "o1", "pixel_diff": 2.0, "from_s": 0},
                                 {"cand": "o1", "pixel_diff": 3.0, "from_s": 82},
                                 {"cand": "o1", "pixel_diff": 3.0, "from_s": 164}]},
        {"fast": "f3", "parts": [], "closest": [], "unchecked": ["x"]},
        {"fast": "f4", "parts": [], "waiting": True}]}
    fams = speed.families(res)
    assert fams[0] == {"orig": "o1", "fast": ["f1", "f2"], "loops": {"f1": 1, "f2": 3}}
    assert fams[1]["orig"] is None and fams[1]["unchecked"] == ["x"] and fams[2]["waiting"]


def test_family_summary_compares_views_with_the_original():
    vids = {"o": {"views": 1_000_000}, "f": {"views": 2_500_000}, "g": {"views": 500_000}}
    line = speed.family_summary(["f", "g"], "o", vids, {"g": 3})
    assert line == ("1x: 1,000,000 views · 2x: 2,500,000 views (2.5× the original's) · "
                    "2x, played 3 times in a row: 500,000 views (50% of the original's)")
    assert speed.family_summary(["f"], None, vids, {}) == "2x: 2,500,000 views"


def test_ratio_text_switches_to_percent_below_one():
    assert speed.ratio_text(9.74) == "9.7× the original's"
    assert speed.ratio_text(468539 / 51789932) == "1% of the original's"


def test_best_diff_takes_the_closest_frame_nearby():
    a = np.full((2, 2, 3), 100.0)
    near = np.stack([np.full((2, 2, 3), 160.0), np.full((2, 2, 3), 103.0), np.full((2, 2, 3), 40.0)])
    assert speed.best_diff(a, near) == 3.0
    assert speed.best_diff(a, near[:0]) is None


def test_inside_later_flags_a_later_or_longer_1x_video():
    vids = {"f": {"duration": 97, "published": "2024-12-13"},
            "orig": {"duration": 190, "published": "2023-01-01"},
            "comp": {"duration": 638, "published": "2023-01-01"},
            "later": {"duration": 190, "published": "2025-12-17"}}
    assert not speed.inside_later("orig", ["f"], vids)
    assert speed.inside_later("comp", ["f"], vids)
    assert speed.inside_later("later", ["f"], vids)


def test_family_summary_leaves_out_the_ratio_when_not_comparable():
    vids = {"o": {"views": 1_000_000}, "f": {"views": 2_500_000}}
    line = speed.family_summary(["f"], "o", vids, {}, compare=False)
    assert line == "1x: 1,000,000 views · 2x: 2,500,000 views"
