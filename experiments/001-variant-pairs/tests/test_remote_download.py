"""Tests for remote_download.py: the laptop side of the downloads."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import remote_download as rd  # noqa: E402


def fake_rsync(outcomes):
    """subprocess.run stand-in: each call takes the next outcome (True = ok, writes the todo file)."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        ok = outcomes[len(calls) - 1]
        if ok:
            Path(cmd[-1]).write_text("a\n\nb\n")
        return subprocess.CompletedProcess(cmd, 0 if ok else 255, "", "" if ok else "Connection closed")
    return run, calls


def test_fetch_todo_retries_a_dropped_connection(monkeypatch, tmp_path):
    run, calls = fake_rsync([False, False, True])
    monkeypatch.setattr(rd.subprocess, "run", run)
    assert rd.fetch_todo("u@h", "/r", tmp_path, wait=0) == ["a", "b"]
    assert len(calls) == 3


def test_fetch_todo_gives_up_after_its_tries(monkeypatch, tmp_path):
    run, calls = fake_rsync([False] * 3)
    monkeypatch.setattr(rd.subprocess, "run", run)
    with pytest.raises(SystemExit, match="3 times"):
        rd.fetch_todo("u@h", "/r", tmp_path, tries=3, wait=0)
    assert len(calls) == 3
