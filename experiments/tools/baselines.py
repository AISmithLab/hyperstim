"""Baselines: how similar unrelated pairs are on each signal, so a pair's value can be judged.

Three sets (PLAN.md, Signal framework), drawn from the website's dataset (backend/data):
- same_song: the same song by another studio (the pair's videos and other studios' versions,
  and those versions with each other); videos that share owner evidence with the pair are left out.
- same_channel: random pairs of videos from one channel.
- random: random pairs from different channels.

API-tier signals (title, timing, duration) and our features use the whole dataset; description,
tags and thumbnails need a sample's snippets and images (API units, image requests).
"""

from __future__ import annotations

import csv
import itertools
from pathlib import Path

import numpy as np

import metadata as md
import yt

REPO = Path(__file__).resolve().parents[2]
DATASET = [REPO / "backend/data/videos.tsv", REPO / "backend/data/collected/2026.tsv"]
FEATURES = ["cuts_per_min", "inter_cut_dssim_mean", "palette_change_per_min", "lstar_flash_per_min",
            "motion_frac", "loudness_jumps_per_min", "mean_saturation", "mean_lstar", "lufs",
            "high_lufs_frac", "build_resolve_per_min", "loudness_jump_at_cut_per_min"]
MIN_PAIRS = 30  # a smaller set is shown but sets no threshold (PLAN.md, Signal framework)


def load_dataset() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for p in DATASET:
        with p.open(newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                rows[r["video_id"]] = r
    return rows


def has_run(title: str, run: list[str]) -> bool:
    t = md.tokens(title)
    return any(t[i:i + len(run)] == run for i in range(len(t) - len(run) + 1))


MIN_STUDIOS = 10   # fewer studios share the subject: fill the set up (PLAN.md, Signal framework)
SUBJECT_CAP = 40   # at most this many subject videos: each costs an image request in the sample


def subject_videos(rows: dict[str, dict], song: list[str], exclude_channels: set[str],
                   pair_titles: list[str], fill_to: int = 16, seed: int = 1) -> tuple[list[str], str]:
    """Other studios' videos on the pair's subject (the run of title words the pair shares), and
    how the set was built. With fewer than MIN_STUDIOS studios (or no shared words), it is filled
    up with the videos whose titles are closest to the pair's (word overlap; thumbnails would cost
    a request per dataset video). Capped at SUBJECT_CAP, at random."""
    ok = {v for v, r in rows.items()
          if r["channel_id"] not in exclude_channels and float(r["duration_s"] or 0) <= 600}
    match = sorted(v for v in ok if song and has_run(rows[v]["title"], song))
    how = "shared title words"
    if len({rows[v]["channel_id"] for v in match}) < MIN_STUDIOS:
        words = [set(md.tokens(t)) for t in pair_titles]
        def closeness(v):  # noqa: E306
            t = set(md.tokens(rows[v]["title"]))
            return max(len(t & w) / len(t | w) if t | w else 0.0 for w in words)
        rest = sorted((v for v in ok if v not in set(match)), key=lambda v: (-closeness(v), v))
        match = match + rest[:max(0, fill_to - len(match))]
        how = "filled up by title similarity" if song else "closest titles (no shared title words)"
    if len(match) > SUBJECT_CAP:
        rng = np.random.default_rng(seed)
        match = sorted(str(v) for v in rng.choice(match, SUBJECT_CAP, replace=False))
    return match, how


def sample_sets(rows: dict[str, dict], song: list[str], exclude_channels: set[str], seed: int = 1,
                n_random: int = 120, n_channels: int = 8, per_channel: int = 6,
                subject: list[str] | None = None) -> dict[str, list[str]]:
    """Video IDs per baseline set (before the owner filter): the snippet/thumbnail sample.
    `subject`: the same-subject videos (subject_videos); without it, the videos sharing `song`."""
    rng = np.random.default_rng(seed)
    same_song = sorted(subject) if subject is not None else sorted(
        v for v, r in rows.items() if has_run(r["title"], song) and r["channel_id"] not in exclude_channels
        and float(r["duration_s"] or 0) <= 600)
    others = sorted(v for v, r in rows.items()
                    if v not in same_song and r["channel_id"] not in exclude_channels)
    rand = list(rng.choice(others, n_random, replace=False))
    by_channel: dict[str, list[str]] = {}
    for v in others:
        by_channel.setdefault(rows[v]["channel_id"], []).append(v)
    big = sorted(c for c, vs in by_channel.items() if len(vs) >= 2 * per_channel)
    chans = rng.choice(big, n_channels, replace=False)
    same_channel = [v for c in chans for v in rng.choice(sorted(by_channel[c]), per_channel, replace=False)]
    return {"same_song": same_song, "random": [str(v) for v in rand],
            "same_channel": [str(v) for v in same_channel]}


def snippets(ids: list[str], experiment: str, note: str) -> dict[str, dict]:
    """snippet + contentDetails for many videos, 50 per API call (cached)."""
    out = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        d = yt.api("videos", {"id": ",".join(chunk), "part": "snippet,contentDetails,statistics"},
                   experiment, note, target=f"{len(chunk)} videos from {chunk[0]}")
        for it in d.get("items", []):
            out[it["id"]] = it
    return out


def thumbnail(video_id: str, experiment: str, note: str) -> Path | None:
    url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return yt.image(url, experiment, "thumbnail", video_id, note)


def pairs_for(sets: dict[str, list[str]], rows: dict[str, dict], pair: tuple[str, str],
              same_owner: set[str], seed: int = 2, max_pairs: int = 600) -> dict[str, list[tuple[str, str]]]:
    """Unrelated pairs per set. `same_owner`: videos sharing owner evidence with the pair (left out)."""
    rng = np.random.default_rng(seed)
    ch = lambda v: rows[v]["channel_id"] if v in rows else v  # noqa: E731
    song = [v for v in sets["same_song"] if v not in same_owner]
    ss = [(p, v) for p in pair for v in song]
    ss += [(x, y) for x, y in itertools.combinations(song, 2) if ch(x) != ch(y)]
    rnd = [(x, y) for x, y in itertools.combinations(sets["random"], 2) if ch(x) != ch(y)]
    sc = [(x, y) for x, y in itertools.combinations(sets["same_channel"], 2) if ch(x) == ch(y)]

    def cap(ps):
        if len(ps) <= max_pairs:
            return ps
        return [ps[i] for i in sorted(rng.choice(len(ps), max_pairs, replace=False))]

    return {"same_song": cap(ss), "same_channel": cap(sc), "random": cap(rnd)}


def dataset_pairs(rows: dict[str, dict], song: list[str], exclude_channels: set[str],
                  same_owner_channels: set[str], n: int = 5000,
                  seed: int = 3, subject: list[str] | None = None) -> dict[str, list[tuple[str, str]]]:
    """Larger pair sets from the whole dataset, for the free signals (timing, duration, title,
    features)."""
    rng = np.random.default_rng(seed)
    ids = sorted(v for v, r in rows.items() if r["channel_id"] not in exclude_channels)
    in_subject = (lambda v: v in set(subject)) if subject is not None else (  # noqa: E731
        lambda v: has_run(rows[v]["title"], song) and float(rows[v]["duration_s"] or 0) <= 600)
    song_ids = [v for v in ids if in_subject(v) and rows[v]["channel_id"] not in same_owner_channels]
    ss = [(x, y) for x, y in itertools.combinations(song_ids, 2)
          if rows[x]["channel_id"] != rows[y]["channel_id"]]
    rnd = []
    while len(rnd) < n:
        x, y = rng.choice(ids, 2, replace=False)
        if rows[x]["channel_id"] != rows[y]["channel_id"]:
            rnd.append((str(x), str(y)))
    by_channel: dict[str, list[str]] = {}
    for v in ids:
        by_channel.setdefault(rows[v]["channel_id"], []).append(v)
    chans = [c for c, vs in by_channel.items() if len(vs) >= 2]
    sc = []
    while len(sc) < n:
        c = chans[rng.integers(len(chans))]
        x, y = rng.choice(by_channel[c], 2, replace=False)
        sc.append((str(x), str(y)))
    return {"same_song": ss, "same_channel": sc, "random": rnd}


def threshold(values: dict[str, list[float]], higher_is_closer: bool, value: float | None = None) -> dict:
    """Per-set 99th percentile (1st for distances) of unrelated pairs, and the strictest of them:
    a signal fires when the pair's value beats it. Sets under MIN_PAIRS set no threshold and mark
    the signal `weak_baseline`. `closer_than`: share of each set's pairs the pair's value is closer
    than."""
    per = {}
    key = "p99" if higher_is_closer else "p1"
    for k, v in values.items():
        v = np.array([x for x in v if x is not None and not np.isnan(x)], float)
        if len(v) == 0:
            continue
        per[k] = {"n": int(len(v)), key: float(np.percentile(v, 99 if higher_is_closer else 1)),
                  "median": float(np.median(v)), "hist": _hist(v, value)}
        if value is not None and not np.isnan(value):
            per[k]["closer_than"] = float(np.mean(v < value) if higher_is_closer else np.mean(v > value))
    cuts = [p[key] for p in per.values() if p["n"] >= MIN_PAIRS]
    strict = (max(cuts) if higher_is_closer else min(cuts)) if cuts else None
    out = {"per_set": per, "threshold": strict, "higher_is_closer": higher_is_closer, "value": value,
           "weak_baseline": any(p["n"] < MIN_PAIRS for p in per.values())}
    out["fires"] = fires(value, out)
    return out


def _hist(v: np.ndarray, value: float | None, bins: int = 30) -> dict:
    """Histogram whose range also covers the pair's value, so it can be drawn on it."""
    lo, hi = float(np.min(v)), float(np.max(v))
    if value is not None and not np.isnan(value):
        lo, hi = min(lo, value), max(hi, value)
    if hi <= lo:
        hi = lo + 1e-9
    counts, edges = np.histogram(v, bins=bins, range=(lo, hi))
    return {"counts": counts.tolist(), "lo": lo, "hi": hi}


def fires(value: float | None, th: dict) -> bool | None:
    if value is None or th["threshold"] is None or np.isnan(value):
        return None
    return value > th["threshold"] if th["higher_is_closer"] else value < th["threshold"]
