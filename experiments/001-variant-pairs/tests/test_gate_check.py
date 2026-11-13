import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gate_check as gc  # noqa: E402


def db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE pairs (a, b, type, score, gate_state, label)")
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?)", [
        ("a", "b", "AxA", 5.0, "stop", None),
        ("c", "a", "AxB", 9.0, "stop", None),
        ("d", "e", "AxA", 7.0, "stop", "unrelated"),   # audited: the agent already saw it
        ("f", "g", "AxA", 8.0, "pass", None),
        ("a", "live", "AxA", 9.5, "stop", None),       # a live stream: nothing to download
    ])
    con.execute("CREATE TABLE videos (id, duration)")
    con.executemany("INSERT INTO videos VALUES (?,?)", [("a", 60), ("b", 60), ("c", 90), ("live", 0)])
    con.execute("CREATE TABLE gate_check (a TEXT, b TEXT, source TEXT, audio_share REAL, frame_share REAL, "
                "share REAL, long_share REAL, lag REAL, dur_a REAL, dur_b REAL, error TEXT, at TEXT)")
    return con


def test_stopped_pairs_unlabelled_highest_score_first():
    assert gc.stopped(db()) == [("c", "a", "AxB"), ("a", "b", "AxA")]


def test_needed_lists_missing_videos_once_in_pair_order(tmp_path, monkeypatch):
    monkeypatch.setattr(gc.yt, "video_path", lambda v: tmp_path / f"{v}.mp4")
    (tmp_path / "a.mp4").touch()
    assert gc.needed([("c", "a", "AxB"), ("a", "b", "AxA"), ("b", "c", "AxA")]) == ["c", "b"]


def test_workers_split_the_work_without_overlap():
    keys = [f"v{i}" for i in range(200)]
    shares = [[k for k in keys if gc.mine(k, w, 3)] for w in range(3)]
    assert sum(map(len, shares)) == 200 and all(len(s) > 30 for s in shares)


def test_cached_embed_computes_once(tmp_path, monkeypatch):
    monkeypatch.setattr(gc, "EMB", tmp_path)
    calls = []

    def fake(p):
        calls.append(p)
        return np.ones((4, 3))

    monkeypatch.setattr(gc.overlap, "embed_frames", fake)
    e1 = gc.cached_embed(Path("/x/vid.mp4"))
    e2 = gc.cached_embed(Path("/x/vid.mp4"))
    assert len(calls) == 1 and e1.dtype == np.float32 and np.array_equal(e1, e2)


def test_stages_count_each_step(tmp_path, monkeypatch):
    monkeypatch.setattr(gc.yt, "video_path", lambda v: tmp_path / f"{v}.mp4")
    monkeypatch.setattr(gc, "EMB", tmp_path / "emb")
    (tmp_path / "emb").mkdir()
    for v in ("a", "b", "c"):
        (tmp_path / f"{v}.mp4").touch()
    for v in ("a", "b"):
        (tmp_path / "emb" / f"{v}.npy").touch()
    con = db()
    con.execute("INSERT INTO gate_check (a, b, share, long_share) VALUES ('a', 'b', 0.9, 0.8)")
    st = gc.stages(con, gc.stopped(con), ["x"])["stages"]
    assert st["downloaded"] == {"done": 3, "of": 3, "pct": 100.0}
    assert st["embedded"]["done"] == 2 and st["pairs_ready"] == {"done": 2, "of": 2, "pct": 100.0}
    assert st["pairs_checked"]["done"] == 1 and st["pairs_passing"] == {"done": 1, "of": 1, "pct": 100.0}


def test_step_checks_ready_pairs_while_videos_still_need_embeddings(tmp_path, monkeypatch):
    # New videos keep arriving: the ready pairs must still get checked, not wait for every embedding.
    monkeypatch.setattr(gc.yt, "video_path", lambda v: tmp_path / f"{v}.mp4")
    monkeypatch.setattr(gc, "EMB", tmp_path / "emb")
    (tmp_path / "emb").mkdir()
    for v in ("a", "b", "c", "d"):
        (tmp_path / f"{v}.mp4").touch()
    for v in ("a", "b"):
        np.save(gc.emb_path(v), np.ones((2, 2)))
    embedded, checked = [], []
    monkeypatch.setattr(gc, "cached_embed", lambda p: embedded.append(p.stem))
    monkeypatch.setattr(gc, "check", lambda con, a, b, t: checked.append((a, b)))
    pairs = [("a", "b", "AxA"), ("c", "d", "AxA")]
    left, ready = gc.step(db(), pairs, 0, 1, set())
    assert (left, ready) == (2, 1) and embedded == ["c"] and checked == [("a", "b")]


def test_finished_only_when_every_video_is_in_and_every_pair_checked():
    def st(todo, checked, errors, pairs):
        return {"todo_for_laptop": todo, "errors": errors, "stages": {
            "pairs_checked": {"done": checked}, "pairs_ready": {"of": pairs}}}
    assert gc.finished(st(0, 9, 1, 10))
    assert not gc.finished(st(0, 8, 1, 10))
    assert not gc.finished(st(3, 10, 0, 10))
