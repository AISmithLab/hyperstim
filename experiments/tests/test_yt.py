import csv
import importlib
import io
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest

import yt

ENV = ["EXP_PLAYER_PER_DAY", "EXP_IMAGE_GAP", "EXP_PLAYER_GAP", "EXP_API_UNITS_PER_DAY", "YTDLP_COOKIES",
       "COLLECTOR_DATA_DIR", "COLLECTOR_USER", "YOUTUBE_API_KEY"]
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code):
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, None)


@pytest.fixture(autouse=True)
def sandbox(monkeypatch, tmp_path):
    """Ledger and cache in tmp_path; any unmocked network or subprocess call fails the test."""
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(yt)
    monkeypatch.setattr(yt, "LEDGER", tmp_path / "ledger.tsv")
    monkeypatch.setattr(yt, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(yt, "now_utc", lambda: NOW)

    def refuse(*a, **k):
        raise AssertionError("unexpected network or subprocess call")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    yield tmp_path
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(yt)


def rows():
    return yt._rows()


def add(at, kind, units=0, what="x", target="t", outcome="ok"):
    yt.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    new = not yt.LEDGER.exists()
    with yt.LEDGER.open("a", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        if new:
            w.writerow(yt.COLUMNS)
        w.writerow([at, "000", kind, what, target, units, outcome, ""])


# --- Ledger -----------------------------------------------------------------------------


def test_log_writes_header_once_and_columns():
    yt.log("001", "API", "videos", "abc", 1, "ok", "a\tnote")
    yt.log("001", "image", "thumb", "abc", 0, "error 404")
    lines = yt.LEDGER.read_text().splitlines()
    assert lines[0].split("\t") == yt.COLUMNS
    assert len(lines) == 3
    assert lines[1].split("\t") == [
        "2026-11-11T12:00:00Z", "001", "API", "videos", "abc", "1", "ok", "a note"]
    assert rows()[1]["outcome"] == "error 404"


def test_player_used_today_counts_utc_day():
    add("2026-11-10T23:59:59Z", "player")
    add("2026-11-11T00:00:00Z", "player")
    add("2026-11-11T23:59:59Z", "player")
    add("2026-11-11T10:00:00Z", "API", 1)
    assert yt.player_used_today() == 2
    assert yt.player_used_today(datetime(2026, 11, 10, 5, tzinfo=UTC)) == 1


def test_units_used_today_counts_pacific_day():
    add("2026-11-11T07:59:00Z", "API", 100)  # 23:59 PST on Nov 10
    add("2026-11-11T08:00:00Z", "API", 1)  # 00:00 PST on Nov 11
    add("2026-11-12T07:00:00Z", "API", 5)  # 23:00 PST on Nov 11
    add("2026-11-11T09:00:00Z", "player")
    assert yt.units_used_today() == 6
    assert yt.units_used_today(datetime(2026, 11, 11, 7, 30, tzinfo=UTC)) == 100


def test_units_used_today_follows_daylight_saving():
    add("2026-07-01T06:59:00Z", "API", 3)  # 23:59 PDT on Jun 30
    add("2026-07-01T07:00:00Z", "API", 4)  # 00:00 PDT on Jul 1
    assert yt.units_used_today(datetime(2026, 7, 1, 12, tzinfo=UTC)) == 4


# --- API --------------------------------------------------------------------------------


def test_api_fetches_logs_and_caches(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    urls = []

    def fake(url, timeout):
        urls.append(url)
        return Response(b'{"items": [1]}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert yt.api("search", {"q": "a b", "part": "id"}, "001") == {"items": [1]}
    assert urls == ["https://www.googleapis.com/youtube/v3/search?q=a+b&part=id&key=k"]
    [row] = rows()
    assert (row["kind"], row["what"], row["units"], row["outcome"]) == ("API", "search", "100", "ok")
    assert yt.api("search", {"part": "id", "q": "a b"}, "001") == {"items": [1]}
    assert len(urls) == 1 and len(rows()) == 1


def test_api_cached_response_needs_no_request_key_or_budget(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: Response(b'{"a": 1}'))
    yt.api("videos", {"id": "abc", "part": "snippet"}, "001")
    monkeypatch.delenv("YOUTUBE_API_KEY")
    monkeypatch.setattr(yt, "API_UNITS_PER_DAY", 0)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("request made"))
    assert yt.api("videos", {"id": "abc", "part": "snippet"}, "001") == {"a": 1}
    assert len(rows()) == 1


def test_api_refuses_over_budget(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    add("2026-11-11T10:00:00Z", "API", 1950)
    with pytest.raises(yt.BudgetError, match="1950 of 2000"):
        yt.api("search", {"q": "x"}, "001")
    assert len(rows()) == 1
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: Response(b"{}"))
    yt.api("videos", {"id": "a"}, "001")  # 1 unit still fits
    assert yt.units_used_today() == 1951


def test_api_refuses_without_key():
    with pytest.raises(yt.BudgetError, match="YOUTUBE_API_KEY"):
        yt.api("videos", {"id": "a"}, "001")
    assert rows() == []


def test_api_logs_errors_and_does_not_cache(monkeypatch, sandbox):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")

    def fail(url, timeout):
        raise http_error(403)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(urllib.error.HTTPError):
        yt.api("videos", {"id": "abc"}, "001", note="n")
    [row] = rows()
    assert (row["target"], row["units"], row["outcome"], row["note"]) == ("abc", "1", "error 403", "n")
    assert not (sandbox / "cache" / "api").exists()


# --- Image ------------------------------------------------------------------------------


@pytest.fixture
def clock(monkeypatch):
    t = [1000.0]
    sleeps = []

    def sleep(s):
        sleeps.append(round(s, 6))
        t[0] += s

    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    monkeypatch.setattr(time, "sleep", sleep)
    monkeypatch.setattr(yt, "_next_at", {"image": 0.0, "player": 0.0})
    return t, sleeps


def test_image_fetches_once_then_returns_cached_path(monkeypatch, clock):
    reqs = []

    def fake(req, timeout):
        reqs.append(req)
        return Response(b"jpg")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    url = "https://i.ytimg.com/vi/abc/hqdefault.jpg"
    path = yt.image(url, "001", "thumbnail", "abc")
    assert path.read_bytes() == b"jpg" and path.suffix == ".jpg"
    assert reqs[0].get_header("User-agent") == yt.UA
    assert yt.image(url, "001", "thumbnail", "abc") == path
    assert len(reqs) == 1
    [row] = rows()
    assert (row["kind"], row["what"], row["units"], row["outcome"]) == ("image", "thumbnail", "0", "ok")


def test_image_remembers_404(monkeypatch, clock):
    calls = []

    def fail(req, timeout):
        calls.append(req)
        raise http_error(404)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    url = "https://i.ytimg.com/sb/abc/storyboard3_L2/M0.jpg"
    assert yt.image(url, "001", "storyboard", "abc") is None
    assert yt.image(url, "001", "storyboard", "abc") is None
    assert len(calls) == 1
    assert [r["outcome"] for r in rows()] == ["error 404"]


def test_image_raises_other_errors_without_remembering(monkeypatch, clock):
    def fail(req, timeout):
        raise http_error(500)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    url = "https://i.ytimg.com/vi/abc/0.jpg"
    for _ in range(2):
        with pytest.raises(urllib.error.HTTPError):
            yt.image(url, "001", "thumbnail", "abc")
    assert [r["outcome"] for r in rows()] == ["error 500", "error 500"]


def test_image_paces_requests_with_random_gaps(monkeypatch, clock):
    t, sleeps = clock
    starts = []
    draws = iter([0.7, 1.3, 0.5])
    calls = []

    def uniform(lo, hi):
        calls.append((lo, hi))
        return next(draws)

    def fake(req, timeout):
        starts.append(t[0])
        t[0] += 0.1  # the request itself takes 0.1 s
        return Response(b"x")

    monkeypatch.setattr(yt.random, "uniform", uniform)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    for i in range(3):
        yt.image(f"https://i.ytimg.com/vi/v{i}/0.jpg", "001", "thumbnail", f"v{i}")
    assert [b - a for a, b in zip(starts, starts[1:], strict=False)] == pytest.approx([0.7, 1.3])
    assert calls == [(0.5, 1.5)] * 3
    t[0] += 5  # a later request after a long pause doesn't wait
    monkeypatch.setattr(yt.random, "uniform", lambda lo, hi: 1.0)
    yt.image("https://i.ytimg.com/vi/v9/0.jpg", "001", "thumbnail", "v9")
    assert sleeps[-1] == 0.0


def test_image_gaps_vary_within_bounds(monkeypatch, clock):
    t, _ = clock
    starts = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: starts.append(t[0]) or Response(b"x"))
    for i in range(20):
        yt.image(f"https://i.ytimg.com/vi/v{i}/0.jpg", "001", "thumbnail", f"v{i}")
    gaps = [b - a for a, b in zip(starts, starts[1:], strict=False)]
    assert all(0.5 <= g <= 1.5 for g in gaps) and len({round(g, 6) for g in gaps}) > 1


# --- Player -----------------------------------------------------------------------------


@pytest.fixture
def collector(monkeypatch, sandbox):
    """A collector.db with `blocked_until`; returns a setter."""
    db = sandbox / "collector.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
    con.commit()
    monkeypatch.setenv("COLLECTOR_DATA_DIR", str(sandbox))

    def set_blocked(until):
        con.execute("INSERT OR REPLACE INTO kv VALUES ('blocked_until', ?)", (str(until),))
        con.commit()

    yield set_blocked
    con.close()


@pytest.fixture
def ytdlp(monkeypatch):
    """A fake yt-dlp that writes the video file; returns the commands it ran."""
    cmds = []
    monkeypatch.setattr(yt.shutil, "which", lambda name: "/fake/yt-dlp")

    def run(cmd, **kw):
        cmds.append(cmd)
        out = cmd[cmd.index("--output") + 1].replace(".%(ext)s", ".mp4")
        open(out, "wb").close()
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    return cmds


def test_download_runs_ytdlp_once_and_logs(collector, ytdlp):
    path = yt.download("abc", "001", note="n")
    assert path == yt.video_path("abc") and path.exists()
    assert ytdlp[0][0] == "/fake/yt-dlp" and ytdlp[0][-1] == "https://www.youtube.com/watch?v=abc"
    assert "--cookies" not in ytdlp[0]
    [row] = rows()
    assert (row["kind"], row["what"], row["target"], row["outcome"], row["note"]) == \
        ("player", "download", "abc", "ok", "n")
    assert yt.download("abc", "001") == path
    assert len(ytdlp) == 1 and len(rows()) == 1


def test_download_waits_a_random_gap_after_each_download(monkeypatch, collector, ytdlp, clock):
    _, sleeps = clock
    monkeypatch.setattr(yt.random, "uniform", lambda lo, hi: (lo + hi) / 2)
    yt.download("abc", "001")
    yt.download("def", "001")
    assert sleeps == [0.0, 90.0]


def test_download_passes_cookies(monkeypatch, collector, ytdlp):
    monkeypatch.setenv("YTDLP_COOKIES", "/c.txt")
    yt.download("abc", "001")
    assert ytdlp[0][1:3] == ["--cookies", "/c.txt"]


def test_download_refuses_over_player_budget(collector, ytdlp):
    for i in range(50):
        add("2026-11-11T01:00:00Z", "player", target=f"v{i}")
    with pytest.raises(yt.BudgetError, match="50 of 50"):
        yt.download("abc", "001")
    assert ytdlp == []


def test_download_allows_after_utc_day_turns(collector, ytdlp):
    for i in range(50):
        add("2026-11-10T23:00:00Z", "player", target=f"v{i}")
    yt.download("abc", "001")
    assert len(ytdlp) == 1


def test_download_refuses_video_downloaded_before_but_not_cached(collector, ytdlp):
    add("2026-01-01T00:00:00Z", "player", what="download", target="abc")
    with pytest.raises(yt.BudgetError, match="never twice"):
        yt.download("abc", "001")
    assert ytdlp == []


def test_download_retries_a_failed_download(collector, ytdlp):
    add("2026-01-01T00:00:00Z", "player", what="download", target="abc", outcome="error")
    yt.download("abc", "001")
    assert len(ytdlp) == 1


def test_download_refuses_while_collector_blocked(collector, ytdlp):
    collector(time.time() + 3600)
    with pytest.raises(yt.BudgetError, match="blocked by YouTube until"):
        yt.download("abc", "001")
    assert ytdlp == [] and rows() == []
    collector(time.time() - 60)
    yt.download("abc", "001")
    assert len(ytdlp) == 1


def test_download_refuses_without_collector_db_setting(ytdlp):
    with pytest.raises(yt.BudgetError, match="COLLECTOR_DATA_DIR"):
        yt.download("abc", "001")
    assert ytdlp == []


def test_download_refuses_when_collector_db_unreadable(monkeypatch, sandbox, ytdlp):
    monkeypatch.setenv("COLLECTOR_DATA_DIR", str(sandbox / "missing"))
    with pytest.raises(yt.BudgetError, match="COLLECTOR_USER"):
        yt.download("abc", "001")
    assert ytdlp == []


def test_download_logs_failure(monkeypatch, collector):
    monkeypatch.setattr(yt.shutil, "which", lambda name: "/fake/yt-dlp")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 1, "", "WARNING: x\nERROR: [youtube] abc: Sign in to confirm\n"))
    with pytest.raises(RuntimeError, match="Sign in"):
        yt.download("abc", "001", note="n")
    [row] = rows()
    assert row["outcome"] == "error"
    assert row["note"] == "n; ERROR: [youtube] abc: Sign in to confirm"


# --- Env overrides ----------------------------------------------------------------------


def test_defaults():
    assert (yt.PLAYER_PER_DAY, yt.API_UNITS_PER_DAY) == (50, 2000)
    assert (yt.IMAGE_GAP, yt.PLAYER_GAP) == ((0.5, 1.5), (45.0, 135.0))


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("EXP_PLAYER_PER_DAY", "2")
    monkeypatch.setenv("EXP_IMAGE_GAP", "1-3")
    monkeypatch.setenv("EXP_PLAYER_GAP", "10-20")
    monkeypatch.setenv("EXP_API_UNITS_PER_DAY", "150")
    importlib.reload(yt)
    monkeypatch.setattr(yt, "LEDGER", tmp_path / "ledger.tsv")
    monkeypatch.setattr(yt, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(yt, "now_utc", lambda: NOW)
    assert (yt.PLAYER_PER_DAY, yt.API_UNITS_PER_DAY) == (2, 150)
    assert (yt.IMAGE_GAP, yt.PLAYER_GAP) == ((1.0, 3.0), (10.0, 20.0))

    add("2026-11-11T10:00:00Z", "API", 100)
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    with pytest.raises(yt.BudgetError, match="100 of 150"):
        yt.api("search", {"q": "x"}, "001")

    add("2026-11-11T01:00:00Z", "player", target="v1")
    add("2026-11-11T02:00:00Z", "player", target="v2")
    with pytest.raises(yt.BudgetError, match="2 of 2"):
        yt.download("abc", "001")


def test_env_image_gap_paces(monkeypatch, tmp_path, clock):
    monkeypatch.setenv("EXP_IMAGE_GAP", "2-2")
    importlib.reload(yt)
    monkeypatch.setattr(yt, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(yt, "LEDGER", tmp_path / "ledger.tsv")
    monkeypatch.setattr(yt, "_next_at", {"image": 0.0, "player": 0.0})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: Response(b"x"))
    _, sleeps = clock
    yt.image("https://i.ytimg.com/vi/a/0.jpg", "001", "thumbnail", "a")
    yt.image("https://i.ytimg.com/vi/b/0.jpg", "001", "thumbnail", "b")
    assert sleeps == [0.0, 2.0]
