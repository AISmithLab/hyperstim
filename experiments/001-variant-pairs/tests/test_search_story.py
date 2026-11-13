import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import search_story as st  # noqa: E402


def vid(side, title, published, views=100):
    return {"side": side, "title": title, "published": published, "views": views}


VIDS = {
    "a1": vid("A", "Five Little Ducks | Nursery Rhymes", "2014-01-10T00:00:00Z", 900),
    "a2": vid("A", "Five Little Ducks 3D | Kids TV", "2014-12-01T00:00:00Z", 50),
    "b1": vid("B", "Five Little Ducks | Kids Channel", "2014-11-05T00:00:00Z", 300),
    "b2": vid("B", "Wheels on the Bus", "2015-03-01T00:00:00Z", 10),
    "b3": vid("B", "Wheels on the Bus 3D", "2015-03-02T00:00:00Z", 20),
}
ROWS = [("a1", "b1", "AxB", 20.0, "re-skin", 0.9), ("a1", "a2", "AxA", 18.0, "re-skin", 0.8),
        ("b2", "b3", "BxB", 15.0, "re-skin", 0.95),
        ("a2", "b2", "AxB", 9.0, "re-skin", 0.5),   # not confident
        ("a2", "b3", "AxB", 9.0, "same-song", 0.9)]


def test_reskins_keep_confident_ones():
    assert [(p["a"], p["b"]) for p in st.reskins(ROWS)] == [("a1", "b1"), ("a1", "a2"), ("b2", "b3")]


def test_families_are_connected_components():
    fams = st.families(st.reskins(ROWS))
    assert fams == [{"a1", "a2", "b1"}, {"b2", "b3"}]


def test_family_name_uses_common_title_words():
    assert st.family_name([VIDS[v]["title"] for v in ("a1", "a2", "b1")]) == "Five Little Ducks"
    assert st.family_name(["Kids TV", "Nursery Rhymes"]) == "Untitled"


def test_signed_uses_a_true_minus():
    assert st.signed(-782.4) == "−782" and st.signed(5) == "+5"


def test_channel_story_counts():
    page = " ".join(st.channel_story(VIDS, ROWS, {("a1", "b1"): "ducks recolored"}, {}).split())
    assert "1 Kids Channel videos re-skin a Kids TV video" in page
    assert "median +299 days" in page                     # b1 is 299 days after a1
    assert "2 families" in page and "ducks recolored" in page
    assert "<svg" in page and page.count('class="link"') == 3


def test_strategy_profiles_flag_reskins_without_shared_animation():
    def report(anim, level):
        fire = {"fires": anim}
        return {"pair": {"a": "a1", "b": "b1"}, "alignment": {"segments": [], "source": "audio"},
                "videos": {"a1": {"duration_s": 60}, "b1": {"duration_s": 60}},
                "signals": {"metadata": {k: {"fires": False} for k in
                                         ("owner", "timing_days", "title", "description", "tags",
                                          "description_lines", "duration")},
                            "visual": {k: dict(fire) for k in
                                       ("thumbnail_embedding", "thumbnail_hash", "storyboard", "aligned_cuts",
                                        "motion_magnitude", "structure_edges", "frame_content")},
                            "audio": {"level": level},
                            "changes": {"color": {"delta_e_mean": 30},
                                        "area": {"changed": 0.5, "reshaped": 0.4},
                                        "parts": {"only_a": [], "only_b": []}}}}
    labels = {("a1", "b1"): ("re-skin", 0.9)}
    page = st.strategy_profiles([("x", report(True, "adjusted")), ("y", report(False, "none"))], labels)
    page = " ".join(page.split())
    assert "2 pairs have a full report" in page and "1 shows no shared animation" in page
    assert "same animation, same audio, adjusted, new title, recolored, redrawn parts" in page
    assert "data-report='y'" in page


def test_audit_note(tmp_path):
    con = sqlite3.connect(tmp_path / "s.db")
    con.execute("CREATE TABLE pairs (a, b, review, gate_state, label, confidence)")
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?)", [
        ("1", "2", "done", "stop", "re-skin", 0.9), ("3", "4", "done", "stop", "unrelated", 0.9),
        ("5", "6", "audit", "stop", None, None), ("7", "8", "done", "pass", "re-skin", 0.9)])
    note = st.audit_note(con)
    assert "2 reviewed so far, 1 of them confident re-skins; 1 more wait" in note


def test_looks_are_cached(tmp_path):
    import cv2
    import numpy as np

    img = tmp_path / "t.jpg"
    cv2.imwrite(str(img), np.full((90, 160, 3), (0, 0, 255), np.uint8))   # pure red (BGR)
    cache = tmp_path / "look.json"
    out = st.looks({"a1": VIDS["a1"]}, cache, lambda v, k: img)
    sat, light = out["a1"]
    assert sat > 0.95 and 40 < light < 60
    assert json.loads(cache.read_text())["a1"] == [round(sat, 4), round(light, 4)]
    assert st.looks({"a1": VIDS["a1"]}, cache, lambda v, k: None) == out    # read back, no image needed


def test_views_span_leaves_out_the_median_of_two():
    assert st.views_span([1500, 3_000_000]).startswith("1.5k / <span")
    assert st.views_span([1500, 3_000_000]).endswith("/ 3.0M")
    assert st.views_span([1500, 2000, 3_000_000]) == "1.5k / 2.0k / 3.0M"
