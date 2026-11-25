"""Live analysis of videos outside the dataset (plan 004).

One video at a time runs through the research pipeline (`backend/pipeline/`, unchanged)
in a background thread; the others wait in a first-in, first-out queue. Each video's
state is one JSON file in the analysis folder, so results and waiting videos survive a
restart. Results never join the dataset: they are scored against it when read
(`Dataset.score_video`).
"""

import contextlib
import csv
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol, get_args

from hyperstim_api import scoring

log = logging.getLogger(__name__)

# waiting: YouTube's bot check refused us; the check runs once it lets us through (2026-11-25).
Status = Literal["queued", "waiting", "lookup", "download", "measure", "done", "failed"]
Step = Literal["lookup", "download", "measure"]
ErrorCode = Literal["unavailable", "too_short", "live", "blocked", "failed"]

STEPS: tuple[Step, ...] = ("lookup", "download", "measure")
# Typical seconds per step, timed on our server (2026-10-14, 2- to 30-minute videos).
TYPICAL_S: dict[Step, float] = {"lookup": 6, "download": 15, "measure": 25}
STEP_CAP = 0.9  # within a step, the bar stops at this share of it until the step is done
MAX_QUEUE = 30  # videos waiting, not counting the one being analyzed
MIN_DURATION_S = 60  # the clip starts at 0:30, so at least 30 s of it (plan 004, 2026-11-23)
LIMIT_WINDOW_S = 3600
DAY_S = 24 * 3600

PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
DOWNLOAD_SCRIPT = PIPELINE_DIR / "58_download_clips_v2.py"
EXTRACT_SCRIPT = PIPELINE_DIR / "04_extract_features_v2.py"
MIN_CLIP_BYTES = 10000  # the download script's own success floor
LOOKUP_TIMEOUT_S = 60
DOWNLOAD_TIMEOUT_S = 15 * 60  # the script tries three YouTube clients, 5 min each
MEASURE_TIMEOUT_S = 10 * 60
# Measuring is mostly single-threaded (only ffmpeg's decoding uses more cores): timed on our
# 8-core server (2026-10-14), 1 core 32 s, 2 28 s, 4 26 s, 8 26 s per video. So 4, leaving
# the rest to other work on the server.
MEASURE_CORES = 4
# When YouTube blocks our IP, every request says so. The collector (plan 013) reads this file,
# written here with the time, and pauses its downloads.
BLOCK_MARKER = "youtube-blocked"
BLOCKED = "blocked by YouTube"
# While YouTube blocks us, checks wait instead of failing (plan 004, 2026-11-25): once an hour
# the oldest is tried again (blocks so far lasted 2-8 hours, and each refused request may
# lengthen one); after a day of waiting one fails as `blocked`; at most this many wait.
RETRY_BLOCKED_S = 3600
GIVE_UP_WAITING_S = DAY_S
MAX_WAITING = 100


class AnalysisError(Exception):
    """An expected failure, with the reason the page shows."""

    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code: ErrorCode = code


class Busy(Exception):
    """The queue is full, or the day's new analyses (all visitors together) are used up."""


class TooManyRequests(Exception):
    """This IP address started its limit of new analyses in the last hour."""


@dataclass(frozen=True)
class VideoInfo:
    title: str
    channel_id: str
    channel: str


@dataclass(frozen=True)
class Record:
    """One video's analysis; stored as `<id>.json`."""

    id: str
    status: Status
    status_since: float  # when the current status began, epoch seconds
    requested_at: float
    title: str | None = None
    channel_id: str | None = None
    channel: str | None = None
    features: dict[str, float | None] | None = None  # raw values, set when done
    error: ErrorCode | None = None
    waiting_since: float | None = None  # first refused by YouTube's bot check; None otherwise


@dataclass(frozen=True)
class Progress:
    share: float  # 0-1
    remaining_s: float | None  # None while queued, done or failed


def estimate(record: Record, now: float) -> Progress:
    """Progress from the typical step durations; never complete before the work is."""
    if record.status == "done":
        return Progress(1.0, None)
    if record.status not in STEPS:
        return Progress(0.0, None)
    i = STEPS.index(record.status)
    step = STEPS[i]
    typical = TYPICAL_S[step]
    elapsed = max(0.0, now - record.status_since)
    before = sum(TYPICAL_S[s] for s in STEPS[:i])
    after = sum(TYPICAL_S[s] for s in STEPS[i + 1 :])
    total = before + typical + after
    share = (before + min(elapsed, typical * STEP_CAP)) / total
    left_in_step = max(typical - elapsed, typical * (1 - STEP_CAP))
    return Progress(share, after + left_in_step)


class Pipeline(Protocol):
    def lookup(self, video_id: str) -> VideoInfo: ...
    def channel(self, url: str) -> tuple[str, str]: ...
    def download(self, video_id: str, workdir: Path) -> None: ...
    def measure(self, video_id: str, workdir: Path) -> dict[str, float | None]: ...
    def cancel(self) -> None: ...


class ResearchPipeline:
    """The research scripts, run as subprocesses exactly as `pipeline/README.md` shows."""

    def __init__(
        self,
        cookies: Path | None = None,
        measure_cores: int = MEASURE_CORES,
    ) -> None:
        self._cookies = cookies
        self._cores = measure_cores  # the collector measures on 1 (plan 013)
        self._proc: subprocess.Popen[str] | None = None
        self._cancelled = False

    def lookup(self, video_id: str) -> VideoInfo:
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download"]
        cmd += ["--remote-components", "ejs:github"]
        if self._cookies:
            cmd += ["--cookies", str(self._cookies)]
        cmd += ["--print", "%(.{title,channel,channel_id,duration,live_status})j"]
        cmd.append(f"https://www.youtube.com/watch?v={video_id}")
        try:
            out = self._run(cmd, LOOKUP_TIMEOUT_S)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if isinstance(exc, subprocess.CalledProcessError) and "not a bot" in (exc.stderr or ""):
                raise AnalysisError("unavailable", BLOCKED) from exc
            raise AnalysisError("unavailable", _stderr_tail(exc)) from exc
        return parse_lookup(video_id, out)

    def download(self, video_id: str, workdir: Path) -> None:
        manifest = _manifest(video_id, workdir)
        clips = workdir / "clips"
        cmd = [sys.executable, str(DOWNLOAD_SCRIPT), "--manifest", str(manifest)]
        cmd += ["--clips-dir", str(clips), "--workers", "1", "--delay-min", "0", "--delay-max", "0"]
        if self._cookies:
            cmd += ["--cookies", str(self._cookies)]
        try:
            self._run(cmd, DOWNLOAD_TIMEOUT_S)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = _stderr_tail(exc)
        else:
            clip = clips / f"{video_id}.mp4"
            if clip.exists() and clip.stat().st_size > MIN_CLIP_BYTES:
                return
            # The script logs each attempt's message next to the clips folder.
            logs = sorted(workdir.glob("download-log-*.tsv"))
            detail = logs[0].read_text(encoding="utf-8").strip().splitlines()[-1] if logs else ""
        # The script keeps only the end of yt-dlp's error, which cuts the reason off.
        if not self._cancelled and probe_block(video_id, self._cookies):
            raise AnalysisError("unavailable", BLOCKED)
        raise AnalysisError("unavailable", detail)

    def measure(self, video_id: str, workdir: Path) -> dict[str, float | None]:
        manifest = _manifest(video_id, workdir)
        cache = workdir / "cache"
        out = workdir / "features.tsv"
        deadline = time.monotonic() + MEASURE_TIMEOUT_S
        extract = [sys.executable, str(EXTRACT_SCRIPT), "extract", "--manifest", str(manifest)]
        extract += ["--clips-dir", str(workdir / "clips"), "--cache-dir", str(cache)]
        extract += ["--workers", "1"]
        derive = [sys.executable, str(EXTRACT_SCRIPT), "derive", "--manifest", str(manifest)]
        derive += ["--cache-dir", str(cache), "--out", str(out)]
        try:
            self._run(extract, deadline - time.monotonic(), self._cores)
            self._run(derive, deadline - time.monotonic(), self._cores)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AnalysisError("failed", _stderr_tail(exc)) from exc
        failures = cache / "failures.tsv"  # extract notes a clip it couldn't measure here
        detail = failures.read_text(encoding="utf-8") if failures.exists() else ""
        return parse_features(video_id, out, detail)

    def channel(self, url: str) -> tuple[str, str]:
        """The channel ID and name behind a channel page link (compare page, plan 008).

        Runs on the request's thread, not the worker's, so it doesn't go through `_run`.
        """
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download"]
        if self._cookies:
            cmd += ["--cookies", str(self._cookies)]
        # Its own details, none of its videos.
        cmd += ["--flat-playlist", "--playlist-items", "0", "-J"]
        cmd.append(url)
        path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=LOOKUP_TIMEOUT_S,
                env={**os.environ, "PATH": path},
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AnalysisError("unavailable", _stderr_tail(exc)) from exc
        return parse_channel(proc.stdout)

    def cancel(self) -> None:
        """Stop the running script (on shutdown)."""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)

    def _run(self, cmd: list[str], timeout: float, cores: int | None = None) -> str:
        # The venv's bin first, so the scripts find yt-dlp however the API was started.
        path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"
        if self._cancelled:
            raise subprocess.CalledProcessError(-1, cmd, "", "cancelled")
        # A session of its own, so a timeout also stops what the script started
        # (yt-dlp, ffmpeg).
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PATH": path},
            start_new_session=True,
        )
        self._proc = proc
        if cores is not None:
            _limit_cores(proc.pid, cores)
        try:
            out, err = proc.communicate(timeout=max(timeout, 1))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise
        finally:
            self._proc = None
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)
        return out


def probe_block(video_id: str, cookies: Path | None = None) -> bool:
    """Ask yt-dlp once, with its full error text, whether YouTube is blocking us. (The
    download script keeps only the error's last 180 characters, which cut the reason off.)
    Used after a failed download, here and by the collector (plan 013)."""
    cmd = [sys.executable, "-m", "yt_dlp", "--simulate", "--no-warnings"]
    cmd += ["--remote-components", "ejs:github"]
    if cookies:
        cmd += ["--cookies", str(cookies)]
    cmd.append(f"https://www.youtube.com/watch?v={video_id}")
    path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env={**os.environ, "PATH": path}
        )
    except subprocess.TimeoutExpired:
        return False
    return "not a bot" in proc.stderr


def _limit_cores(pid: int, cores: int) -> None:
    """Keep a process (and what it starts later, e.g. ffmpeg) on `cores` of our cores.

    Set right after the start rather than in the child (`preexec_fn` isn't safe with
    threads); the script only starts ffmpeg after its imports. Linux only, like the server;
    elsewhere the process uses every core.
    """
    if not hasattr(os, "sched_setaffinity"):
        return
    allowed = sorted(os.sched_getaffinity(0))
    with contextlib.suppress(ProcessLookupError):  # already exited: communicate() says how
        os.sched_setaffinity(pid, allowed[:cores])


def parse_lookup(video_id: str, out: str) -> VideoInfo:
    """yt-dlp's JSON line → the video's details, or why it can't be measured."""
    lines = out.strip().splitlines()
    try:
        info = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        info = None
    if not isinstance(info, dict):
        raise AnalysisError("unavailable", f"unexpected yt-dlp output: {out[-200:]!r}")
    if info.get("live_status") in ("is_live", "is_upcoming"):
        raise AnalysisError("live")
    duration = info.get("duration")
    if not isinstance(duration, int | float):
        raise AnalysisError("unavailable", "no duration")
    if duration < MIN_DURATION_S:
        raise AnalysisError("too_short", f"{duration} s")
    return VideoInfo(
        title=str(info.get("title") or video_id),
        channel_id=str(info.get("channel_id") or ""),
        channel=str(info.get("channel") or ""),
    )


def parse_channel(out: str) -> tuple[str, str]:
    """yt-dlp's JSON for a channel page → the channel's ID and name."""
    lines = out.strip().splitlines()
    try:
        info = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        info = None
    if not isinstance(info, dict):
        info = {}
    channel_id = info.get("channel_id")
    if not isinstance(channel_id, str) or not channel_id.startswith("UC"):
        raise AnalysisError("unavailable", f"no channel in yt-dlp output: {out[-200:]!r}")
    return channel_id, str(info.get("channel") or "")


def parse_features(video_id: str, path: Path, detail: str = "") -> dict[str, float | None]:
    """The video's 12 raw features from `derive`'s TSV."""
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh, delimiter="\t") if r["video_id"] == video_id]
    if not rows:
        raise AnalysisError("failed", detail or "no features row")
    features = {name: _float(rows[0].get(name)) for name in scoring.FEATURES}
    if all(v is None for v in features.values()):
        raise AnalysisError("failed", "no feature values")
    return features


def _float(raw: str | None) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def _manifest(video_id: str, workdir: Path) -> Path:
    path = workdir / "manifest.tsv"
    path.write_text(f"video_id\n{video_id}\n", encoding="utf-8")
    return path


def _stderr_tail(exc: subprocess.CalledProcessError | subprocess.TimeoutExpired) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"timed out after {exc.timeout:.0f} s"
    return (exc.stderr or "").strip()[-300:]


class Analyzer:
    """The queue, the worker thread and the file store."""

    def __init__(
        self,
        directory: Path,
        pipeline: Pipeline,
        limit_per_ip: int,
        limit_per_day: int = 0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._dir = directory
        self._work = directory / "work"  # one temporary folder per running video
        self._pipeline = pipeline
        self._limit = limit_per_ip
        self._limit_per_day = limit_per_day
        self.clock = clock
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._records: dict[str, Record] = {}
        self._queue: deque[str] = deque()
        # Refused by YouTube's bot check, in the order requested; while `_blocked`, new checks
        # join them, and from `_next_try` on the worker tries the oldest again.
        self._waiting: list[str] = []
        self._blocked = False
        self._next_try = 0.0
        self._running: str | None = None
        self._requests: dict[str, deque[float]] = {}  # IP -> its new analyses in the window
        self._started: deque[float] = deque()  # new analyses in the last 24 hours, all IPs
        self._stopping = False
        self._thread: threading.Thread | None = None
        directory.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self._work, ignore_errors=True)  # left over if the API was stopped
        self._load()

    def _load(self) -> None:
        unfinished = []
        waiting = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                record = Record(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError) as exc:
                log.error("Skipping unreadable analysis file %s: %s", path, exc)
                continue
            if record.error is not None and record.error not in get_args(ErrorCode):
                # A code the API no longer sends (`not_for_kids`, until 2026-11-23): the page
                # offers to try again, which runs it under today's rules.
                record = replace(record, error="failed")
            self._records[record.id] = record
            if record.status == "waiting":
                waiting.append(record)
            elif record.status not in ("done", "failed"):
                unfinished.append(record)
        # So a restart (each release) doesn't reset the day's count.
        now = self.clock()
        self._started.extend(
            sorted(r.requested_at for r in self._records.values() if now - r.requested_at < DAY_S)
        )
        # Waiting or running when the API stopped: start again, in the order requested.
        for record in sorted(unfinished, key=lambda r: r.requested_at):
            self._save(replace(record, status="queued", status_since=now))
            self._queue.append(record.id)
        # Waiting for YouTube when the API stopped: still waiting; the next try an hour after
        # the last refusal.
        self._waiting = [r.id for r in sorted(waiting, key=lambda r: r.requested_at)]
        if self._waiting:
            self._blocked = True
            self._next_try = self._blocked_at(now) + RETRY_BLOCKED_S
        log.info(
            "Loaded %d analyses from %s (%d queued again, %d waiting for YouTube)",
            len(self._records),
            self._dir,
            len(unfinished),
            len(self._waiting),
        )

    def _blocked_at(self, default: float) -> float:
        """When YouTube last refused us, from the marker the collector reads too."""
        try:
            return float((self._dir / BLOCK_MARKER).read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return default

    def snapshot(self, video_id: str) -> tuple[Record, int | None] | None:
        """The video's record and, while it waits, how many videos are ahead of it."""
        with self._lock:
            record = self._records.get(video_id)
            if record is None:
                return None
            position = None
            if video_id in self._queue:
                position = self._queue.index(video_id) + (self._running is not None)
            return record, position

    def start(self, video_id: str, ip: str) -> tuple[Record, bool]:
        """Queue the video unless it is stored or running; True if newly queued.

        Raises Busy when the queue is full or the day's limit is used up, TooManyRequests when
        the IP is over its limit.
        """
        with self._lock:
            record = self._records.get(video_id)
            if record is not None and record.status != "failed":
                return record, False
            now = self.clock()
            while self._started and now - self._started[0] >= DAY_S:
                self._started.popleft()
            if len(self._waiting if self._blocked else self._queue) >= (
                MAX_WAITING if self._blocked else MAX_QUEUE
            ):
                raise Busy
            if self._limit_per_day and len(self._started) >= self._limit_per_day:
                raise Busy
            self._count_request(ip)
            self._started.append(now)
            if self._blocked:  # don't ask YouTube while it refuses us
                record = Record(video_id, "waiting", now, now, waiting_since=now)
                self._save(record)
                self._waiting.append(video_id)
                return record, True
            record = Record(id=video_id, status="queued", status_since=now, requested_at=now)
            self._save(record)
            self._queue.append(video_id)
            self._wake.notify()
            return record, True

    def count_request(self, ip: str) -> None:
        """Count a request that asks YouTube (a channel lookup) toward the IP's limit.

        Raises TooManyRequests when the IP is over it; shares the count with new analyses.
        """
        with self._lock:
            self._count_request(ip)

    def _count_request(self, ip: str) -> None:
        if self._limit == 0:
            return
        now = self.clock()
        for key in [k for k, t in self._requests.items() if now - t[-1] >= LIMIT_WINDOW_S]:
            del self._requests[key]  # nothing in the window: forget the IP
        times = self._requests.setdefault(ip, deque())
        while times and now - times[0] >= LIMIT_WINDOW_S:
            times.popleft()
        if len(times) >= self._limit:
            raise TooManyRequests
        times.append(now)

    def run_next(self) -> bool:
        """Analyze the next waiting video, if any; True if one ran.

        The worker thread calls this in a loop; tests call it directly.
        """
        with self._lock:
            now = self.clock()
            self._give_up(now)
            if self._queue:
                video_id = self._queue.popleft()
            elif self._waiting and now >= self._next_try:
                video_id = self._waiting.pop(0)  # is YouTube letting us through again?
            else:
                return False
            self._running = video_id
        try:
            self._analyze(video_id)
        finally:
            with self._lock:
                self._running = None
        return True

    def _analyze(self, video_id: str) -> None:
        workdir = self._work / video_id
        times = [self.clock()]
        try:
            workdir.mkdir(parents=True)
            self._update(video_id, status="lookup")
            info = self._pipeline.lookup(video_id)
            times.append(self.clock())
            self._update(
                video_id,
                status="download",
                title=info.title,
                channel_id=info.channel_id,
                channel=info.channel,
            )
            self._pipeline.download(video_id, workdir)
            times.append(self.clock())
            self._update(video_id, status="measure")
            features = self._pipeline.measure(video_id, workdir)
            times.append(self.clock())
            self._update(video_id, status="done", features=features)
            steps = ", ".join(
                f"{s} {b - a:.0f} s" for s, a, b in zip(STEPS, times[:-1], times[1:], strict=True)
            )
            log.info("Analyzed %s: %s", video_id, steps)
        except Exception as exc:
            if self._stopping:
                return  # interrupted by shutdown: queued again at the next start
            if str(exc) == BLOCKED:
                log.warning("YouTube refused the check of %s: it waits", video_id)
                (self._dir / BLOCK_MARKER).write_text(f"{self.clock()}\n", encoding="utf-8")
                self._wait_for_youtube(video_id)
                return
            if isinstance(exc, AnalysisError):
                log.warning("Analysis of %s failed (%s): %s", video_id, exc.code, exc)
                code: ErrorCode = exc.code
            else:
                log.exception("Analysis of %s failed", video_id)
                code = "failed"
            self._update(video_id, status="failed", error=code)
            self._unblock()
        else:
            self._unblock()
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _wait_for_youtube(self, video_id: str) -> None:
        """YouTube's bot check refused the video: it waits, and so do the ones queued behind
        it, so visitors don't add to the block; the oldest is tried again in an hour."""
        with self._lock:
            now = self.clock()
            for vid in [video_id, *self._queue]:
                record = self._records[vid]
                since = record.waiting_since if record.waiting_since is not None else now
                self._save(replace(record, status="waiting", status_since=now, waiting_since=since))
            self._waiting += [video_id, *self._queue]
            self._waiting.sort(key=lambda vid: self._records[vid].requested_at)
            self._queue.clear()
            self._blocked = True
            self._next_try = now + RETRY_BLOCKED_S

    def _unblock(self) -> None:
        """A check got past YouTube's bot check: the waiting ones go first, oldest first."""
        with self._lock:
            if not self._blocked:
                return
            log.info("YouTube lets us through again: %d waiting checks queued", len(self._waiting))
            now = self.clock()
            for vid in self._waiting:
                self._save(replace(self._records[vid], status="queued", status_since=now))
            self._queue.extendleft(reversed(self._waiting))
            self._waiting = []
            self._blocked = False
            self._wake.notify()

    def _give_up(self, now: float) -> None:
        """Checks that waited a day for YouTube fail as `blocked`. Hold the lock."""
        for vid in list(self._waiting):
            record = self._records[vid]
            if now - (record.waiting_since or now) >= GIVE_UP_WAITING_S:
                log.warning("Gave up on %s after a day of waiting for YouTube", vid)
                self._save(replace(record, status="failed", status_since=now, error="blocked"))
                self._waiting.remove(vid)

    def _due(self) -> float | None:
        """When the worker has something to do for the waiting checks. Hold the lock."""
        if not self._waiting:
            return None
        give_up = min(
            (self._records[vid].waiting_since or 0) + GIVE_UP_WAITING_S for vid in self._waiting
        )
        return min(self._next_try, give_up)

    def _update(self, video_id: str, **changes: Any) -> None:
        with self._lock:
            record = replace(self._records[video_id], status_since=self.clock(), **changes)
            self._save(record)

    def _save(self, record: Record) -> None:
        """Write the record's file (whole, via a rename) and keep it in memory. Hold the lock."""
        path = self._dir / f"{record.id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(record)), encoding="utf-8")
        os.replace(tmp, path)
        self._records[record.id] = record

    def start_worker(self) -> None:
        self._thread = threading.Thread(target=self._work_loop, name="analysis", daemon=True)
        self._thread.start()

    def stop_worker(self) -> None:
        with self._lock:
            self._stopping = True
            self._wake.notify_all()
        self._pipeline.cancel()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _work_loop(self) -> None:
        while True:
            with self._lock:
                while not self._queue and not self._stopping:
                    due = self._due()
                    if due is None:
                        self._wake.wait()
                    elif due <= self.clock():
                        break
                    else:
                        self._wake.wait(timeout=due - self.clock())
                if self._stopping:
                    return
            self.run_next()
