"""Downloads made on another machine (PLAN.md, Search, filter 6): the inbox side.

    uv run python 001-variant-pairs/import_downloads.py      # once; run_reports.py runs it every 30 s

The other machine runs remote_download.py with cache/remote/todo.txt and copies each
<id>.mp4 and <id>.info.json into cache/remote/inbox/ (rsync: a file appears only when complete).
Each video whose two files are in and whose mp4 reads is moved into the cache and recorded in the
ledger as kind "player-elsewhere": not this server's player request, so it doesn't count against
the day's budget here. A file that doesn't read goes to cache/remote/rejected/.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

from search import DB, EXP, log_event  # noqa: E402

import media  # noqa: E402
import yt  # noqa: E402

REMOTE = ROOT / "cache" / "remote"
INBOX = REMOTE / "inbox"
REJECTED = REMOTE / "rejected"
TODO = REMOTE / "todo.txt"


def write_todo(ids: list[str]) -> None:
    REMOTE.mkdir(parents=True, exist_ok=True)
    tmp = TODO.with_suffix(".tmp")
    tmp.write_text("".join(f"{v}\n" for v in ids))
    tmp.replace(TODO)


def run_once() -> list[str]:
    """Moves every complete, readable video from the inbox into the cache; returns their IDs."""
    INBOX.mkdir(parents=True, exist_ok=True)
    done = []
    for info in sorted(INBOX.glob("*.info.json")):
        v = info.name.removesuffix(".info.json")
        mp4 = INBOX / f"{v}.mp4"
        if not mp4.exists():
            continue
        dest = yt.video_path(v)
        try:
            media.probe(mp4)
        except Exception as e:  # noqa: BLE001 - any unreadable file is set aside
            REJECTED.mkdir(parents=True, exist_ok=True)
            for f in (mp4, info):
                shutil.move(f, REJECTED / f.name)
            log_event(f"import {v}: rejected ({e})")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():  # already here: keep ours
            mp4.unlink()
            info.unlink()
            continue
        shutil.move(info, dest.parent / info.name)
        shutil.move(mp4, dest)
        yt.log(EXP, "player-elsewhere", "download", v, 0, "ok", "downloaded on another machine")
        log_event(f"import {v}: ok (downloaded elsewhere)")
        done.append(v)
    return done


if __name__ == "__main__":
    import run_reports

    write_todo(run_reports.needed(sqlite3.connect(DB, timeout=120)))
    print(f"{len(run_once())} videos imported")
