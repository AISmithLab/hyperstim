"""fetch -> group -> page on a small fake YouTube: no network, every request answered from a dict."""

import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_channels_report as rep  # noqa: E402
import channels as ch  # noqa: E402

# Dataset channels A and B (same owner, by copyright), family channel F (A lists it in "Our Family";
# its own videos name the owner), S (a seed outside the dataset), D (deleted: no channels.list item).
A, B, F, S, D = "UCaaaaaaaaaaaaaaaaaaaaaa", "UCbbbbbbbbbbbbbbbbbbbbbb", "UCffffffffffffffffffffff", \
    "UCssssssssssssssssssssss", "UCdddddddddddddddddddddd"
OWNER = "© 2024 Acme Toons Pvt. Ltd."


def channel(cid, title, desc="", lang=""):
    return {"id": cid, "snippet": {"title": title, "description": desc, "defaultLanguage": lang,
                                   "publishedAt": "2015-01-01T00:00:00Z", "country": "IN"},
            "statistics": {"videoCount": "10", "subscriberCount": "1000", "viewCount": "5"},
            "brandingSettings": {"channel": {"description": ""}}}


def video(vid, desc, lang="en"):
    return {"id": vid, "snippet": {"description": desc, "defaultAudioLanguage": lang}}


CHANNELS = {A: channel(A, "Acme Kids"), B: channel(B, "Acme Rhymes"), F: channel(F, "Acme Hindi", lang="hi"),
            S: channel(S, "Seed Studio", "Visit seedstudio.example")}
VIDEOS = {"va1": video("va1", OWNER), "vb1": video("vb1", OWNER), "vb2": video("vb2", OWNER),
          "vf1": video("vf1", OWNER, "hi"), "vf2": video("vf2", OWNER, "hi")}
SECTIONS = {A: [("Our Family", [F, D]), ("Our Friends", ["UCxxxxxxxxxxxxxxxxxxxxxx"])],
            F: [("Featured Channels", ["UCzzzzzzzzzzzzzzzzzzzzzz"])],  # never fetched: F is linked in stage 1
            S: [("Featured Channels", ["UCyyyyyyyyyyyyyyyyyyyyyy"])]}
UPLOADS = {F: ["vf1", "vf2"], S: []}  # F's are never fetched: F is linked in stage 1


def answer(endpoint, params):
    if endpoint == "channels":
        return {"items": [CHANNELS[c] for c in params["id"].split(",") if c in CHANNELS]}
    if endpoint == "videos":
        return {"items": [VIDEOS[v] for v in params["id"].split(",") if v in VIDEOS]}
    if endpoint == "channelSections":
        secs = SECTIONS.get(params["channelId"], [])
        return {"items": [{"snippet": {"type": "multiplechannels", "title": t},
                           "contentDetails": {"channels": cs}} for t, cs in secs]}
    if endpoint == "playlistItems":
        cid = "UC" + params["playlistId"][2:]
        if cid not in UPLOADS:
            raise urllib.error.HTTPError("https://example.invalid", 404, "gone", {}, None)
        return {"items": [{"contentDetails": {"videoId": v}} for v in UPLOADS[cid]]}
    raise AssertionError(endpoint)


@pytest.fixture
def world(tmp_path, monkeypatch):
    ref = tmp_path / "videos.tsv"
    head = "video_id\tchannel_id\tchannel_title\n"
    ref.write_text(f"{head}va1\t{A}\tAcme Kids\nvb1\t{B}\tAcme Rhymes\n")
    col = tmp_path / "2026.tsv"
    col.write_text(f"{head}vb1\t{B}\tAcme Rhymes\nvb2\t{B}\tAcme Rhymes\n")
    monkeypatch.setattr(ch, "DATASETS", {"reference": ref, "collected": col})
    monkeypatch.setattr(ch, "OUT", tmp_path / "out")
    monkeypatch.setattr(ch, "SEEDS", {A: "Acme Kids", S: "Seed Studio"})
    cache, calls = {}, []

    def key(endpoint, params):
        return endpoint, json.dumps(params, sort_keys=True)

    def api(endpoint, params, experiment, note="", target=""):
        calls.append(endpoint)
        data = answer(endpoint, params)
        cache[key(endpoint, params)] = data
        return data

    monkeypatch.setattr(ch.yt, "api", api)
    monkeypatch.setattr(ch.yt, "api_cached", lambda e, p, t="": cache.get(key(e, p)))
    monkeypatch.setattr(ch.yt, "units_used_today", lambda: len(calls))
    return tmp_path, calls


def test_fetch_then_group_then_page(world, monkeypatch):
    tmp, calls = world
    ch.fetch()
    assert calls.count("channelSections") == 2 + 1  # A, B; then S, still unlinked, in stage 3
    n = len(calls)
    summary = ch.run_group()  # offline: answered from what fetch saved
    assert len(calls) == n

    assert summary["channels"] == 4 and summary["family_channels"] == 1 and summary["frontier"] == 1
    out = tmp / "out"
    groups = json.loads((out / "groups.json").read_text())
    acme = groups["groups"][0]
    assert set(acme["channels"]) == {A, B, F} and acme["dubs"] == [F] and acme["language"] == "en"
    assert groups["featured_only"] == []  # the friend X has no channels.list item; S is a seed
    assert [g["channels"] for g in groups["groups"][1:]] == [[S]]
    rows = {r.split("\t")[0]: r.split("\t") for r in (out / "channels.tsv").read_text().splitlines()[1:]}
    assert [rows[c][2] for c in (A, B, F, S)] == ["reference", "both", "family", "seed"]
    assert rows[A][11] == "acme toons"
    assert (out / "frontier.tsv").read_text().split() == ["channel_id", "UCyyyyyyyyyyyyyyyyyyyyyy"]
    assert "fetch: done" in (out / "events.log").read_text()

    monkeypatch.setattr(rep, "RES", out)
    monkeypatch.setattr(rep, "OUT", tmp / "page" / "report.html")
    monkeypatch.setattr(rep, "SEEDS", {A: "Acme Kids", S: "Seed Studio"})
    d = rep.data()
    assert d["seeds"] == {"Acme Kids": acme["id"], "Seed Studio": groups["groups"][1]["id"]}
    assert d["groups"][0]["evidence"][0][:2] == ["copyright", "acme toons"]
    rep.main()
    html = (tmp / "page" / "report.html").read_text()
    assert "__DATA__" not in html and "Acme Hindi" in html


def test_call_waits_for_the_next_day_then_retries(monkeypatch, tmp_path):
    monkeypatch.setattr(ch, "OUT", tmp_path)
    answers = [ch.yt.BudgetError("API budget: 9500 of 9500 units used today (Pacific)"),
               urllib.error.HTTPError("u", 503, "busy", {}, None), {"ok": 1}]

    def api(*a, **k):
        x = answers.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    slept = []
    monkeypatch.setattr(ch.yt, "api", api)
    monkeypatch.setattr(ch.time, "sleep", slept.append)
    monkeypatch.setattr(ch, "next_pacific_day", lambda: datetime(2000, 1, 1, tzinfo=UTC))
    assert ch.call("videos", {"id": "a"}) == {"ok": 1}
    assert slept == [60.0, 30]
    assert "budget used up" in (tmp_path / "events.log").read_text()


def test_call_gone_is_none_and_other_errors_raise(monkeypatch):
    def raiser(exc):
        def api(*a, **k):
            raise exc
        return api

    monkeypatch.setattr(ch.yt, "api", raiser(urllib.error.HTTPError("u", 404, "gone", {}, None)))
    assert ch.call("channels", {"id": "x"}) is None
    monkeypatch.setattr(ch.yt, "api", raiser(urllib.error.HTTPError("u", 400, "bad", {}, None)))
    with pytest.raises(urllib.error.HTTPError):
        ch.call("channels", {"id": "x"})
    monkeypatch.setattr(ch.yt, "api", raiser(ch.yt.BudgetError("EXP_YOUTUBE_API_KEY is not set")))
    with pytest.raises(ch.yt.BudgetError):
        ch.call("channels", {"id": "x"})


def test_main_dispatches(monkeypatch):
    seen = []
    monkeypatch.setattr(ch, "fetch", lambda: seen.append("fetch"))
    monkeypatch.setattr(ch, "run_group", lambda: seen.append("group"))
    for cmd in ("fetch", "group"):
        monkeypatch.setattr(sys, "argv", ["channels.py", cmd])
        ch.main()
    assert seen == ["fetch", "group"]
