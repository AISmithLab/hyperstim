import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import learn  # noqa: E402


def test_pair_pos_matches_triu_order():
    n = 7
    iu, ju = np.triu_indices(n, 1)
    assert np.array_equal(learn.pair_pos(iu, ju, n), np.arange(len(iu)))
    # order of the two videos doesn't matter
    assert np.array_equal(learn.pair_pos(ju, iu, n), np.arange(len(iu)))


def test_jaccard_matrix():
    m = learn.jaccard_matrix([{"a", "b"}, {"b", "c"}, set(), {"a", "b"}])
    assert m[0, 1] == pytest.approx(1 / 3)
    assert m[0, 3] == pytest.approx(1.0)
    assert m[2, 2] == 0.0  # two empty sets: no evidence, not a match
    assert m[0, 2] == 0.0
    assert np.allclose(m, m.T)


def test_max_dot_takes_best_combination_and_is_symmetric():
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[0.0, 1.0], [0.0, 1.0]])  # video 0's second frame matches video 1's first
    m = learn.max_dot([a, b])
    assert m[0, 1] == pytest.approx(1.0)
    assert np.allclose(m, m.T)


def test_groups_of_connects_chains():
    g = learn.groups_of(6, [(0, 1), (1, 2), (4, 5)])
    assert g[0] == g[1] == g[2]
    assert g[4] == g[5]
    assert len({g[0], g[3], g[4]}) == 3


def test_cut_for_recall_keeps_at_least_the_share():
    s = np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0, -1.0, -2.0, -3.0, -4.0])
    assert learn.cut_for_recall(s, 1.0) == -4.0
    assert learn.cut_for_recall(s, 0.9) == -3.0
    assert learn.cut_for_recall(s, 0.95) == -4.0  # 9.5 of 10 rounds up to all 10
    assert (s >= learn.cut_for_recall(s, 0.5)).sum() == 5


def test_videos_touched():
    assert learn.videos_touched(np.array([0, 0, 3]), np.array([1, 2, 4]), 10) == 5
    assert learn.videos_touched(np.array([], int), np.array([], int), 10) == 0


def test_sample_weights_balance_positives_and_scale_unlabelled():
    cls = np.array([learn.POS, learn.POS, learn.HARD_NEG, learn.UNLABELLED, learn.UNLABELLED])
    w = learn.sample_weights(cls, n_unlabelled_total=1000)
    assert w[3] == w[4] == 500  # two sampled pairs stand for 1,000
    assert w[2] == 1
    assert w[:2].sum() == pytest.approx(w[2:].sum())


def test_clopper_pearson_bounds():
    lo, hi = learn.clopper_pearson(0, 100)
    assert lo == 0.0 and 0.03 < hi < 0.04
    lo, hi = learn.clopper_pearson(5, 100)
    assert lo < 0.05 < hi


def test_tier_table_cuts_on_same_length_reskins_and_reports_medleys():
    n = 5
    iu, ju = np.triu_indices(n, 1)  # 10 pairs
    score = np.arange(10, dtype=np.float32)
    cls = np.zeros(10, np.int8)
    cls[[9, 8]] = learn.POS
    cls[2] = learn.POS
    cls[7] = learn.REUPLOAD
    pos = cls == learn.POS
    medley = np.zeros(10, bool)
    medley[2] = True
    info = {p: {"a": "x", "b": "y"} for p in range(10)}
    rows = learn.tier_table(score, cls, pos, medley, iu, ju, n, info)
    full = next(r for r in rows if r["recall_target"] == 1.0)
    assert full["positives"] == 2 and full["positives_kept"] == 2
    assert full["cut"] == 8.0 and full["pairs_kept"] == 2
    assert full["medley"] == 1 and full["medley_kept"] == 0
    assert full["reuploads_kept"] == 0


def test_group_cost_scales_images_per_video_and_agent_as_a_range():
    c = {"videos_total": 1000, "m": {"videos_needing_images": 1000}, "i": {"videos_needing_gate_frames": 500}}
    agent = {"pairs_reviewed": 100, "download_videos": 30}
    g = learn.group_cost(2000, c, agent)
    assert g["api_units"] == 80  # uploads list + video details, 50 videos a request
    assert g["images"] == 5000  # every thumbnail; three frames for half the videos
    assert g["image_hours"] == pytest.approx(5000 / 3600)
    assert g["agent_pairs"][0] == 200  # per video
    assert g["agent_pairs"][1] == round(100 / 499500 * 1999000)  # per pair
    assert g["sheets"][0] == 20
    assert g["download_videos"] == 60 and g["download_days"] == pytest.approx(1.2)


def test_class_labels_from_search_and_audit(tmp_path, monkeypatch):
    import json
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE pairs (a TEXT, b TEXT, label TEXT, confidence REAL)")
    con.execute("CREATE TABLE overlap (a TEXT, b TEXT, share REAL)")
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?)", [
        ("v0", "v1", "re-skin", 0.9),   # confirmed by overlap -> positive
        ("v0", "v2", "re-skin", 0.9),   # overlap too small -> unsure
        ("v1", "v2", "re-upload", 0.8),
        ("v2", "v3", "same-song", 0.9),
        ("v0", "zz", "re-skin", 0.9),   # video not in the index (a compilation) -> skipped
    ])
    con.executemany("INSERT INTO overlap VALUES (?,?,?)", [("v0", "v1", 0.9), ("v0", "v2", 0.1)])
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "batch-001.json").write_text(json.dumps([
        {"a": "v1", "b": "v3", "label": "re-skin", "confidence": 0.75, "note": "x"},
        {"a": "v0", "b": "v3", "label": "unrelated", "confidence": 0.9},
        {"a": "v0", "b": "v1", "label": "unrelated", "confidence": 0.9},  # search label wins
    ]))
    monkeypatch.setattr(learn, "AUDIT_LABELS", labels)
    index = {f"v{i}": i for i in range(4)}
    pos = {(a, b): int(learn.pair_pos(np.array([index[a]]), np.array([index[b]]), 4)[0])
           for a in index for b in index if a < b}
    cls = learn.class_labels(con, index, 4)["cls"]
    assert cls[pos["v0", "v1"]] == learn.POS
    assert cls[pos["v0", "v2"]] == learn.UNSURE
    assert cls[pos["v1", "v2"]] == learn.REUPLOAD
    assert cls[pos["v2", "v3"]] == learn.HARD_NEG
    assert cls[pos["v1", "v3"]] == learn.AUDIT_POS
    assert cls[pos["v0", "v3"]] == learn.HARD_NEG
    base = learn.class_labels(con, index, 4, with_audit=False)["cls"]
    assert pos["v1", "v3"] not in base and pos["v0", "v3"] not in base
