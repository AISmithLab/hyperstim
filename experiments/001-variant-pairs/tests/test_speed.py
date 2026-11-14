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


def test_facts_list_mentions_missing_downloads_only_while_there_are_some():
    assert "<b>1</b> candidate video not downloaded" in speed.facts_list(7, 6, 1)
    done = speed.facts_list(7, 6, 0)
    assert "not downloaded" not in done and "Every candidate downloaded and checked" in done


def test_report_jobs_take_each_copys_best_original_and_its_first_loop():
    res = {"fast": [
        {"fast": "F", "parts": [{"cand": "O", "pixel_diff": 3.0, "from_s": 0.0, "to_s": 82.0}]},
        {"fast": "L", "parts": [{"cand": "O", "pixel_diff": 2.0, "from_s": 82.0, "to_s": 164.0},
                                {"cand": "O", "pixel_diff": 3.0, "from_s": 0.0, "to_s": 82.0}]},
        {"fast": "U", "parts": []}]}
    jobs = speed.report_jobs(res)
    assert jobs == [{"name": "Spd-O-F", "a": "O", "b": "F", "end_s": None},
                    {"name": "Spd-O-L", "a": "O", "b": "L", "end_s": 82.0}]
    assert "first 82 s" in speed.report_note(jobs[1]) and "slowed to 1x" in speed.report_note(jobs[0])
    assert "further apart than they are" in speed.report_note(jobs[0])


def test_report_videos_pair_the_1x_video_with_the_slowed_copy():
    done = {"Spd-O-F": {"name": "Spd-O-F", "a": "O", "b": "F", "end_s": None}}
    assert speed.report_videos(done, {"O": "/_blob/o", "F": "/_blob/f", "F.1x": "/_blob/f1"}) == {
        "Spd-O-F": {"a": "/_blob/o", "b": "/_blob/f1"}}
    assert speed.report_videos(done, {}) == {"Spd-O-F": {"a": None, "b": None}}


def test_reports_block_adds_all_versions_only_for_a_group():
    num = {"O": 1, "F": 2, "G": 3}
    reps = [{"name": "Spd-O-F", "a": "O", "b": "F"}, {"name": "Spd-O-G", "a": "O", "b": "G"}]
    html = speed.reports_block(1, "Pink", num, reps, True)
    assert "group.html#g=1" in html and "#1 → #3" in html and html.count("<li>") == 3
    assert "group.html" not in speed.reports_block(1, "Pink", num, reps[:1], False)
    assert speed.reports_block(1, "Pink", num, [], False) == ""


def test_family_section_escapes_the_name_once():
    html = speed.family_section(1, "K71QjqJlAI0", "Bao's Bus", "a < b", "line", "<table></table>")
    assert "Bao&#x27;s Bus</h2>" in html and "&amp;#x27;" not in html
    assert "a &lt; b" in html and html.endswith("<table></table></section>")


def test_reports_block_escapes_the_name_once():
    reps = [{"name": "Spd-K71QjqJlAI0-LXMGLr9uFv4", "b": "LXMGLr9uFv4"}]
    html = speed.reports_block(1, "Bao's Bus", {"K71QjqJlAI0": 1, "LXMGLr9uFv4": 2}, reps, False)
    assert "Bao&#x27;s Bus" in html and "&amp;#x27;" not in html
