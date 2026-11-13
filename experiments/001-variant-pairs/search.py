"""Search the seed channel pair for more variant pairs: the filter chain (PLAN.md, Search).

    uv run python 001-variant-pairs/search.py run

Filters run at once, each with its own queue: 0 inventory, 1 images, 2 candidates, 3 score,
4 gate, 5 agent review (labels written by subagents into results/search/labels/), 6 download.
Filter 7 (full reports) runs on its own (score_pair.py, build_report.py).

State: cache/search.db (queues; rebuilt from the image cache and saved results if lost) and
cache/search/ (per-video features). Results: results/search/ (progress log, calibration,
gated pairs, labels). A stopped run resumes where it was: every request is cached.

Env vars: those of tools/yt.py (EXP_YOUTUBE_API_KEY, COLLECTOR_DATA_DIR, COLLECTOR_USER, budgets).
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import queue
import random
import re
import sqlite3
import sys
import threading
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import metadata as md  # noqa: E402
import visual as vis  # noqa: E402
import yt  # noqa: E402

EXP = "001"
CHANNELS = {"A": "UC7Pq3Ko42YpkCB_Q4E981jw", "B": "UCv7TYWhF5jhtuY3FDPf06Aw"}  # Kids TV, Kids Channel
SEED = ("pRPe05YfXxg", "AJ1vEJXC0-M")
TYPES = ("AxB", "AxA", "BxB")
DB = ROOT / "cache" / "search.db"
FEAT = ROOT / "cache" / "search"
OUT = HERE / "results" / "search"

N_CALIBRATION = 500        # videos (random order) whose pairs set the random baselines
GATE_SAMPLE = {"A": 150, "B": 60}  # videos whose hq1/hq3 set the gate's random baseline
SCORE_TARGET = 5000        # pairs the score filter should pass, of 17.3 M
AUDIT_SHARE = 0.03         # share of gate-stopped pairs sent to review anyway
AUDIT_MAX = 60
COMPILATION_S = 1800  # longer is a compilation, left out of pairs (human decision 2026-11-11: was 10 min)
COMPILATION_RE = re.compile(r"compilation|collection|\b\d+\s*(hours?|hrs?)\b|non[- ]?stop|\bmegamix\b", re.I)
END_SCREEN_S = 30          # duration fit allows one version up to this much longer (an end screen)
CAND_SIGNALS = ("title", "thumb_emb", "thumb_outline", "hq2_emb", "hq2_outline")
SCORE_SIGNALS = CAND_SIGNALS + ("description", "tags", "duration_fit", "days")
LOWER_IS_CLOSER = {"duration_fit", "days"}
GATE_SIGNALS = ("frames_outline", "frames_emb")
EMBED_SIZE = (224, 126)     # DINOv2 input (w, h), 16 x 9 patches: enough for near-duplicates, fast on CPU


# --- Pure helpers (tested) ----------------------------------------------------------------


def is_compilation(title: str, duration_s: float) -> bool:
    return duration_s > COMPILATION_S or bool(COMPILATION_RE.search(title))


def pair_type(ch_x: str, ch_y: str) -> str:
    return "AxB" if ch_x != ch_y else f"{ch_x}x{ch_y}"


def crop_bars(img: np.ndarray, dark: float = 14.0) -> np.ndarray:
    """Trim the black letterbox bars YouTube adds to 4:3 thumbnails of 16:9 videos."""
    rows = img.mean(axis=(1, 2))
    top, bot, lim = 0, len(rows), len(rows) // 4
    while top < lim and rows[top] < dark:
        top += 1
    while len(rows) - bot < lim and rows[bot - 1] < dark:
        bot -= 1
    return img[top:bot]


def outline_vector(img: np.ndarray, size: tuple[int, int] = (64, 36)) -> np.ndarray:
    """Blurred edge map as a zero-mean unit vector: its dot product is the edge maps' correlation,
    which ignores color (catches recolors)."""
    g = cv2.cvtColor(cv2.resize(img, (192, 108), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    e = cv2.resize(vis.edges(g).astype(np.float32), size, interpolation=cv2.INTER_AREA).ravel()
    e -= e.mean()
    n = np.linalg.norm(e)
    return e / n if n > 0 else e


def outline_map(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(cv2.resize(img, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    return vis.edges(g)


BOILERPLATE = {"nursery", "rhymes", "rhyme", "kids", "kid", "tv", "channel", "songs", "song", "baby",
               "babies", "children", "childrens", "toddlers", "for", "and", "the", "3d", "cartoon",
               "cartoons", "videos", "video", "learn", "preschool", "with", "of", "by", "in", "a"}


def title_text(title: str) -> str:
    return " ".join(w for w in md.tokens(title) if w not in BOILERPLATE)


class TitleIndex:
    """Char 3-5-gram TF-IDF over all titles (boilerplate removed); rows are L2-normalized."""

    def __init__(self, titles: dict[str, str]):
        self.ids = list(titles)
        self.row = {v: i for i, v in enumerate(self.ids)}
        grams = [self._grams(title_text(titles[v])) for v in self.ids]
        vocab: dict[str, int] = {}
        for g in grams:
            for x in g:
                vocab.setdefault(x, len(vocab))
        df = np.zeros(len(vocab))
        rows, cols, vals = [], [], []
        for i, g in enumerate(grams):
            c = Counter(g)
            for x, n in c.items():
                rows.append(i)
                cols.append(vocab[x])
                vals.append(1 + math.log(n))
                df[vocab[x]] += 1
        idf = np.log((1 + len(grams)) / (1 + df)) + 1
        m = sparse.csr_matrix((vals, (rows, cols)), shape=(len(grams), len(vocab)))
        m = m.multiply(idf).tocsr()
        norms = np.sqrt(np.asarray(m.multiply(m).sum(axis=1)).ravel())
        norms[norms == 0] = 1
        self.m = sparse.diags(1 / norms) @ m

    @staticmethod
    def _grams(text: str) -> list[str]:
        t = f" {text} "
        return [t[i:i + n] for n in (3, 4, 5) for i in range(len(t) - n + 1)]

    def sims(self, v: str, others: list[str]) -> np.ndarray:
        if not others:
            return np.zeros(0)
        a = self.m[self.row[v]]
        b = self.m[[self.row[o] for o in others]]
        return np.asarray((b @ a.T).todense()).ravel()


def closer_than(sorted_vals: np.ndarray, x: float, lower_is_closer: bool) -> float:
    n = len(sorted_vals)
    if n == 0 or x is None or math.isnan(x):
        return 0.0
    if lower_is_closer:
        return float((n - np.searchsorted(sorted_vals, x, side="right")) / n)
    return float(np.searchsorted(sorted_vals, x, side="left") / n)


def screen_score(pcts: dict[str, float], n: int) -> float:
    """Sum of -log10(share of random pairs at least as close) over all signals: a pair that is
    rare on one signal or unusual on several scores high, so no single signal is the gate."""
    floor = 1 / (n + 1)
    return float(sum(-math.log10(max(1 - p, floor)) for p in pcts.values()))


def duration_fit(da: float, db: float) -> float:
    return max(0.0, abs(da - db) - END_SCREEN_S)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


# --- Storage -------------------------------------------------------------------------------


SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, side TEXT, title TEXT, published TEXT,
  duration REAL, views INTEGER, likes INTEGER, description TEXT, tags TEXT, compilation INTEGER,
  rank INTEGER, images_done INTEGER DEFAULT 0, compared INTEGER DEFAULT 0, missing TEXT);
CREATE TABLE IF NOT EXISTS pairs (a TEXT, b TEXT, type TEXT, sims TEXT, cand_fired TEXT,
  score REAL, scored INTEGER DEFAULT 0, gate TEXT, gate_fired TEXT, gate_state TEXT,
  review TEXT, label TEXT, confidence REAL, dl_state TEXT, PRIMARY KEY (a, b));
CREATE INDEX IF NOT EXISTS pairs_gate ON pairs (gate_state);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS compared (type TEXT PRIMARY KEY, n INTEGER);
"""


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)
    con.executescript(SCHEMA)
    return con


def kv_get(con, key, default=None):
    r = con.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def kv_set(con, key, value):
    con.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value)))


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Filter 0: inventory -------------------------------------------------------------------


def inventory(con) -> None:
    if con.execute("SELECT COUNT(*) FROM videos").fetchone()[0]:
        return
    ids: dict[str, str] = {}
    for side, ch in CHANNELS.items():
        token = ""
        while True:
            params = {"playlistId": "UU" + ch[2:], "part": "contentDetails", "maxResults": "50"}
            if token:
                params["pageToken"] = token
            d = yt.api("playlistItems", params, EXP, "search: inventory",
                       target=f"UU{ch[2:]}:{token or 'first'}")
            for it in d.get("items", []):
                ids[it["contentDetails"]["videoId"]] = side
            token = d.get("nextPageToken", "")
            if not token:
                break
        log_event(f"inventory: {sum(1 for s in ids.values() if s == side)} uploads listed for {side}")
    vids = sorted(ids)
    rng = random.Random(11)
    order = vids[:]
    rng.shuffle(order)
    # The seed pair goes first: the seed check runs on it, and it's in the calibration anyway.
    order = list(SEED) + [v for v in order if v not in SEED]
    rank = {v: i for i, v in enumerate(order)}
    rows = []
    for i in range(0, len(vids), 50):
        chunk = vids[i:i + 50]
        d = yt.api("videos", {"id": ",".join(chunk), "part": "snippet,contentDetails,statistics"},
                   EXP, "search: inventory", target=f"{len(chunk)} videos from {chunk[0]}")
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            dur = md.iso_duration(it["contentDetails"].get("duration", "PT0S"))
            side = ("A" if sn["channelId"] == CHANNELS["A"]
                    else "B" if sn["channelId"] == CHANNELS["B"] else None)
            if side is None:
                continue
            rows.append((it["id"], side, sn["title"], sn["publishedAt"], dur, int(st.get("viewCount", 0)),
                         int(st.get("likeCount", 0)), sn.get("description", ""),
                         json.dumps(sn.get("tags", [])), int(is_compilation(sn["title"], dur)),
                         rank[it["id"]]))
    con.executemany("INSERT OR IGNORE INTO videos (id, side, title, published, duration, views, likes, "
                    "description, tags, compilation, rank) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    log_event(f"inventory: {len(rows)} videos with metadata of {len(vids)} listed")


# --- Progress ------------------------------------------------------------------------------


EVENTS = OUT / "events.log"


def log_event(msg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = f"{now()}  {msg}"
    print(line, flush=True)
    with EVENTS.open("a") as f:
        f.write(line + "\n")


# --- Filter 1: images (a thread) ----------------------------------------------------------


IMG_URL = {"thumb": "hqdefault", "hq1": "hq1", "hq2": "hq2", "hq3": "hq3"}


class Fetcher(threading.Thread):
    """One image at a time (yt.image paces them); gate frames before bulk images."""

    def __init__(self):
        super().__init__(daemon=True)
        self.heap: list = []
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        self.queued: set = set()
        self.done: queue.Queue = queue.Queue()
        self.seq = 0
        self.requests = 0
        self.errors = 0
        self.started_at = time.time()
        self.paused_until = 0.0

    def put(self, prio: int, video: str, kind: str) -> None:
        with self.cv:
            if (video, kind) in self.queued:
                return
            self.queued.add((video, kind))
            self.seq += 1
            heapq.heappush(self.heap, (prio, self.seq, video, kind))
            self.cv.notify()

    def pending(self) -> Counter:
        with self.lock:
            return Counter("gate" if p == 0 else "baseline" if p == 1 else "bulk" for p, *_ in self.heap)

    def run(self) -> None:
        streak = 0
        while True:
            with self.cv:
                while not self.heap:
                    self.cv.wait()
                prio, _, video, kind = heapq.heappop(self.heap)
            url = f"https://i.ytimg.com/vi/{video}/{IMG_URL[kind]}.jpg"
            for attempt in range(4):
                try:
                    before = yt._next_at["image"]
                    path = yt.image(url, EXP, "thumbnail" if kind == "thumb" else "auto-frame", video,
                                    f"search: {kind}")
                    if yt._next_at["image"] != before:
                        self.requests += 1
                    self.done.put((video, kind, str(path) if path else None))
                    streak = 0
                    break
                except Exception as e:  # network trouble: back off, then go on
                    self.errors += 1
                    streak += 1
                    log_event(f"image error {video} {kind} (try {attempt + 1}): {e!r}")
                    time.sleep(30 * (attempt + 1) * (3 if streak >= 5 else 1))
            else:
                self.done.put((video, kind, "error"))


# --- Filter 6: downloads (a thread) --------------------------------------------------------


class Downloader(threading.Thread):
    def __init__(self, limit: int):
        super().__init__(daemon=True)
        self.q: queue.Queue = queue.Queue()
        self.done: queue.Queue = queue.Queue()
        self.limit = limit
        self.stopped = ""

    def run(self) -> None:
        while True:
            v = self.q.get()
            if self.stopped:
                self.done.put((v, "skipped"))
                continue
            if yt.video_path(v).exists():
                self.done.put((v, "ok"))
                continue
            try:
                if yt.player_used_today() >= self.limit:
                    raise yt.BudgetError(f"search's player budget ({self.limit}) used")
                yt.download(v, EXP, "search: download")
                self.done.put((v, "ok"))
            except yt.BudgetError as e:
                if "blocked" in str(e):  # wait while the collector is blocked, then go on
                    log_event(f"downloads wait: {e}")
                    time.sleep(600)
                    self.q.put(v)
                    continue
                self.stopped = f"{v}: {e}"
                log_event(f"downloads stopped: {self.stopped}")
                self.done.put((v, "failed"))
            except Exception as e:
                # Stop at the first failed download (PLAN.md, Constraints).
                self.stopped = f"{v}: {e}"
                log_event(f"downloads stopped: {self.stopped}")
                self.done.put((v, "failed"))


# --- The chain -----------------------------------------------------------------------------


class Search:
    def __init__(self, player_limit: int):
        self.con = connect()
        self.fetcher = Fetcher()
        self.downloader = Downloader(player_limit)
        self.t0 = time.time()
        self.vids: dict[str, dict] = {}
        self.feat: dict[str, dict[str, np.ndarray]] = {}
        self.pending_embed: list[tuple[str, str, np.ndarray]] = []
        self.compared: list[str] = []       # videos already compared, in arrival order
        self.mat = {k: np.zeros((8000, 384 if k.endswith("emb") else 64 * 36), np.float32)
                    for k in ("thumb_emb", "thumb_outline", "hq2_emb", "hq2_outline")}
        self.cal: dict | None = None
        self.gate_cal: dict | None = None
        self.counts = Counter()           # pairs compared per type (filter 2 input)
        self.history: list[tuple[float, int]] = []

    # -- setup --

    def load(self) -> None:
        inventory(self.con)
        cur = self.con.execute("SELECT id, side, title, published, duration, views, likes, description, "
                               "tags, compilation, rank, images_done, compared FROM videos")
        cols = [d[0] for d in cur.description]
        for row in cur:
            r = dict(zip(cols, row, strict=True))
            r["tags"] = {md.norm_tag(t) for t in json.loads(r["tags"])}
            r["desc_words"] = set(md.tokens(md.URL_RE.sub(" ", r["description"])))
            self.vids[r["id"]] = r
        self.titles = TitleIndex({v: r["title"] for v, r in self.vids.items()})
        self.cal = kv_get(self.con, "calibration")
        if self.cal:
            for t in TYPES:
                for s in SCORE_SIGNALS:
                    self.cal["dist"][t][s] = np.array(self.cal["dist"][t][s])
        self.gate_cal = kv_get(self.con, "gate_calibration")
        self.counts = Counter({t: n for t, n in self.con.execute("SELECT type, n FROM compared")})
        eligible = [v for v, r in self.vids.items() if not r["compilation"]]
        log_event(f"loaded {len(self.vids)} videos, {len(eligible)} eligible "
                  f"({len(self.vids) - len(eligible)} compilations left out)")

    def eligible(self) -> list[str]:
        return sorted((v for v, r in self.vids.items() if not r["compilation"]),
                      key=lambda v: self.vids[v]["rank"])

    # -- features --

    def feat_path(self, v: str) -> Path:
        return FEAT / f"{v}.npz"

    def load_feat(self, v: str) -> dict:
        if v not in self.feat:
            p = self.feat_path(v)
            self.feat[v] = dict(np.load(p)) if p.exists() else {}
        return self.feat[v]

    def save_feat(self, v: str) -> None:
        FEAT.mkdir(parents=True, exist_ok=True)
        np.savez(self.feat_path(v), **self.feat[v])

    def on_image(self, v: str, kind: str, path: str | None) -> None:
        f = self.load_feat(v)
        if path in (None, "error"):
            f[f"{kind}_missing"] = np.array(1)
            self.save_feat(v)
            return
        img = crop_bars(vis.load_image(path))
        f[f"{kind}_outline"] = outline_vector(img)
        if kind in ("hq1", "hq2", "hq3"):
            f[f"{kind}_map"] = outline_map(img)
        self.pending_embed.append((v, kind, img))

    def flush_embed(self) -> None:
        if not self.pending_embed:
            return
        batch, self.pending_embed = self.pending_embed, []
        embs = vis.embed([im for _, _, im in batch], size=EMBED_SIZE)
        touched = set()
        for (v, kind, _), e in zip(batch, embs, strict=True):
            self.feat[v][f"{kind}_emb"] = e.astype(np.float32)
            touched.add(v)
        for v in touched:
            self.save_feat(v)

    def has(self, v: str, kinds) -> bool:
        f = self.load_feat(v)
        return all(f"{k}_emb" in f or f"{k}_missing" in f for k in kinds)

    def vec(self, v: str, key: str) -> np.ndarray:
        f = self.load_feat(v)
        if key in f:
            return f[key]
        dim = 384 if key.endswith("emb") else 64 * 36
        return np.zeros(dim, np.float32)

    # -- pair signals --

    def sims_against(self, v: str, others: list[str], mats: dict[str, np.ndarray] | None = None) -> dict:
        out = {"title": self.titles.sims(v, others)}
        for key in self.mat:
            m = mats[key] if mats is not None else np.stack([self.vec(o, key) for o in others])
            out[key] = m @ self.vec(v, key) if len(others) else np.zeros(0)
        return out

    def api_signals(self, x: str, y: str) -> dict:
        a, b = self.vids[x], self.vids[y]
        return {"description": jaccard(a["desc_words"], b["desc_words"]),
                "tags": jaccard(a["tags"], b["tags"]),
                "duration_fit": duration_fit(a["duration"], b["duration"]),
                "days": md.timing_signal(a["published"], b["published"])["days"]}

    def ptype(self, x: str, y: str) -> str:
        return pair_type(self.vids[x]["side"], self.vids[y]["side"])

    # -- calibration --

    def calibrate(self, ids: list[str]) -> None:
        dist = {t: {s: [] for s in SCORE_SIGNALS} for t in TYPES}
        for i, v in enumerate(ids[1:], 1):
            others = ids[:i]
            s = self.sims_against(v, others)
            for j, o in enumerate(others):
                t = self.ptype(o, v)
                for k in CAND_SIGNALS:
                    dist[t][k].append(float(s[k][j]))
                for k, val in self.api_signals(o, v).items():
                    dist[t][k].append(val)
        cal = {"n_videos": len(ids), "at": now(), "dist": {}, "p99": {}, "n_pairs": {}}
        for t in TYPES:
            cal["n_pairs"][t] = len(dist[t]["title"])
            cal["dist"][t] = {s: np.sort(np.array(dist[t][s], np.float32)) for s in SCORE_SIGNALS}
            cal["p99"][t] = {s: float(np.percentile(cal["dist"][t][s], 99)) for s in CAND_SIGNALS}
        # Score of every calibration pair, to set the score cut.
        scores = {}
        for t in TYPES:
            d = cal["dist"][t]
            n = len(d["title"])
            if n == 0:
                scores[t] = np.zeros(0)
                continue
            floor = 1 / (n + 1)
            total_t = np.zeros(n)
            for s in SCORE_SIGNALS:
                raw = np.array(dist[t][s], np.float32)
                if s in LOWER_IS_CLOSER:
                    p = (n - np.searchsorted(d[s], raw, side="right")) / n
                else:
                    p = np.searchsorted(d[s], raw, side="left") / n
                total_t += -np.log10(np.maximum(1 - p, floor))
            scores[t] = total_t
        self.cal = cal
        seed = self.pair_score(*SEED)
        total = sum(cal["n_pairs"].values())
        all_scores = np.sort(np.concatenate(list(scores.values())))[::-1]
        q = SCORE_TARGET / 17.3e6
        k = max(1, int(round(q * total)))
        target_cut = float(all_scores[min(k, len(all_scores)) - 1])
        cal["seed_score"] = seed["score"]
        cal["seed_pcts"] = seed["pcts"]
        cal["target_cut"] = target_cut
        # Pass the seed with margin: at most 3/4 of its score.
        cal["score_cut"] = min(target_cut, 0.75 * seed["score"])
        cal["score_quantiles"] = {t: [float(np.percentile(scores[t], x)) for x in (50, 90, 99, 99.9)]
                                  for t in TYPES}
        save = {**cal, "dist": {t: {s: cal["dist"][t][s].tolist() for s in SCORE_SIGNALS} for t in TYPES}}
        kv_set(self.con, "calibration", save)
        self.con.commit()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "calibration.json").write_text(json.dumps(
            {k: v for k, v in cal.items() if k != "dist"}, indent=1))
        log_event(f"calibration on {len(ids)} videos, pairs {cal['n_pairs']}: "
                  f"seed score {seed['score']:.2f}, "
                  f"target cut {target_cut:.2f}, cut {cal['score_cut']:.2f}")

    def pair_score(self, x: str, y: str, sims: dict | None = None) -> dict:
        t = self.ptype(x, y)
        if sims is None:
            s = self.sims_against(y, [x])
            sims = {k: float(s[k][0]) for k in CAND_SIGNALS}
        vals = {**sims, **self.api_signals(x, y)}
        d = self.cal["dist"][t]
        n = len(d["title"])
        pcts = {s: closer_than(d[s], vals[s], s in LOWER_IS_CLOSER) for s in SCORE_SIGNALS}
        return {"type": t, "vals": vals, "pcts": pcts, "score": screen_score(pcts, n)}

    def gate_calibrate(self) -> None:
        sample = kv_get(self.con, "gate_sample")
        vals = {t: {g: [] for g in GATE_SIGNALS} for t in TYPES}
        for i, x in enumerate(sample):
            for y in sample[i + 1:]:
                t = self.ptype(x, y)
                g = self.gate_signals(x, y)
                for k in GATE_SIGNALS:
                    vals[t][k].append(g[k])
        cal = {"n_videos": len(sample), "at": now(),
               "n_pairs": {t: len(vals[t]["frames_emb"]) for t in TYPES},
               "p99": {t: {k: float(np.percentile(vals[t][k], 99)) for k in GATE_SIGNALS} for t in TYPES},
               "p999_thumb": {t: {k: float(np.percentile(self.cal["dist"][t][k], 99.9))
                                  for k in ("thumb_emb", "thumb_outline")} for t in TYPES}}
        self.gate_cal = cal
        kv_set(self.con, "gate_calibration", cal)
        self.con.commit()
        (OUT / "gate_calibration.json").write_text(json.dumps(cal, indent=1))
        log_event(f"gate calibration on {len(sample)} videos, pairs {cal['n_pairs']}: p99 {cal['p99']}")

    def gate_signals(self, x: str, y: str) -> dict:
        fx, fy = self.load_feat(x), self.load_feat(y)
        ks = ("hq1", "hq2", "hq3")
        outl, emb = [], []
        for a in ks:
            for b in ks:
                if f"{a}_map" in fx and f"{b}_map" in fy:
                    outl.append(vis.ssim(fx[f"{a}_map"], fy[f"{b}_map"]))
                if f"{a}_emb" in fx and f"{b}_emb" in fy:
                    emb.append(float(fx[f"{a}_emb"] @ fy[f"{b}_emb"]))
        return {"frames_outline": max(outl, default=0.0), "frames_emb": max(emb, default=0.0)}

    # -- filters 2-4 for one arriving video --

    def compare(self, v: str) -> None:
        others = self.compared
        if others:
            n = len(others)
            s = self.sims_against(v, others, {k: m[:n] for k, m in self.mat.items()})
            types = [self.ptype(o, v) for o in others]
            self.counts.update(types)
            p99 = self.cal["p99"]
            rows = []
            for j, o in enumerate(others):
                t = types[j]
                fired = [k for k in CAND_SIGNALS if s[k][j] > p99[t][k]]
                if not fired:
                    continue
                sims = {k: float(s[k][j]) for k in CAND_SIGNALS}
                x, y = (o, v) if self.vids[o]["published"] <= self.vids[v]["published"] else (v, o)
                if t == "AxB" and self.vids[x]["side"] == "B":
                    x, y = y, x
                sc = self.pair_score(x, y, sims)
                passed = sc["score"] >= self.cal["score_cut"]
                rows.append((x, y, t, json.dumps({k: round(val, 4) for k, val in sc["vals"].items()}),
                             ",".join(fired), sc["score"], int(passed), "wait" if passed else None))
                if passed:
                    for z in (x, y):
                        for k in ("hq1", "hq3"):
                            self.fetcher.put(0, z, k)
            self.con.executemany("INSERT OR IGNORE INTO pairs (a, b, type, sims, cand_fired, score, scored, "
                                 "gate_state) VALUES (?,?,?,?,?,?,?,?)", rows)
            self.con.executemany("INSERT OR REPLACE INTO compared VALUES (?, ?)", list(self.counts.items()))
        self.add_compared(v)
        self.con.execute("UPDATE videos SET compared = 1 WHERE id = ?", (v,))

    def add_compared(self, v: str) -> None:
        for k in self.mat:
            self.mat[k][len(self.compared)] = self.vec(v, k)
        self.compared.append(v)

    def run_gate(self) -> None:
        if not self.gate_cal:
            return
        rows = self.con.execute("SELECT a, b, type, score FROM pairs WHERE gate_state = 'wait'").fetchall()
        for a, b, t, _score in rows:
            if not (self.has(a, ("hq1", "hq2", "hq3")) and self.has(b, ("hq1", "hq2", "hq3"))):
                continue
            g = self.gate_signals(a, b)
            s = self.sims_against(b, [a])
            th = {k: float(s[k][0]) for k in ("thumb_emb", "thumb_outline")}
            fired = [k for k in GATE_SIGNALS if g[k] > self.gate_cal["p99"][t][k]]
            fired += [k for k in th if th[k] > self.gate_cal["p999_thumb"][t][k]]
            state = "pass" if fired else "stop"
            review = None
            if fired:
                review = "queue"
            elif random.random() < AUDIT_SHARE:
                n_audit = self.con.execute("SELECT COUNT(*) FROM pairs WHERE review = 'audit'").fetchone()[0]
                if n_audit < AUDIT_MAX:
                    review = "audit"
            self.con.execute("UPDATE pairs SET gate = ?, gate_fired = ?, gate_state = ?, review = ? "
                             "WHERE a = ? AND b = ?",
                             (json.dumps({k: round(x, 4) for k, x in {**g, **th}.items()}),
                              ",".join(fired), state, review, a, b))

    # -- filter 5/6: labels and downloads --

    def read_labels(self) -> None:
        for p in sorted((OUT / "labels").glob("*.json")):
            if kv_get(self.con, f"labels:{p.name}"):
                continue
            try:
                data = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            for it in data:
                self.con.execute("UPDATE pairs SET label = ?, confidence = ?, review = 'done' "
                                 "WHERE a = ? AND b = ?",
                                 (it["label"], float(it.get("confidence", 0)), it["a"], it["b"]))
            kv_set(self.con, f"labels:{p.name}", True)
            log_event(f"labels read: {p.name} ({len(data)} pairs)")
        self.select_downloads()

    def select_downloads(self) -> None:
        """Confident re-skins, most different strategy profiles first, round robin over pair types."""
        if self.downloader.stopped:
            return
        rows = self.con.execute(
            "SELECT a, b, type, score, cand_fired, gate_fired, dl_state FROM pairs WHERE label = 're-skin' "
            "AND confidence >= 0.7").fetchall()
        queued = [r for r in rows if r[6]]
        todo = [r for r in rows if not r[6]]
        if not todo:
            return
        profiles = Counter((r[4], r[5]) for r in queued)
        per_type = Counter(r[2] for r in queued)
        videos = {v for r in queued for v in r[:2]}
        while todo:
            t = min({r[2] for r in todo}, key=lambda x: per_type[x])
            cands = [r for r in todo if r[2] == t]
            r = min(cands, key=lambda r: (profiles[(r[4], r[5])], -r[3]))
            new = {r[0], r[1]} - videos
            if len(videos | new) > self.player_budget_videos():
                break
            todo.remove(r)
            profiles[(r[4], r[5])] += 1
            per_type[t] += 1
            videos |= new
            for v in (r[0], r[1]):
                self.downloader.q.put(v)
            self.con.execute("UPDATE pairs SET dl_state = 'queued' WHERE a = ? AND b = ?", (r[0], r[1]))

    def player_budget_videos(self) -> int:
        return self.downloader.limit - 10  # ~10 kept for baseline videos

    # -- progress --

    def progress(self) -> dict:
        c = self.con
        el = [v for v, r in self.vids.items() if not r["compilation"]]
        imaged = sum(1 for v in el if self.has(v, ("thumb", "hq2")))
        n_compared = len(self.compared)
        total_pairs = {"AxB": 0, "AxA": 0, "BxB": 0}
        na = sum(1 for v in el if self.vids[v]["side"] == "A")
        nb = len(el) - na
        total_pairs = {"AxB": na * nb, "AxA": na * (na - 1) // 2, "BxB": nb * (nb - 1) // 2}

        def by_type(where: str) -> dict:
            out = dict.fromkeys(TYPES, 0)
            for t, n in c.execute(f"SELECT type, COUNT(*) FROM pairs WHERE {where} GROUP BY type"):
                out[t] = n
            return out

        cand = by_type("1")
        scored = by_type("scored = 1")
        gate_wait = by_type("gate_state = 'wait'")
        gate_pass = by_type("gate_state = 'pass'")
        gate_stop = by_type("gate_state = 'stop'")
        review_queue = by_type("review IN ('queue', 'audit', 'sent')")
        labelled = by_type("review = 'done'")
        labels = {f"{t}|{lab}": n for t, lab, n in c.execute(
            "SELECT type, label, COUNT(*) FROM pairs WHERE label IS NOT NULL GROUP BY type, label")}
        dl = {s: n for s, n in c.execute("SELECT dl_state, COUNT(*) FROM pairs WHERE dl_state IS NOT NULL "
                                         "GROUP BY dl_state")}
        pend = self.fetcher.pending()
        elapsed = time.time() - self.t0
        self.history.append((time.time(), self.fetcher.requests))
        recent = [h for h in self.history if h[0] >= time.time() - 600]
        rate = ((recent[-1][1] - recent[0][1]) / (recent[-1][0] - recent[0][0])
                if len(recent) >= 2 and recent[-1][0] > recent[0][0] else 0.0)
        left = sum(pend.values())
        eta_s = left / rate if rate > 0 else None
        downloaded = sum(1 for v in {v for r in c.execute("SELECT a, b FROM pairs WHERE dl_state IS NOT NULL")
                                     for v in r} if yt.video_path(v).exists())
        return {
            "at": now(), "elapsed_min": round(elapsed / 60, 1),
            "inventory": {"videos": len(self.vids), "eligible": len(el),
                          "compilations": len(self.vids) - len(el), "A": na, "B": nb},
            "images": {"videos_done": imaged, "videos_total": len(el),
                       "requests_this_run": self.fetcher.requests,
                       "errors": self.fetcher.errors, "queue": dict(pend), "rate_per_s": round(rate, 2),
                       "eta_min": round(eta_s / 60, 1) if eta_s else None},
            "calibrated": bool(self.cal), "gate_calibrated": bool(self.gate_cal),
            "candidates": {"videos_compared": n_compared, "pairs_compared": dict(self.counts),
                           "pairs_total": total_pairs, "passed": cand},
            "score": {"in": cand, "passed": scored, "cut": self.cal["score_cut"] if self.cal else None},
            "gate": {"in": scored, "waiting_frames": gate_wait, "passed": gate_pass, "stopped": gate_stop},
            "review": {"queued": review_queue, "labelled": labelled, "labels": labels},
            "download": {"pairs": dl, "videos_downloaded": downloaded, "stopped": self.downloader.stopped,
                         "player_today": yt.player_used_today()},
        }

    def write_progress(self) -> None:
        p = self.progress()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "progress.json").write_text(json.dumps(p, indent=1))
        with (OUT / "progress.jsonl").open("a") as f:
            f.write(json.dumps(p) + "\n")
        tsv = OUT / "progress.tsv"
        new = not tsv.exists()
        with tsv.open("a") as f:
            if new:
                f.write("at\telapsed_min\tstage\tpair_type\tin\tpassed\tpass_rate\twaiting\tnote\n")

            def row(stage, t, n_in, n_pass, waiting="", note=""):
                rate = f"{n_pass / n_in:.6f}" if n_in else ""
                f.write(f"{p['at']}\t{p['elapsed_min']}\t{stage}\t{t}\t{n_in}\t{n_pass}\t{rate}\t{waiting}\t{note}\n")

            inv = p["inventory"]
            row("0-inventory", "all", inv["videos"], inv["eligible"],
                note=f"{inv['compilations']} compilations")
            im = p["images"]
            row("1-images", "all", im["videos_total"], im["videos_done"], sum(im["queue"].values()),
                f"rate {im['rate_per_s']}/s; eta {im['eta_min']} min; requests {im['requests_this_run']}")
            for t in TYPES:
                ca = p["candidates"]
                row("2-candidates", t, ca["pairs_compared"].get(t, 0), ca["passed"][t],
                    note=f"of {ca['pairs_total'][t]} pairs in all")
                row("3-score", t, ca["passed"][t], p["score"]["passed"][t])
                g = p["gate"]
                row("4-gate", t, g["passed"][t] + g["stopped"][t], g["passed"][t], g["waiting_frames"][t])
                rv = p["review"]
                row("5-review", t, rv["labelled"][t], sum(n for k, n in rv["labels"].items()
                                                          if k == f"{t}|re-skin"), rv["queued"][t])
            row("6-download", "all", sum(p["download"]["pairs"].values()), p["download"]["videos_downloaded"],
                note=p["download"]["stopped"])

    # -- main loop --

    def run(self) -> None:
        self.load()
        el = self.eligible()
        # Seed check first: all its frames, ahead of everything.
        for v in SEED:
            for k in ("thumb", "hq1", "hq2", "hq3"):
                self.fetcher.put(0, v, k)
        for v in el:
            if not self.has(v, ("thumb", "hq2")):
                for k in ("thumb", "hq2"):
                    self.fetcher.put(2, v, k)
        self.fetcher.start()
        self.downloader.start()
        last_progress = 0.0
        # Resume: videos compared before (in rank order) are re-added to the matrices.
        for v in el:
            if self.vids[v]["compared"] and self.has(v, ("thumb", "hq2")):
                self.add_compared(v)
        for a, b in self.con.execute("SELECT a, b FROM pairs WHERE gate_state = 'wait'").fetchall():
            for z in (a, b):
                for k in ("hq1", "hq3"):
                    self.fetcher.put(0, z, k)
        if not self.gate_cal and kv_get(self.con, "gate_sample"):
            for z in kv_get(self.con, "gate_sample"):
                for k in ("hq1", "hq3"):
                    self.fetcher.put(1, z, k)
        while True:
            got = 0
            try:
                while got < 64:
                    v, kind, path = self.fetcher.done.get(timeout=1 if got == 0 else 0.01)
                    self.on_image(v, kind, path)
                    got += 1
            except queue.Empty:
                pass
            if len(self.pending_embed) >= 16 or (self.pending_embed and got == 0):
                self.flush_embed()
            ready = [v for v in el if not self.vids[v]["compared"] and self.has(v, ("thumb", "hq2"))]
            if not self.cal and (len(ready) >= N_CALIBRATION or (ready and len(ready) == len(
                    [v for v in el if not self.vids[v]["compared"]]))):
                cal_ids = sorted(ready, key=lambda v: self.vids[v]["rank"])
                self.calibrate(cal_ids)
                # The gate's random baseline: hq1/hq3 for a sample of these videos.
                rng = random.Random(5)
                sample = []
                for side, n in GATE_SAMPLE.items():
                    pool = [v for v in cal_ids if self.vids[v]["side"] == side]
                    sample += rng.sample(pool, min(n, len(pool)))
                kv_set(self.con, "gate_sample", sample)
                for z in sample:
                    for k in ("hq1", "hq3"):
                        self.fetcher.put(1, z, k)
                self.con.commit()
            if self.cal:
                for v in sorted(ready, key=lambda v: self.vids[v]["rank"]):
                    self.compare(v)
                    self.vids[v]["compared"] = 1
                if ready:
                    self.con.commit()
                if not self.gate_cal:
                    sample = kv_get(self.con, "gate_sample") or []
                    if sample and all(self.has(z, ("hq1", "hq2", "hq3")) for z in sample):
                        self.gate_calibrate()
                self.run_gate()
                self.con.commit()
            if time.time() - last_progress >= 60:
                self.read_labels()
                while not self.downloader.done.empty():
                    v, state = self.downloader.done.get()
                    log_event(f"download {v}: {state}")
                self.con.commit()
                self.write_progress()
                last_progress = time.time()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--player-limit", type=int, default=200)
    sub.add_parser("progress")
    a = ap.parse_args()
    if a.cmd == "run":
        s = Search(a.player_limit)
        try:
            s.run()
        except Exception:
            log_event("crashed: " + traceback.format_exc())
            raise
    elif a.cmd == "progress":
        print((OUT / "progress.json").read_text())


if __name__ == "__main__":
    main()
