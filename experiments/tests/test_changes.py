import cv2
import numpy as np
import pytest

import changes as chg
from align import Segment


def scene() -> np.ndarray:
    """A gray background with a red square and a blue disc (RGB uint8, 90 x 160)."""
    im = np.full((90, 160, 3), 120, np.uint8)
    im[20:60, 20:60] = (220, 30, 30)
    cv2.circle(im, (115, 45), 22, (30, 60, 220), -1)
    return im


def test_pair_change_identical():
    a = scene()
    ch = chg.pair_change(a, a.copy(), np.zeros(a.shape[:2], bool))
    assert not ch["changed"].any() and not ch["reshaped"].any() and not ch["recolored"].any()
    assert ch["delta_e"].max() == pytest.approx(0)


def test_pair_change_recolored_vs_reshaped():
    a = scene()
    b = a.copy()
    b[20:60, 20:60] = (230, 200, 30)  # the square turns yellow: recolored, same shape
    ch = chg.pair_change(a, b, np.zeros(a.shape[:2], bool))
    inner = (slice(28, 52), slice(28, 52))
    assert ch["changed"][inner].all() and ch["recolored"][inner].all()
    assert not ch["changed"][:, 80:].any()
    c = a.copy()
    cv2.circle(c, (115, 45), 22, (120, 120, 120), -1)
    c[30:60, 95:135] = (30, 60, 220)  # the disc becomes a rectangle: reshaped along its edges
    ch = chg.pair_change(a, c, np.zeros(a.shape[:2], bool))
    assert ch["reshaped"][:, 80:].sum() > 50 and not ch["changed"][:, :70].any()
    assert not (ch["reshaped"] & ch["recolored"]).any()
    assert ((ch["reshaped"] | ch["recolored"]) == ch["changed"]).all()


def test_mask_image():
    a = scene()
    ch = {k: np.zeros(a.shape[:2], bool) for k in ("recolored", "reshaped")}
    ch["recolored"][0, 0] = ch["reshaped"][0, 1] = True
    out = chg.mask_image(a, ch)
    assert out.shape == a.shape and out.dtype == np.uint8
    assert out[0, 0, 0] > out[0, 0, 2] and out[0, 1, 2] > out[0, 1, 1]  # amber, magenta tints
    assert out[50, 150].max() == out[50, 150].min() < 120 * 0.5  # the rest dimmed to gray


def test_hue_hist():
    red = np.zeros((10, 10, 3), np.uint8)
    red[...] = (255, 0, 0)
    h = chg.hue_hist(red)
    assert h.sum() == pytest.approx(1) and h[0] == pytest.approx(1)
    assert chg.hue_hist(np.full((10, 10, 3), 128, np.uint8)).sum() == pytest.approx(0)  # gray: no hue


def test_palette_finds_dominant_colors():
    im = np.zeros((40, 40, 3), np.uint8)
    im[:30] = (200, 40, 40)
    im[30:] = (40, 40, 200)
    p = chg.palette([im], k=2)
    assert [round(x["share"], 2) for x in p] == [0.75, 0.25]
    rgb = [tuple(int(p[i]["hex"][j:j + 2], 16) for j in (1, 3, 5)) for i in range(2)]
    assert np.allclose(rgb[0], (200, 40, 40), atol=6) and np.allclose(rgb[1], (40, 40, 200), atol=6)
    assert p == chg.palette([im], k=2)  # seeded


def test_color_summary():
    a = scene()
    b = cv2.cvtColor((cv2.cvtColor(a, cv2.COLOR_RGB2HSV) * np.array([1, 0.5, 1])).astype(np.uint8),
                     cv2.COLOR_HSV2RGB)  # half the saturation
    s = chg.color_summary([a, a], [b, b])
    assert s["saturation_diff"] < 0 and s["saturation_b"] == pytest.approx(s["saturation_a"] / 2, rel=0.05)
    assert s["delta_e_mean"] > 0 and len(s["delta_e_curve"]) == 2
    same = chg.color_summary([a], [a])
    assert same["delta_e_mean"] == 0 and same["hue_hist_overlap"] == pytest.approx(1)
    assert same["lightness_diff"] == 0 and len(same["palette_a"]) == 6


def test_area_summary():
    z = np.zeros((2, 4), bool)

    def ch(changed, reshaped, moving):
        c = {"changed": z.copy(), "reshaped": z.copy(), "moving": z.copy()}
        c["changed"].flat[changed] = True
        c["reshaped"].flat[reshaped] = True
        c["moving"].flat[moving] = True
        c["recolored"] = c["changed"] & ~c["reshaped"]
        return c

    s = chg.area_summary([ch([0, 1, 2], [0], [0, 1]), ch([], [], [])])
    assert s["changed"] == 3 / 16 and s["reshaped"] == 1 / 16 and s["recolored"] == 2 / 16
    assert s["moving_share"] == 2 / 16
    assert s["moving"] == {"changed": 1.0, "recolored": 0.5, "reshaped": 0.5}
    assert s["still"]["changed"] == 1 / 14
    assert s["changed_curve"] == [3 / 8, 0.0]
    assert np.isnan(chg.area_summary([ch([0], [], [])])["moving"]["changed"])  # nothing moves


def test_only_parts():
    segs = [Segment(5, 20, 3.0, 1), Segment(25, 30, -2.0, 1)]
    p = chg.only_parts(segs, 32.0, 30.0)
    assert p["only_a"] == [[0.0, 5], [20, 25], [30, 32.0]]
    assert p["only_b"] == [[0.0, 8.0], [28.0, 30.0]]  # B 23-28 holds A's 25-30
    assert p["matched_a"] == [[5, 20], [25, 30]] and p["matched_b"] == [[8.0, 23.0], [23, 28]]
    assert chg.only_parts([Segment(0.5, 10, 0, 1)], 10.4, 10.0)["only_a"] == []  # < 1 s gaps


def test_moving_mask():
    g = np.stack([np.zeros((9, 16), np.uint8)] * 2)
    m = chg.moving_mask(g, 0, (32, 18))
    assert m.shape == (18, 32) and m.dtype == bool and not m.any()
    assert not chg.moving_mask(g, 1, (32, 18)).any()
