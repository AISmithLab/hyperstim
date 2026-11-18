import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import views_model as vm  # noqa: E402


def test_is_holiday():
    assert vm.is_holiday("Jingle Bells | Christmas Songs for Kids")
    assert vm.is_holiday("HALLOWEEN finger family")
    assert not vm.is_holiday("Five Little Ducks")
    assert not vm.is_holiday("")


def test_days_between():
    assert vm.days_between("2026-01-01T00:00:00Z", "2026-01-11T12:00:00Z") == pytest.approx(10.5)
    assert vm.days_between("2026-01-01T00:00:00Z", "2026-01-02T00:00:00+00:00") == pytest.approx(1)


def _pool(side="A", dur=120.0, ts=range(0, 300, 10), lv=1.0):
    return [{"side": side, "t": float(t), "dur": dur, "lv": lv} for t in ts]


def test_expected_uses_same_channel_and_length_class():
    pool = _pool(lv=2.0) + _pool(side="B", lv=9.0) + _pool(dur=900.0, lv=7.0)
    exp, n, w = vm.expected_log_views({"side": "A", "t": 150.0, "dur": 100.0}, pool, window=50, min_n=5)
    assert exp == 2.0
    assert n == 11  # t = 100 ... 200
    assert w == 50


def test_expected_widens_window_until_enough():
    pool = _pool(ts=[0, 400, 410, 420, 430])
    exp, n, w = vm.expected_log_views({"side": "A", "t": 0.0, "dur": 60.0}, pool, window=100, min_n=5)
    assert (n, w) == (5, 800)
    assert vm.expected_log_views({"side": "A", "t": 0.0, "dur": 60.0}, pool, window=10, min_n=5) is None


def test_split_by_format():
    short = {"a": True, "b": True, "c": False, "d": False, "e": None}
    assert vm.split_by_format(["a", "b", "c", "d", "e"], short) == [["a", "b"], ["c", "d", "e"]]
    assert vm.split_by_format(["a", "c", "d"], short) == [["c", "d"]]  # a lone Short drops out
    assert vm.split_by_format(["a", "c"], short) == []


def test_demean():
    g = np.array([0, 0, 1, 1, 1])
    out = vm.demean(np.array([1.0, 3.0, 5.0, 6.0, 7.0]), g)
    assert np.allclose(out, [-1, 1, -1, 0, 1])


def _families(beta=0.05, n_fam=60, k=3, seed=0, noise=0.3):
    rng = np.random.default_rng(seed)
    groups = np.repeat(np.arange(n_fam), k)
    x = rng.normal(130, 20, len(groups))
    fam_level = rng.normal(0, 3, n_fam)[groups]  # large family effects, absorbed
    y = fam_level + beta * x + rng.normal(0, noise, len(groups))
    return groups, x, y


def test_ols_within_recovers_beta_despite_family_effects():
    groups, x, y = _families()
    b, se = vm.ols_within(y, x[:, None], groups)
    assert b[0] == pytest.approx(0.05, abs=0.005)
    assert 0 < se[0] < 0.01


def test_ols_within_drops_column_constant_within_families():
    groups, x, y = _families()
    const = np.repeat(np.arange(60), 3).astype(float)  # varies only between families
    b, se = vm.ols_within(y, np.column_stack([x, const]), groups)
    assert not np.isnan(b[0]) and np.isnan(b[1]) and np.isnan(se[1])


def test_permutation_p_small_for_effect_large_for_none():
    groups, x, y = _families()
    assert vm.permutation_p(y, x[:, None], 0, groups, n=200) < 0.02
    groups, x, y = _families(beta=0.0, seed=3)
    assert vm.permutation_p(y, x[:, None], 0, groups, n=200) > 0.05


def test_permute_within_keeps_values_inside_families():
    g = np.array([0, 0, 0, 1, 1])
    x = np.array([1.0, 2.0, 3.0, 10.0, 20.0])
    out = vm.permute_within(x, g, np.random.default_rng(0))
    assert sorted(out[:3]) == [1, 2, 3] and sorted(out[3:]) == [10, 20]


def test_holm():
    assert vm.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert vm.holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])  # capped at 1


def test_within_pairs_and_family_weights():
    g = np.array([0, 0, 0, 1, 1])
    assert vm.within_pairs(g) == [(0, 1), (0, 2), (1, 2), (3, 4)]
    assert np.allclose(vm.family_weights(g), [1 / 3, 1 / 3, 1 / 3, 1, 1])


def test_pair_logit_sign_and_offset():
    groups, x, y = _families(beta=0.05, noise=0.5)
    X = x[:, None]
    b = vm.pair_logit(y, np.zeros(len(y)), X, vm.within_pairs(groups))
    assert b[0] > 0
    # if the offset already explains the views, nothing is left for x
    b0 = vm.pair_logit(y, 1000 * 0.05 * x, X, vm.within_pairs(groups))
    assert b0[0] < b[0]


def test_bootstrap_families_relabels():
    g = np.array([0, 0, 1, 1, 1])
    idx, lab = next(vm.bootstrap_families(g, 1, np.random.default_rng(0), size=3))
    assert len(np.unique(lab)) == 3 and len(idx) == len(lab)


def test_fetch_dates_takes_first_file(tmp_path):
    a, b = tmp_path / "videos-a.json", tmp_path / "videos-b.json"
    a.write_text(json.dumps({"items": [{"id": "v1"}, {"id": "v2"}]}))
    b.write_text(json.dumps({"items": [{"id": "v1"}]}))
    os.utime(a, (1_700_000_000, 1_700_000_000))
    os.utime(b, (1_800_000_000, 1_800_000_000))
    (tmp_path / "channels-x.json").write_text(json.dumps({"items": [{"id": "v3"}]}))
    out = vm.fetch_dates(tmp_path)
    assert set(out) == {"v1", "v2"}
    assert out["v1"].startswith("2023-11-14")


def test_aspect_short_missing_file(tmp_path):
    assert vm.aspect_short(tmp_path / "none.mp4") is None


def test_build_rows_marks_later_and_splits_formats():
    vids = {
        "o": {
            "side": "A",
            "title": "Ducks",
            "published": "2015-01-01T00:00:00Z",
            "duration": 120,
            "views": 1000,
            "likes": 1,
            "compilation": 0,
        },
        "r": {
            "side": "A",
            "title": "Ducks Christmas",
            "published": "2016-01-01T00:00:00Z",
            "duration": 120,
            "views": 5000,
            "likes": 1,
            "compilation": 0,
        },
        "s": {
            "side": "A",
            "title": "Ducks",
            "published": "2017-01-01T00:00:00Z",
            "duration": 50,
            "views": 50,
            "likes": 1,
            "compilation": 0,
        },
    }
    for i in range(40):  # the channel's other videos, one every 30 days from 2014
        vids[f"x{i}"] = {
            "side": "A",
            "title": "x",
            "published": f"{2014 + i * 30 // 365}-{1 + (i * 30 % 365) // 31:02d}-01T00:00:00Z",
            "duration": 100,
            "views": 100,
            "likes": 0,
            "compilation": 0,
        }
    data = {
        "vids": vids,
        "fetched": {},
        "feats": {m: {"o": 100.0, "r": 120.0, "s": 90.0} for m, *_ in (*vm.MEASURES, vm.PLACEBO)},
        "fam": {"re-skin": [["o", "r", "s"]], "re-upload": []},
        "short": {"s": True},
    }
    rows = vm.build_rows(data, window=400)["rows"]["re-skin"]
    assert [r["video"] for r in rows] == ["o", "r"]  # the lone Short drops out
    assert [r["later"] for r in rows] == [0, 1]
    assert [r["holiday"] for r in rows] == [False, True]
    assert rows[0]["expected"] == pytest.approx(math.log(100))


def test_page_later_beats_first_and_build(tmp_path):
    import views_page

    rows = [
        {
            "family": "f1",
            "video": "a",
            "title": "A",
            "side": "A",
            "published": "2015-01-01T00:00:00Z",
            "views": 100,
            "expected": math.log(50),
            "short": False,
            "holiday": False,
            "later": 0,
        },
        {
            "family": "f1",
            "video": "b",
            "title": "B </script>",
            "side": "B",
            "published": "2016-01-01T00:00:00Z",
            "views": 300,
            "expected": math.log(100),
            "short": False,
            "holiday": True,
            "later": 1,
        },
        {
            "family": "f1",
            "video": "c",
            "title": "C",
            "side": "A",
            "published": "2017-01-01T00:00:00Z",
            "views": 10,
            "expected": math.log(100),
            "short": False,
            "holiday": False,
            "later": 1,
        },
    ]
    assert views_page.later_beats_first(rows) == (1, 2)
    fams = views_page.families(rows)
    assert [v["video"] for v in fams[0]["versions"]] == ["a", "b", "c"]
    assert fams[0]["versions"][1]["vs_expected"] == pytest.approx(3.0)
    m = {
        "label": "Saturation",
        "per_text": "10 points",
        "views_ratio": 1.2,
        "views_ratio_ci": [0.9, 1.5],
        "p_perm": 0.2,
        "p_holm": 0.6,
        "top_wins": 1,
        "top_families": 1,
        "pair_odds_ratio": 1.1,
        "pair_odds_ci": [0.8, 1.4],
        "n_videos": 3,
        "n_families": 1,
        "measure": "mean_saturation",
        "beta": 0.02,
    }
    res = {
        "measures": [m],
        "placebo": {**m, "label": "Cuts"},
        "noise": {},
        "power": {},
        "robust_window": {},
        "rows": rows,
        "reupload_rows": rows,
        "dropped": {},
        "at": "2026-11-17T00:00:00+00:00",
        "window_days": 90,
        "n_perm": 10,
        "n_boot": 10,
    }
    page = views_page.build(res, tmp_path).read_text()
    assert "{{" not in page
    assert "1 of 2 re-skins" in page
    assert "B <\\/script>" in page  # a title can't close the data block
