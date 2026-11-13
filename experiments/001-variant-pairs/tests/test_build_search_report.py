import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_search_report as base  # noqa: E402


def _db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE pairs (a TEXT, b TEXT, type TEXT, label TEXT, confidence REAL)")
    con.execute("CREATE TABLE overlap (a TEXT, b TEXT, share REAL, dur_a REAL, dur_b REAL)")
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?,?)", [
        ("a1", "b1", "AxB", "re-skin", 0.9),
        ("a2", "b2", "AxB", "re-skin", 0.8),
        ("a9", "b9", "AxB", "re-skin", 0.9),        # b9 is a compilation holding a9
        ("a3", "b3", "AxB", "re-skin", 0.5),        # not confident
        ("a4", "b4", "AxB", "re-upload", 0.9),
        ("a5", "a6", "AxA", "same-song", 0.9),
        ("a7", "a8", "AxA", "unrelated", 0.9),
    ])
    con.executemany("INSERT INTO overlap VALUES (?,?,?,?,?)", [
        ("a1", "b1", 0.9, 100, 100), ("a2", "b2", 0.1, 100, 100), ("a4", "b4", 1.0, 100, 100),
        ("a9", "b9", 1.0, 100, 400)])
    return con


def _prog():
    per = {"AxB": 10, "AxA": 10, "BxB": 10}
    return {"candidates": {"passed": per, "pairs_compared": per, "pairs_total": per},
            "score": {"passed": per}, "gate": {"passed": per, "stopped": per}}


def test_chain_table_counts_re_skins_only(monkeypatch, tmp_path):
    for v in ("a1", "b1", "a2", "b2", "a4", "b4", "a9", "b9"):
        (tmp_path / v).touch()
    monkeypatch.setattr(base.yt, "video_path", lambda v: tmp_path / v)
    groups = {"re-skin": {"groups": [{"videos": ["a1", "b1"], "pairs": [{"type": "AxB"}]}]},
              "re-upload": {"groups": [{"videos": ["a4", "b4"], "pairs": [{"type": "AxB"}]}]}}
    html = base.chain_table(_db(), _prog(), groups)
    for other in ("Re-upload", "Same song", "Same template", "Shared segments", "Unrelated"):
        assert other not in html
    assert "<b>3</b> re-skins" in html                 # stage 5: the three confident re-skins of AxB
    assert "<b>3</b> downloaded" in html               # stage 6: not the re-upload
    assert "<b>1</b> overlap<span>33% of 3 · 1 little shared · 1 contained" in html
    assert "1 re-skin groups of 2 videos" in html


def test_label_cards_link_only_the_re_skin_page():
    groups = {"re-skin": {"groups": [{"videos": ["a", "b", "c"]}], "little_shared": [], "waiting": []},
              "re-upload": {"groups": [{"videos": ["x", "y"]}], "little_shared": [], "waiting": []}}
    html = base.label_cards(groups, {"re-skin": "https://example.org/rs", "re-upload": "https://example.org/ru"})
    assert "https://example.org/rs" in html
    assert "example.org/ru" not in html
    assert "1 groups" in html and "3 videos" in html
