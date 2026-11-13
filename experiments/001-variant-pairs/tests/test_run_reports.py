import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_reports  # noqa: E402


def test_steps_pass_ids_after_double_dash(monkeypatch, tmp_path):
    # A video ID can start with "-" (e.g. -QG7hoU3k0g): it must not be read as an option.
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(run_reports, "LOG", tmp_path / "reports.tsv")
    monkeypatch.setattr(run_reports, "ROOT", tmp_path)
    monkeypatch.setattr(run_reports, "log_event", lambda msg: None)
    monkeypatch.setattr(run_reports.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or Done())
    run_reports.run_pair("-QG7hoU3k0g", "U3O9WIfjY8A", "AxA", 0)
    for cmd in calls[:2]:
        assert cmd[-3:] == ["--", "-QG7hoU3k0g", "U3O9WIfjY8A"]
    assert "ok" in (tmp_path / "reports.tsv").read_text()


def test_log_gains_memory_columns_and_keeps_old_rows(monkeypatch, tmp_path):
    log = tmp_path / "reports.tsv"
    log.write_text("at\tname\tstate\tall_signals\tprepare_s\tscore_s\treport_s\tnote\n"
                   "t0\tAxA-a-b\tok\t0\t10\t20\t5\t\n")
    monkeypatch.setattr(run_reports, "LOG", log)
    run_reports.write_log("AxA-c-d", "ok", False, {"prepare": 1, "score": 2, "report": 3}, "",
                          {"score": 1234.4})
    lines = log.read_text().splitlines()
    assert lines[0] == run_reports.COLUMNS and lines[1].startswith("t0\tAxA-a-b\tok")
    assert lines[2].split("\t")[8:] == ["", "1234", ""]
    assert run_reports.done_names() == {"AxA-a-b", "AxA-c-d"}


def test_peak_mb_reads_time_output(tmp_path):
    f = tmp_path / "t"
    f.write_text("Command exited with non-zero status 1\n2097152\n")
    assert run_reports.peak_mb(f) == 2048
    assert run_reports.peak_mb(tmp_path / "missing") is None


def test_needed_puts_re_skins_first_and_skips_downloaded(monkeypatch, tmp_path):
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE pairs (a, b, label, confidence, score)")
    con.executemany("INSERT INTO pairs VALUES (?,?,?,?,?)", [
        ("u1", "u2", "re-upload", 0.9, 30), ("s1", "s2", "re-skin", 0.9, 10),
        ("s2", "s3", "re-skin", 0.9, 20),
        ("x1", "x2", "re-skin", 0.5, 99), ("s4", "have", "re-skin", 0.8, 5)])
    monkeypatch.setattr(run_reports.yt, "video_path",
                        lambda v: tmp_path / ("have" if v == "have" else "no") / v)
    (tmp_path / "have").mkdir()
    (tmp_path / "have" / "have").write_text("")
    assert run_reports.needed(con) == ["s2", "s3", "s1", "s4", "u1", "u2"]


def test_stage_rates():
    assert run_reports.stage("6b overlap", 50, 200, 40) == {
        "stage": "6b overlap", "done": 50, "of": 200, "pct_done": 25.0, "passed": 40, "pct_passed": 80.0}
    assert run_reports.stage("6 download", 0, 0)["pct_done"] == 100.0
