import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import search  # noqa: E402


def test_compilations_by_length_and_title():
    assert not search.is_compilation("Five Little Ducks | 3D Rhyme", 94)
    assert not search.is_compilation("Wheels on the Bus", 25 * 60)  # long, but under 30 min
    assert search.is_compilation("Wheels on the Bus", 31 * 60)
    assert search.is_compilation("Finger Family Collection | Nursery Rhymes", 322)
    assert search.is_compilation("1 Hour of Kids Songs", 200)
    assert not search.is_compilation("123 Songs For Babies", 180)


def test_pair_types():
    assert search.pair_type("A", "B") == search.pair_type("B", "A") == "AxB"
    assert search.pair_type("A", "A") == "AxA"
    assert search.pair_type("B", "B") == "BxB"


def test_crop_bars_trims_letterbox_only():
    img = np.full((360, 480, 3), 120, np.uint8)
    img[:45] = 0
    img[-45:] = 0
    assert search.crop_bars(img).shape == (270, 480, 3)
    dark = np.zeros((360, 480, 3), np.uint8)  # an all-dark frame loses at most a quarter each side
    assert search.crop_bars(dark).shape[0] >= 180


def test_outline_ignores_color_but_not_shape():
    rng = np.random.default_rng(0)
    base = np.zeros((270, 480, 3), np.uint8)
    for _ in range(12):
        x, y = rng.integers(0, 420), rng.integers(0, 220)
        base[y:y + 40, x:x + 50] = rng.integers(40, 255, 3)
    recolored = base[..., ::-1].copy()  # same shapes, swapped channels
    other = np.roll(base, 120, axis=1)
    o = search.outline_vector
    assert o(base) @ o(recolored) > 0.9
    assert o(base) @ o(other) < 0.5
    assert np.linalg.norm(o(base)) == pytest.approx(1, abs=1e-5)


def test_title_index_ignores_boilerplate():
    idx = search.TitleIndex({"a": "Five Little Ducks | Nursery Rhymes for Kids",
                             "b": "Five Little Ducks | Kids Channel 3D Songs",
                             "c": "Wheels on the Bus | Nursery Rhymes for Kids"})
    s = idx.sims("a", ["b", "c"])
    assert s[0] > 0.9 and s[1] < 0.2


def test_closer_than_both_directions():
    vals = np.sort(np.array([0.1, 0.2, 0.3, 0.4]))
    assert search.closer_than(vals, 0.35, False) == 0.75
    assert search.closer_than(vals, 0.15, True) == 0.75   # distance: smaller is closer
    assert search.closer_than(vals, float("nan"), False) == 0.0


def test_screen_score_rewards_one_rare_signal_and_caps():
    assert search.screen_score({"x": 0.0, "y": 0.0}, 100) == 0.0
    one = search.screen_score({"x": 0.999, "y": 0.5}, 10_000)
    assert one == pytest.approx(3 + np.log10(2))
    capped = search.screen_score({"x": 1.0}, 99)
    assert capped == pytest.approx(2.0)


def test_duration_fit_allows_an_end_screen():
    assert search.duration_fit(118, 94) == 0.0
    assert search.duration_fit(200, 100) == 70.0
