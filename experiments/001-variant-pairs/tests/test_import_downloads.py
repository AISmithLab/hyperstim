import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import import_downloads as imp  # noqa: E402


def test_imports_complete_readable_videos_and_sets_bad_ones_aside(monkeypatch, tmp_path):
    inbox, cache = tmp_path / "inbox", tmp_path / "video"
    monkeypatch.setattr(imp, "INBOX", inbox)
    monkeypatch.setattr(imp, "REJECTED", tmp_path / "rejected")
    monkeypatch.setattr(imp.yt, "video_path", lambda v: cache / f"{v}.mp4")
    logged, events = [], []
    monkeypatch.setattr(imp.yt, "log", lambda *a: logged.append(a))
    monkeypatch.setattr(imp, "log_event", events.append)

    def probe(p):
        if "bad" in p.name:
            raise RuntimeError("moov atom not found")
        return {}

    monkeypatch.setattr(imp.media, "probe", probe)
    inbox.mkdir()
    for v in ("-ok1", "bad"):
        (inbox / f"{v}.mp4").write_text("x")
        (inbox / f"{v}.info.json").write_text("{}")
    (inbox / "half.info.json").write_text("{}")  # its mp4 isn't in yet
    assert imp.run_once() == ["-ok1"]
    assert (cache / "-ok1.mp4").exists() and (cache / "-ok1.info.json").exists()
    assert (tmp_path / "rejected" / "bad.mp4").exists() and (inbox / "half.info.json").exists()
    assert logged == [(imp.EXP, "player-elsewhere", "download", "-ok1", 0, "ok",
                       "downloaded on another machine")]


def test_todo_is_replaced_whole(monkeypatch, tmp_path):
    monkeypatch.setattr(imp, "REMOTE", tmp_path)
    monkeypatch.setattr(imp, "TODO", tmp_path / "todo.txt")
    imp.write_todo(["a", "-b"])
    assert (tmp_path / "todo.txt").read_text() == "a\n-b\n"
