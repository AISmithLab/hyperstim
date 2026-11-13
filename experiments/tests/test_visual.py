import math

import cv2
import numpy as np
import pytest

import visual as vis
from align import Segment


def texture(seed: int, size=(90, 160)) -> np.ndarray:
    """A smooth random gray image (blobs with edges), uint8."""
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 256, (size[0] // 10, size[1] // 10)).astype(np.uint8)
    return cv2.resize(small, size[::-1], interpolation=cv2.INTER_NEAREST)


def rgb(seed: int, size=(90, 160)) -> np.ndarray:
    return np.stack([texture(seed, size), texture(seed + 1, size), texture(seed + 2, size)], axis=2)


def fake_embed(images, size=(392, 224), batch=32):
    """Stands in for DINOv2: zero-mean, L2-normalised pixels of a small copy."""
    x = np.stack([cv2.resize(im, (16, 9), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
                  for im in images])
    x -= x.mean(axis=1, keepdims=True)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


@pytest.fixture(autouse=True)
def no_dino(monkeypatch):
    def fail():
        raise AssertionError("tests must not load DINOv2")
    monkeypatch.setattr(vis, "_dino", fail)


def test_shifts_reproducible_and_in_range():
    s = vis.shifts(20)
    assert np.array_equal(s, vis.shifts(20))
    assert not np.array_equal(s, vis.shifts(20, seed=1))
    assert np.all((np.abs(s) >= 3) & (np.abs(s) <= 30))
    assert (s > 0).any() and (s < 0).any()


def test_dhash_and_hash_similarity():
    a = rgb(1)
    h = vis.dhash(a)
    assert h.shape == (64,) and h.dtype == bool
    assert vis.hash_similarity(h, vis.dhash(a)) == 1.0
    assert vis.hash_similarity(h, vis.dhash(np.clip(a.astype(int) + 20, 0, 255).astype(np.uint8))) == 1.0
    assert vis.hash_similarity(h, ~h) == 0.0
    assert vis.hash_similarity(h, vis.dhash(rgb(10))) < 0.8


def test_ssim():
    a, b = texture(1), texture(2)
    assert vis.ssim(a, a) == pytest.approx(1.0)
    assert vis.ssim(a, b) < 0.5
    noisy = np.clip(a + np.random.default_rng(0).normal(0, 10, a.shape), 0, 255).astype(np.uint8)
    assert vis.ssim(a, b) < vis.ssim(a, noisy) < 1.0
    full = vis.ssim(a, b, full=True)
    assert full.shape == a.shape and full.mean() == pytest.approx(vis.ssim(a, b))


def test_edges():
    img = np.zeros((60, 80), np.uint8)
    img[:, 40:] = 200
    e = vis.edges(img)
    assert e.shape == img.shape and e.dtype == np.uint8
    assert e[:, 38:42].max() > 0 and e[:, :30].max() == 0 and e[:, 50:].max() == 0
    assert vis.edges(np.full((60, 80), 90, np.uint8)).max() == 0


def scenes(starts: list[int], n: int, seed: int = 0) -> np.ndarray:
    """Gray frames: a new texture at each start, a slow drift and noise in between."""
    rng = np.random.default_rng(seed)
    out, scene = [], None
    for i in range(n):
        if i in starts or scene is None:
            scene = texture(seed + 7 * i).astype(np.float32)
        out.append(np.clip(scene + i % 5 + rng.normal(0, 1, scene.shape), 0, 255).astype(np.uint8))
    return np.stack(out)


def test_frame_diff_and_cuts():
    fps = 10.0
    starts = [20, 35, 70]
    frames = scenes(starts, 100)
    d = vis.frame_diff(frames)
    assert d.shape == (100,) and d[0] == 0
    assert vis.cuts(d, fps).tolist() == starts
    assert vis.cuts(vis.frame_diff(scenes([], 50)), fps).tolist() == []


def test_cuts_at_least_0_3_s_apart():
    d = np.ones(60)
    d[[10, 12, 30]] = [100, 90, 100]  # 12 is 0.2 s after 10
    assert vis.cuts(d, 10.0).tolist() == [10, 30]


def test_cut_match():
    fps = 10.0
    segs = [Segment(0, 10, 2.0, 1)]
    cuts_a = np.array([10, 50, 120])  # 12 s is outside the matched part
    cuts_b = np.array([30, 71])       # A's 1 s -> B's 3 s; A's 5 s -> 7 s (71: within 1 frame)
    share, n = vis.cut_match(cuts_a, cuts_b, segs, fps)
    assert (share, n) == (1.0, 2)
    assert vis.cut_match(cuts_a, cuts_b, segs, fps, shift=5.0)[0] == 0.0
    assert vis.cut_match(cuts_a, np.array([], int), segs, fps)[0] == 0.0
    assert math.isnan(vis.cut_match(cuts_a, cuts_b, [], fps)[0])


def test_flow_curves_camera_pan():
    base = texture(3, (120, 200))
    frames = np.stack([base[10:100, 10 + 2 * i:170 + 2 * i] for i in range(5)])  # view moves right
    f = vis.flow_curves(frames)
    assert set(f) == {"dx", "dy", "magnitude", "object"}
    assert f["dx"][0] == 0
    assert np.allclose(f["dx"][1:], -2, atol=0.5) and np.allclose(f["dy"][1:], 0, atol=0.5)
    assert not vis.flow_map(frames[0], frames[0]).any()


def test_curve_corr():
    fps = 10.0
    rng = np.random.default_rng(0)
    ca = rng.normal(size=100)
    cb = np.concatenate([rng.normal(size=20), ca])  # B = A delayed 2 s
    segs = [Segment(0, 10, 2.0, 1)]
    assert vis.curve_corr(ca, cb, segs, fps) == pytest.approx(1.0)
    assert abs(vis.curve_corr(ca, cb, segs, fps, shift=3.0)) < 0.5
    assert math.isnan(vis.curve_corr(np.ones(100), cb, segs, fps))  # flat curve
    assert math.isnan(vis.curve_corr(ca, cb, [Segment(0, 0.5, 2.0, 1)], fps))  # too few points


def test_sample_pairs():
    segs = [Segment(1, 3, 0.5, 1)]
    pairs = vis.sample_pairs(segs, 5.0, 10.0, n_b=30, rate=2.0)
    assert pairs == [(1.0, 10, 15), (1.5, 15, 20), (2.0, 20, 25)]  # B frame 30 is past B's end
    assert vis.sample_pairs(segs, 5.0, 10.0, n_b=100, rate=2.0, shift=-10.0) == []


def test_structure():
    a = np.stack([texture(1), texture(2)])
    s = vis.structure(a, a, [(0.0, 0, 0), (0.5, 1, 0), (1.0, 5, 0)])
    assert s["gray_ssim"][0] == pytest.approx(1.0) and s["edge_ssim"][0] == pytest.approx(1.0)
    assert s["gray_ssim"][1] < 0.5
    assert np.isnan(s["gray_ssim"][2]) and np.isnan(s["edge_ssim"][2])  # A frame past its end


def test_thumbnail_similarity():
    a = rgb(1)
    e = fake_embed([a])[0]
    assert vis.thumbnail_similarity(a, a, e, e) == {"embedding": pytest.approx(1.0), "hash": 1.0}


def test_load_image(tmp_path):
    p = tmp_path / "x.png"
    cv2.imwrite(str(p), np.zeros((4, 6), np.uint8))
    im = vis.load_image(p)
    assert im.shape == (4, 6, 3) and im.dtype == np.uint8


def test_storyboard_format_and_frames():
    info = {"formats": [{"format_note": "storyboard", "width": 48},
                        {"format_note": "storyboard", "width": 160}, {"format_note": "360p", "width": 640}]}
    assert vis.storyboard_format(info)["width"] == 160
    assert vis.storyboard_format({"formats": []}) is None
    fmt = {"width": 16, "height": 9, "rows": 2, "columns": 3}
    sheet = np.zeros((18, 48, 3), np.uint8)
    for k in range(6):
        r, c = divmod(k, 3)
        sheet[r * 9:(r + 1) * 9, c * 16:(c + 1) * 16] = k
    partial = sheet[:9]  # the last sheet: one row filled
    times, tiles = vis.storyboard_frames(fmt, [sheet, partial], duration=8.5)
    assert times.tolist() == list(range(9))
    assert [int(t[0, 0, 0]) for t in tiles] == [0, 1, 2, 3, 4, 5, 0, 1, 2]
    times, tiles = vis.storyboard_frames(fmt, [sheet], duration=30.0)  # long video: 5 s per tile
    assert times.tolist() == [0, 5, 10, 15, 20, 25] and len(tiles) == 6


def test_storyboard_signal_finds_offset(monkeypatch):
    monkeypatch.setattr(vis, "embed", fake_embed)
    n, offset = 60, 4
    # One storyboard tile a second; the "video" changes scene every few seconds.
    scene_of = np.random.default_rng(0).integers(0, 1000, n + offset)
    scene_of = np.repeat(scene_of[::3], 3)[:n + offset]
    frames = [rgb(int(s)) for s in scene_of]
    frames_a = frames[offset:]  # A starts `offset` s into B: B time = A time + offset
    frames_b = [cv2.resize(f, (80, 45)) for f in frames[:n]]  # B's tiles are smaller
    t = np.arange(n, dtype=float)
    s = vis.storyboard_signal(t, frames_a, t, frames_b, audio_lag=4.0)
    assert s["lag"] == offset and s["audio_lag"] == 4.0
    assert s["embedding"] > 0.95 > s["baseline_median"]
    assert s["edge_ssim"] > 0.5 and s["step_s"] == 1.0
    assert len(s["offsets"]["lags"]) == len(s["offsets"]["scores"]) == 121
    assert all(x["t_b"] == x["t_a"] + offset for x in s["sequence"])
    cuts_a = s["rough_cuts_a"]
    assert cuts_a and {c + offset for c in cuts_a if c + offset < n} <= set(s["rough_cuts_b"])


def test_embed_batches_and_normalises(monkeypatch):
    calls = []

    def model(x):  # (n, 3, h, w) -> per-channel means
        calls.append(tuple(x.shape))
        return x.mean(dim=(2, 3)) + 3

    monkeypatch.setattr(vis, "_dino", lambda: model)
    out = vis.embed(np.stack([rgb(s) for s in range(5)]), size=(28, 14), batch=2)
    assert calls == [(2, 3, 14, 28), (2, 3, 14, 28), (1, 3, 14, 28)]
    assert out.shape == (5, 3) and np.allclose(np.linalg.norm(out, axis=1), 1)


def test_embed_of_no_images_is_empty():
    # A pair whose versions barely align (e.g. one at 2x speed) has no frames to compare.
    assert vis.embed([]).shape == (0, 384)


def test_frame_alignment_finds_the_offset_of_shared_frames():
    # B is A's frames 10..39 with a new start: B time = A time - 5 s at 2 frames a second.
    rng = np.random.default_rng(0)
    ea = rng.normal(size=(40, 16))
    ea /= np.linalg.norm(ea, axis=1, keepdims=True)
    noise = rng.normal(size=(6, 16))
    eb = np.vstack([noise / np.linalg.norm(noise, axis=1, keepdims=True), ea[10:40]])
    seg = vis.frame_alignment(ea, eb, 2.0, 20.0, 18.0)
    assert seg.lag == pytest.approx(-2.0)  # A frame 10 (5 s) is B frame 6 (3 s)
    assert seg.a0 == pytest.approx(2.0) and seg.a1 == pytest.approx(20.0)
    assert seg.score > 0.8  # 30 of the 36 overlapping frames match


def test_frame_alignment_without_frames():
    assert vis.frame_alignment(np.zeros((0, 4)), np.zeros((3, 4)), 2.0, 1.0, 1.5) is None


def test_frame_overlap_counts_only_matching_frames():
    # B shares A's frames 40..119 (40 s) at lag -10 s; the rest of each is something else.
    rng = np.random.default_rng(1)

    def unit(n):
        x = rng.normal(size=(n, 16))
        return x / np.linalg.norm(x, axis=1, keepdims=True)

    ea = unit(200)
    eb = np.vstack([unit(20), ea[40:120], unit(100)])
    seg = vis.frame_alignment(ea, eb, 2.0, 100.0, 100.0)
    assert seg.lag == pytest.approx(-10.0)
    # A window matches once a few of its frames are shared, and counts its middle 5 s: each edge
    # can add up to 5 s.
    assert 40.0 <= vis.frame_overlap(ea, eb, 2.0, seg) <= 50.0
    assert vis.frame_overlap(unit(200), unit(200), 2.0, seg) < 20.0  # chance matches only


def test_frame_overlap_holds_through_repeated_scenes_and_drift():
    # A re-skin of a song whose verse scene repeats: B is A recolored (noise), and frame by frame the
    # repeats look as alike as the match. Its second half is also re-timed 1 s later.
    rng = np.random.default_rng(2)

    def unit(x):
        return x / np.linalg.norm(x, axis=1, keepdims=True)

    verse = rng.normal(size=(16, 16))
    parts = []
    for _ in range(6):   # verse, then a short unique bridge, six times
        parts += [verse + 0.3 * rng.normal(size=verse.shape), rng.normal(size=(8, 16))]
    ea = unit(np.vstack(parts))                                   # 144 frames, 72 s
    eb = unit(np.vstack([ea[:72], ea[70:]]) + 0.08 * rng.normal(size=(146, 16)))
    seg = vis.Segment(0.0, 72.0, 0.0, 0.9)
    assert vis.frame_overlap(ea, eb, 2.0, seg) >= 0.8 * 72.0
