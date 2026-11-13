"""Downloads for the search on another machine (PLAN.md, Search, filter 6): the laptop side.

    python3 remote_download.py --server USER@HOST --remote-dir DIR [--out DIR] [--gap 5-20]

Needs only Python 3.10+, yt-dlp, deno and ffmpeg on this machine and an SSH login to the server.
Every minute it fetches DIR/todo.txt (the videos still needed, most important first) from the
server, downloads the next one it hasn't tried (≤ 360p with audio plus its info JSON, the same
settings as tools/yt.py), and an upload thread copies finished videos to DIR/inbox/ with rsync
(files appear there only when complete) and deletes them here. A small random gap between
downloads stays friendly to YouTube. Stops after 5 failed downloads in a row (likely a block);
a failed video is tried once more at the end. Ends when the todo list is done.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

FORMAT = "18/best[height<=360][acodec!=none]"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX_FAILS_IN_A_ROW = 5


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def fetch_todo(server: str, remote: str, out: Path) -> list[str]:
    dst = out / "todo.txt"
    subprocess.run(["rsync", "-q", f"{server}:{remote}/todo.txt", str(dst)], check=True)
    return [ln.strip() for ln in dst.read_text().splitlines() if ln.strip()]


def download(v: str, out: Path) -> bool:
    ytdlp = shutil.which("yt-dlp") or "yt-dlp"
    cmd = [ytdlp, "--no-playlist", "--format", FORMAT, "--write-info-json",
           "--output", str(out / "partial" / v) + ".%(ext)s", "--retries", "3", "--socket-timeout", "30",
           "--remote-components", "ejs:github", "--user-agent", UA, "--", v]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    mp4, info = out / "partial" / f"{v}.mp4", out / "partial" / f"{v}.info.json"
    if res.returncode != 0 or not mp4.exists() or not info.exists():
        lines = [ln for ln in res.stderr.splitlines() if ln.strip()]
        log(f"{v}: failed: {lines[-1] if lines else res.returncode}")
        return False
    (out / "ready").mkdir(exist_ok=True)
    info.replace(out / "ready" / info.name)   # info first: the server imports a video once both are in
    mp4.replace(out / "ready" / mp4.name)
    return True


def uploader(server: str, remote: str, out: Path, stop: threading.Event) -> None:
    ready = out / "ready"
    while True:
        files = sorted(ready.glob("*")) if ready.exists() else []
        if files:
            res = subprocess.run(["rsync", "-q", "--remove-source-files", *map(str, files),
                                  f"{server}:{remote}/inbox/"],
                                 capture_output=True, text=True, check=False)
            if res.returncode == 0:
                log(f"uploaded {len(files) // 2} videos")
            else:
                log(f"upload failed, retrying: {res.stderr.strip()[-200:]}")
        elif stop.is_set():
            return
        time.sleep(15)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="SSH login of the server, e.g. user@host")
    ap.add_argument("--remote-dir", required=True, help="the server's experiments/cache/remote folder")
    ap.add_argument("--out", type=Path, default=Path("variant-downloads"))
    ap.add_argument("--gap", default="5-20", help="random seconds between downloads, min-max")
    args = ap.parse_args()
    lo, hi = (float(x) for x in args.gap.split("-"))
    (args.out / "partial").mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    up = threading.Thread(target=uploader, args=(args.server, args.remote_dir, args.out, stop), daemon=True)
    up.start()
    tried: dict[str, int] = {}
    succeeded: set[str] = set()
    fails_in_a_row, waits = 0, 0
    while True:
        todo = fetch_todo(args.server, args.remote_dir, args.out)
        left = [v for v in todo if v not in succeeded]
        nxt = [v for v in left if tried.get(v, 0) == 0] or [v for v in left if tried.get(v, 0) == 1]
        if not nxt:
            pending = [v for v in todo if v in succeeded]
            if not pending or waits >= 30:  # nothing left, or the server stopped importing
                break
            log(f"waiting for the server to import {len(pending)} uploaded videos")
            waits += 1
            time.sleep(60)
            continue
        v = nxt[0]
        tried[v] = tried.get(v, 0) + 1
        if download(v, args.out):
            succeeded.add(v)
            fails_in_a_row = 0
            log(f"{v}: ok ({len(succeeded)} done, {len(left) - 1} left)")
        else:
            fails_in_a_row += 1
            if fails_in_a_row >= MAX_FAILS_IN_A_ROW:
                log(f"stopping: {fails_in_a_row} failed downloads in a row (blocked?)")
                break
        time.sleep(random.uniform(lo, hi))
    stop.set()
    up.join()
    log(f"done: {len(succeeded)} downloaded")
    sys.exit(0 if fails_in_a_row < MAX_FAILS_IN_A_ROW else 1)


if __name__ == "__main__":
    main()
