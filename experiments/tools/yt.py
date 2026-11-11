"""The only way experiments reach YouTube: checks the budget, then logs one ledger row per request.

Budget (experiments/README.md, YouTube budget):
- API: Data API units per Pacific day, at most EXP_API_UNITS_PER_DAY (default 2000).
- Image: thumbnails and storyboard sprites from YouTube's image servers; logged, not budgeted,
  but paced: one at a time, with a random gap of EXP_IMAGE_GAP seconds (default 0.5-1.5) between
  request starts.
- Player: any yt-dlp call; at most EXP_PLAYER_PER_DAY per UTC day (default 50), one download per
  video ever, and none while the collector is blocked (its `blocked_until`); a random gap of
  EXP_PLAYER_GAP seconds (default 45-135) after each download.

Every response is cached under experiments/cache/ and reused, so a request is never repeated.

Env vars:
- YOUTUBE_API_KEY: Data API key (never commit it).
- COLLECTOR_DATA_DIR: folder of the collector's collector.db, to read `blocked_until`.
- COLLECTOR_USER: if set and collector.db isn't readable, read it through `sudo -n -u` this user.
- YTDLP_COOKIES: optional cookies file for yt-dlp.

Library use: `from yt import api, image, download`. CLI: `python tools/yt.py --help`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent  # experiments/
LEDGER = ROOT / "ledger.tsv"
CACHE = ROOT / "cache"
COLUMNS = ["at", "experiment", "kind", "what", "target", "units", "outcome", "note"]

PLAYER_PER_DAY = int(os.environ.get("EXP_PLAYER_PER_DAY", "50"))


def _gap(name: str, default: str) -> tuple[float, float]:
    lo, hi = (float(x) for x in os.environ.get(name, default).split("-"))
    return lo, hi


# Random gaps (min, max seconds), so requests don't come at a fixed rhythm.
IMAGE_GAP = _gap("EXP_IMAGE_GAP", "0.5-1.5")
PLAYER_GAP = _gap("EXP_PLAYER_GAP", "45-135")
_next_at = {"image": 0.0, "player": 0.0}
API_UNITS_PER_DAY = int(os.environ.get("EXP_API_UNITS_PER_DAY", "2000"))
# Data API costs in units; everything we use is 1 except search.
UNIT_COST = {"search": 100}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class BudgetError(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def _rows() -> list[dict[str, str]]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def log(experiment: str, kind: str, what: str, target: str, units: int, outcome: str, note: str = "") -> None:
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        if new:
            w.writerow(COLUMNS)
        at = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        w.writerow([at, experiment, kind, what, target, units, outcome, note.replace("\t", " ")])


def _at(row: dict[str, str]) -> datetime:
    return datetime.strptime(row["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def player_used_today(now: datetime | None = None) -> int:
    day = (now or now_utc()).date()
    return sum(1 for r in _rows() if r["kind"] == "player" and _at(r).date() == day)


def units_used_today(now: datetime | None = None) -> int:
    pacific = ZoneInfo("America/Los_Angeles")
    day = (now or now_utc()).astimezone(pacific).date()
    return sum(int(r["units"] or 0) for r in _rows()
               if r["kind"] == "API" and _at(r).astimezone(pacific).date() == day)


def collector_blocked_until() -> float:
    """The collector's `blocked_until` (epoch seconds). Raises if it can't be read: no download
    without knowing the server isn't blocked."""
    data_dir = os.environ.get("COLLECTOR_DATA_DIR")
    if not data_dir:
        raise BudgetError("COLLECTOR_DATA_DIR is not set: can't check whether the collector is blocked")
    db = Path(data_dir) / "collector.db"
    query = "SELECT value FROM kv WHERE key = 'blocked_until'"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = con.execute(query).fetchone()
        return float(row[0]) if row else 0.0
    except sqlite3.Error as e:
        user = os.environ.get("COLLECTOR_USER")
        if not user:
            raise BudgetError(f"can't read {db}; set COLLECTOR_USER to read it through sudo") from e
    code = (f"import sqlite3; c = sqlite3.connect({f'file:{db}?mode=ro'!r}, uri=True); "
            f"r = c.execute({query!r}).fetchone(); print(r[0] if r else 0)")
    out = subprocess.run(["sudo", "-n", "-u", user, "python3", "-I", "-c", code],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise BudgetError(f"can't read {db} as {user}: {out.stderr.strip()}")
    return float(out.stdout.strip() or 0)


# --- API --------------------------------------------------------------------------------


def api(endpoint: str, params: dict[str, str], experiment: str, note: str = "",
        target: str = "") -> dict:
    """One Data API GET (e.g. api("videos", {"id": "a,b", "part": "snippet"}, "001")).
    Cached by endpoint and params; a cached response costs nothing and isn't logged."""
    key = "&".join(f"{k}={params[k]}" for k in sorted(params))
    target = target or params.get("id") or params.get("channelId") or params.get("playlistId") or key
    digest = hashlib.sha1(f"{endpoint}?{key}".encode()).hexdigest()[:12]
    path = CACHE / "api" / f"{endpoint}-{_safe(target)[:80]}-{digest}.json"
    if path.exists():
        return json.loads(path.read_text())
    units = UNIT_COST.get(endpoint, 1)
    used = units_used_today()
    if used + units > API_UNITS_PER_DAY:
        raise BudgetError(f"API budget: {used} of {API_UNITS_PER_DAY} units used today (Pacific)")
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise BudgetError("YOUTUBE_API_KEY is not set")
    url = (f"https://www.googleapis.com/youtube/v3/{endpoint}?"
           + urllib.parse.urlencode({**params, "key": api_key}))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(experiment, "API", endpoint, target, units, f"error {e.code}", note)
        raise
    log(experiment, "API", endpoint, target, units, "ok", note)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


# --- Image ------------------------------------------------------------------------------


def _wait(kind: str) -> None:
    """Sleep until the random gap after this process's last request of this kind has passed."""
    time.sleep(max(0.0, _next_at[kind] - time.monotonic()))


def image(url: str, experiment: str, what: str, target: str, note: str = "") -> Path | None:
    """One file from YouTube's image servers (thumbnail, storyboard sprite); None on a 404."""
    ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
    path = CACHE / "img" / f"{_safe(target)}-{hashlib.sha1(url.encode()).hexdigest()[:12]}{ext}"
    missing = path.with_suffix(".404")
    if path.exists():
        return path
    if missing.exists():
        return None
    _wait("image")
    _next_at["image"] = time.monotonic() + random.uniform(*IMAGE_GAP)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            path.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        log(experiment, "image", what, target, 0, f"error {e.code}", note)
        if e.code == 404:
            missing.touch()
            return None
        raise
    log(experiment, "image", what, target, 0, "ok", note)
    return path


# --- Player -----------------------------------------------------------------------------


def video_path(video_id: str) -> Path:
    return CACHE / "video" / f"{video_id}.mp4"


def download(video_id: str, experiment: str, note: str = "") -> Path:
    """The whole video at ≤ 360p with audio, plus its info JSON (storyboard URLs included), in
    one player request. At most once per video, ever."""
    out = video_path(video_id)
    if out.exists():
        return out
    if any(r["kind"] == "player" and r["what"] == "download" and r["target"] == video_id
           and r["outcome"] == "ok" for r in _rows()):
        raise BudgetError(f"{video_id} was downloaded before but isn't in the cache: never twice")
    used = player_used_today()
    if used >= PLAYER_PER_DAY:
        raise BudgetError(f"player budget: {used} of {PLAYER_PER_DAY} used today (UTC)")
    blocked = collector_blocked_until()
    if blocked > time.time():
        until = datetime.fromtimestamp(blocked, UTC).isoformat(timespec="minutes")
        raise BudgetError(f"the collector is blocked by YouTube until {until}")
    ytdlp = shutil.which("yt-dlp") or str(Path(sys.executable).parent / "yt-dlp")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ytdlp, "--no-playlist", "--format", "18/best[height<=360][acodec!=none]",
           "--write-info-json", "--output", str(out.with_suffix("")) + ".%(ext)s",
           "--retries", "3", "--socket-timeout", "30", "--remote-components", "ejs:github",
           "--user-agent", UA, f"https://www.youtube.com/watch?v={video_id}"]
    if os.environ.get("YTDLP_COOKIES"):
        cmd[1:1] = ["--cookies", os.environ["YTDLP_COOKIES"]]
    _wait("player")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    _next_at["player"] = time.monotonic() + random.uniform(*PLAYER_GAP)
    ok = res.returncode == 0 and out.exists()
    last_error = next((ln for ln in reversed(res.stderr.splitlines()) if "ERROR" in ln), "")
    log(experiment, "player", "download", video_id, 0, "ok" if ok else "error",
        note if ok else f"{note}; {last_error[:200]}".strip("; "))
    if not ok:
        raise RuntimeError(f"download failed: {last_error or res.stderr[-500:]}")
    return out


def info(video_id: str) -> dict:
    """The info JSON written with the download (no request)."""
    return json.loads((CACHE / "video" / f"{video_id}.info.json").read_text())


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_," else "_" for c in s).replace(",", "_")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="today's use of both budgets and the collector's block")
    d = sub.add_parser("download", help="download one video (one player request)")
    d.add_argument("video_id")
    d.add_argument("--experiment", required=True)
    d.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "status":
        print(f"player requests today (UTC): {player_used_today()} of {PLAYER_PER_DAY}")
        print(f"API units today (Pacific): {units_used_today()} of {API_UNITS_PER_DAY}")
        try:
            b = collector_blocked_until()
            state = "blocked until " + datetime.fromtimestamp(b, UTC).isoformat(timespec="minutes") \
                if b > time.time() else "not blocked"
        except BudgetError as e:
            state = f"unknown ({e})"
        print(f"collector: {state}")
    elif a.cmd == "download":
        print(download(a.video_id, a.experiment, a.note))


if __name__ == "__main__":
    main()
