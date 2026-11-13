import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import report_selection as rs  # noqa: E402


def db(pairs, overlaps):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE videos (id, published)")
    con.execute("CREATE TABLE pairs (a, b, type, label, confidence, score)")
    con.execute("CREATE TABLE overlap (a, b, source, audio_share, frame_share, share, dur_a, dur_b)")
    vids = sorted({v for p in pairs for v in p[:2]})
    con.executemany("INSERT INTO videos VALUES (?,?)",
                    [(v, f"2015-01-{i + 1:02d}") for i, v in enumerate(vids)])
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?)", pairs)
    con.executemany("INSERT INTO overlap VALUES (?,?,?,?,?,?,?,?)",
                    [o if len(o) == 8 else (*o, 100.0, 100.0) for o in overlaps])
    return con


def test_groups_need_main_content_overlap_and_reports_span_each_group():
    con = db([("a", "b", "AxA", "re-skin", 0.9, 20), ("b", "c", "AxA", "re-skin", 0.9, 19),
              ("a", "c", "AxA", "re-skin", 0.9, 18), ("c", "d", "AxA", "re-skin", 0.9, 17),
              ("e", "f", "AxA", "re-skin", 0.9, 16), ("g", "h", "AxA", "same-song", 0.8, 5),
              ("i", "j", "AxA", "unrelated", 0.9, 1)],
             [("a", "b", "audio", 0.99, None, 0.99), ("b", "c", "audio", 0.95, None, 0.95),
              ("a", "c", "frames", 0.1, 0.7, 0.7),
              ("c", "d", "audio", 0.04, 0.05, 0.05)])  # c-d shares 2-3 s; e-f isn't aligned yet
    groups, sel = rs.build(con)
    skin = groups["re-skin"]
    assert [g["videos"] for g in skin["groups"]] == [["a", "b", "c"]]
    assert [(p["a"], p["b"]) for p in skin["little_shared"]] == [("c", "d")]
    assert [(p["a"], p["b"]) for p in skin["waiting"]] == [("e", "f")]
    # Every version against the earliest (a), where labelled: n - 1 reports.
    assert [(p["a"], p["b"]) for p in sel] == [("a", "b"), ("a", "c")]
    # Labels without an overlap check group as they are; unrelated isn't listed.
    assert groups["same-song"]["groups"][0]["videos"] == ["g", "h"]
    assert "unrelated" not in groups


def test_a_compilation_holding_a_version_is_contained_not_linked():
    # x (400 s) holds all of a (100 s), but that's a quarter of x: a compilation, not a re-skin.
    con = db([("a", "b", "AxA", "re-skin", 0.9, 20), ("x", "a", "AxA", "re-skin", 0.9, 19),
              ("b", "c", "AxA", "re-skin", 0.9, 18), ("a", "c", "AxA", "re-skin", 0.9, 17)],
             [("a", "b", "audio", 0.99, None, 0.99, 100.0, 110.0),
              ("x", "a", "audio", 1.0, None, 1.0, 400.0, 100.0),
              ("b", "c", "audio", 0.95, None, 0.95, 110.0, 105.0),
              ("a", "c", "frames", 0.0, 0.45, 0.45, 100.0, 105.0)])
    skin = rs.build(con)[0]["re-skin"]
    assert [g["videos"] for g in skin["groups"]] == [["a", "b", "c"]]
    assert [(p["a"], p["b"]) for p in skin["contained"]] == [("x", "a")]
    assert skin["contained"][0]["long_share"] == 0.25
    # a-c shares under half, but a and c are in one group through b: not listed apart.
    assert skin["little_shared"] == []
