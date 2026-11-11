import math

import numpy as np
import pytest

import baselines as bl


@pytest.fixture(autouse=True)
def no_youtube(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("tests must not reach YouTube")
    for name in ("api", "image", "download"):
        monkeypatch.setattr(bl.yt, name, fail)


def rows_for(n_channels=20, per=15, song_every=5):
    rows = {}
    for c in range(n_channels):
        for i in range(per):
            v = f"v{c:02d}{i:02d}"
            title = "Five Little Ducks | Kids" if i % song_every == 0 else f"Song {c} {i}"
            rows[v] = {"video_id": v, "title": title, "channel_id": f"ch{c:02d}", "duration_s": "120",
                       "published_at": "2020-01-01T00:00:00Z"}
    return rows


def test_threshold_strictest_per_set():
    rng = np.random.default_rng(0)
    vals = {"random": list(rng.uniform(0, 1, 200)),
            "same_song": list(rng.uniform(0, 2, 200)) + [None, np.nan]}
    t = bl.threshold(vals, True, 1.5)
    assert t["per_set"]["same_song"]["n"] == 200
    assert t["per_set"]["random"]["p99"] == pytest.approx(np.percentile(vals["random"], 99))
    assert t["threshold"] == t["per_set"]["same_song"]["p99"] > 1.9
    assert t["fires"] is False and not t["weak_baseline"]
    assert t["per_set"]["random"]["closer_than"] == 1.0
    assert t["per_set"]["same_song"]["closer_than"] == pytest.approx(0.75, abs=0.06)
    assert sum(t["per_set"]["random"]["hist"]["counts"]) == 200


def test_threshold_distances_use_p1():
    vals = {"a": list(range(1, 101)), "b": list(range(50, 150))}
    t = bl.threshold(vals, False, 0.5)
    assert t["threshold"] == pytest.approx(np.percentile(range(1, 101), 1))
    assert t["fires"] is True and t["per_set"]["a"]["closer_than"] == 1.0
    assert bl.threshold(vals, False, 30)["fires"] is False


def test_threshold_weak_baseline_under_30_pairs():
    """PLAN.md: a set under 30 pairs is shown with its size but sets no threshold."""
    vals = {"big": [0.1] * 40, "small": [0.9] * 29}
    t = bl.threshold(vals, True, 0.5)
    assert t["per_set"]["small"]["n"] == 29 and t["weak_baseline"]
    assert t["threshold"] == pytest.approx(0.1) and t["fires"] is True
    only_small = bl.threshold({"small": [0.1] * 10}, True, 0.5)
    assert only_small["threshold"] is None and only_small["fires"] is None and only_small["weak_baseline"]
    assert not bl.threshold({"big": [0.1] * 30}, True, 0.5)["weak_baseline"]


def test_threshold_without_value_or_data():
    t = bl.threshold({"a": [0.1] * 50}, True)
    assert t["fires"] is None and "closer_than" not in t["per_set"]["a"]
    assert bl.threshold({"a": [0.1] * 50}, True, float("nan"))["fires"] is None
    empty = bl.threshold({"a": [], "b": [None]}, True, 0.5)
    assert empty["per_set"] == {} and empty["threshold"] is None and empty["fires"] is None


def test_hist_covers_value():
    h = bl._hist(np.array([1.0, 2.0, 3.0]), 10.0, bins=3)
    assert (h["lo"], h["hi"]) == (1.0, 10.0) and h["counts"] == [3, 0, 0]
    flat = bl._hist(np.array([2.0, 2.0]), None)
    assert flat["hi"] > flat["lo"] and sum(flat["counts"]) == 2


def test_fires():
    th = {"threshold": 0.5, "higher_is_closer": True}
    assert bl.fires(0.6, th) is True and bl.fires(0.4, th) is False
    assert bl.fires(0.4, {**th, "higher_is_closer": False}) is True
    assert bl.fires(None, th) is None and bl.fires(math.nan, th) is None
    assert bl.fires(0.6, {**th, "threshold": None}) is None


def test_has_run():
    assert bl.has_run("5 Little Ducks (3D)", ["five", "little", "ducks"])
    assert not bl.has_run("Little Five Ducks", ["five", "little", "ducks"])


def test_sample_sets():
    rows = rows_for()
    kw = {"n_random": 50, "n_channels": 4, "per_channel": 5}
    sets = bl.sample_sets(rows, ["five", "little", "ducks"], {"ch00"}, **kw)
    assert len(sets["same_song"]) == 19 * 3 and all(not v.startswith("v00") for v in sets["same_song"])
    assert all(bl.has_run(rows[v]["title"], ["five", "little", "ducks"]) for v in sets["same_song"])
    assert len(sets["random"]) == len(set(sets["random"])) == 50
    assert not set(sets["random"]) & set(sets["same_song"])
    assert len(sets["same_channel"]) == 20 and len({rows[v]["channel_id"] for v in sets["same_channel"]}) == 4
    assert sets == bl.sample_sets(rows, ["five", "little", "ducks"], {"ch00"}, **kw)  # seeded


def test_pairs_for():
    rows = rows_for()
    sets = {"same_song": ["v0100", "v0105", "v0200"], "random": ["v0301", "v0302", "v0401"],
            "same_channel": ["v0501", "v0502", "v0601"]}
    p = bl.pairs_for(sets, rows, ("A", "B"), same_owner={"v0200"})
    assert p["same_song"] == [("A", "v0100"), ("A", "v0105"), ("B", "v0100"), ("B", "v0105")]  # same channel
    assert p["random"] == [("v0301", "v0401"), ("v0302", "v0401")]
    assert p["same_channel"] == [("v0501", "v0502")]
    capped = bl.pairs_for({**sets, "random": [f"v{c:02d}01" for c in range(20)]}, rows, ("A", "B"), set(),
                          max_pairs=10)
    assert len(capped["random"]) == 10


def test_dataset_pairs():
    rows = rows_for()
    p = bl.dataset_pairs(rows, ["five", "little", "ducks"], {"ch00"}, {"ch01"}, n=100)
    ch = lambda v: rows[v]["channel_id"]  # noqa: E731
    assert len(p["same_song"]) == 18 * 3 * 17 * 3 // 2
    assert all(ch(x) != ch(y) and "ch01" not in (ch(x), ch(y)) for x, y in p["same_song"])
    assert len(p["random"]) == len(p["same_channel"]) == 100
    assert all(ch(x) != ch(y) for x, y in p["random"]) and all(ch(x) == ch(y) and x != y
                                                               for x, y in p["same_channel"])
    assert all("ch00" not in (ch(x), ch(y)) for ps in p.values() for x, y in ps)


def test_load_dataset(tmp_path, monkeypatch):
    a, b = tmp_path / "a.tsv", tmp_path / "b.tsv"
    a.write_text("video_id\ttitle\nx\told\ny\tY\n")
    b.write_text("video_id\ttitle\nx\tnew\n")
    monkeypatch.setattr(bl, "DATASET", [a, b])
    assert bl.load_dataset() == {"x": {"video_id": "x", "title": "new"}, "y": {"video_id": "y", "title": "Y"}}


def test_snippets_batches_of_50(monkeypatch):
    calls = []

    def api(endpoint, params, experiment, note, target=""):
        ids = params["id"].split(",")
        calls.append((endpoint, len(ids), target))
        return {"items": [{"id": v} for v in ids if v != "gone"]}

    monkeypatch.setattr(bl.yt, "api", api)
    ids = [f"v{i:03d}" for i in range(120)] + ["v000", "gone"]
    out = bl.snippets(ids, "001", "test")
    assert [c[1] for c in calls] == [50, 50, 21] and calls[0][2] == "50 videos from gone"
    assert len(out) == 120 and out["v007"] == {"id": "v007"}


def test_thumbnail_url(monkeypatch):
    seen = []
    monkeypatch.setattr(bl.yt, "image", lambda *a: seen.append(a) or None)
    assert bl.thumbnail("abc", "001", "n") is None
    assert seen == [("https://i.ytimg.com/vi/abc/hqdefault.jpg", "001", "thumbnail", "abc", "n")]
