"""Search: other channels, step 1: discover the dataset's channels and their family, group them by owner.

PLAN.md, Search: other channels, Step 1. API only: no images, no player requests.

  fetch  Data API requests, all cached by tools/yt.py (reruns cost nothing). When the day's API budget
         is used up, waits for the next Pacific day and carries on; safe to stop and restart.
  group  Offline: owner evidence -> links -> networks -> groups, into results/channels/.

Run (from experiments/): uv run python 001-variant-pairs/channels.py fetch|group
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # experiments/
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "tools"))

import metadata as md  # noqa: E402
import yt  # noqa: E402

EXP = "001"
NOTE = "channels: step 1"
DATASETS = {"reference": REPO / "backend" / "data" / "videos.tsv",
            "collected": REPO / "backend" / "data" / "collected" / "2026.tsv"}
OUT = HERE / "results" / "channels"
UPLOADS_PER_FAMILY = 50
# Part 2's seed channels (Kids TV, Kids Channel): always in, so the grouping can be checked on them.
IN_DATASET = ("reference", "collected", "both")
SEEDS = {"UC7Pq3Ko42YpkCB_Q4E981jw": "Kids TV", "UCv7TYWhF5jhtuY3FDPf06Aw": "Kids Channel"}

# A featured-channels section with one of these words in its title lists the channel's own company.
FAMILY_SECTION_RE = re.compile(
    r"\bour\b|\bmy\b|sister|official|famil|network|group|universe|languages?\b|idiomas|langues|sprachen|"
    r"\b(more|other|all)\b.*\bchannels?\b|worldwide|around the world|international|группа|nuestr|notre|unser",
    re.I)
# ...unless it names friends or other people's channels.
NOT_FAMILY_SECTION_RE = re.compile(r"friend|amig|ami[se]\b|freunde|друз|buddies|partner|recommend|suggest|"
                                   r"similar|favou?rite|must watch|featured|destacad|추천|"
                                   r"\blove|great|awesome|\bcool\b|\bbest\b|\blike\b|enjoy|related|check out",
                                   re.I)
# Copyright "holders" that name nobody: legal boilerplate and placeholders.
JUNK_HOLDER_RE = re.compile(
    r"respective|original owner|owners?$|all rights|reserved|disclaimer|section 107|fair use|act,? 1976|"
    r"^(by|the|and|of|for|to|this|our|my|channel|video|videos|music|youtube|free|kids|copyright)\b|"
    r"\b(claim|infring|permission|allowance|strike|licen[sc]|copyright|intended)|^\W*$", re.I)
COMPANY_SUFFIX_RE = re.compile(
    r"\b(private|pvt|limited|ltd|llc|inc|incorporated|gmbh|corp|corporation|company|co|plc|s\.?a|s\.?l|"
    r"b\.?v|srl|pte|ag|oy|ab|llp)\b\.?", re.I)
# Link hosts that say nothing about the owner, beyond metadata.COMMON_HOSTS.
OTHER_HOSTS = {
    "amazon.co.uk", "amazon.com", "amazon.in", "amzn.to", "apple.co", "apple.com",
    "apps.apple.com", "artlist.io", "audiojungle.net", "bensound.com", "bit.ly",
    "buymeacoffee.com", "canva.com", "capcut.com", "creativecommons.org", "discord.com",
    "discord.gg", "docs.google.com", "drive.google.com", "envato.com", "epidemicsound.com",
    "facebook.com", "fb.com", "fb.me", "ffm.to", "flic.kr", "forms.gle", "found.ee", "freepik.com",
    "geni.us", "goo.gl", "google.com", "hyperurl.co", "incompetech.com", "instagr.am",
    "instagram.com", "itunes.apple.com", "ko-fi.com", "linkedin.com", "linktr.ee", "lnk.to",
    "m.facebook.com", "minecraft.net", "music.amazon.com", "music.apple.com", "naver.com",
    "onelink.me", "onelink.to", "open.spotify.com", "patreon.com", "paypal.com", "paypal.me",
    "pinterest.co.uk", "pinterest.com", "pixabay.com", "play.google.com", "rebrand.ly",
    "redbubble.com", "roblox.com", "shutterstock.com", "smarturl.it", "snapchat.com",
    "soundcloud.com", "spoti.fi", "spotify.com", "spreadshirt.com", "studio.youtube.com",
    "support.google.com", "t.me", "teespring.com", "threads.net", "tiktok.com", "tinyurl.com",
    "twitch.tv", "twitter.com", "vimeo.com", "vm.tiktok.com", "wa.me", "whatsapp.com", "x.com",
    "youtube.com"}
STRONG_KINDS = ("copyright", "app", "email")
EVIDENCE_KINDS = ("copyright", "app", "email", "domain")


def log_event(msg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}"
    print(line, flush=True)
    with (OUT / "events.log").open("a") as f:
        f.write(line + "\n")


# --- Inputs --------------------------------------------------------------------------------


def dataset_channels() -> dict[str, dict]:
    """Channel ID -> title, which datasets it is in, and its dataset video IDs."""
    out: dict[str, dict] = {}
    for name, path in DATASETS.items():
        with path.open(newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                c = out.setdefault(r["channel_id"], {"title": r["channel_title"], "sets": [], "videos": []})
                if name not in c["sets"]:
                    c["sets"].append(name)
                if r["video_id"] not in c["videos"]:
                    c["videos"].append(r["video_id"])
    return out


# --- Fetch ---------------------------------------------------------------------------------


def next_pacific_day(now: datetime | None = None) -> datetime:
    pacific = ZoneInfo("America/Los_Angeles")
    local = (now or datetime.now(UTC)).astimezone(pacific)
    midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), pacific)
    return midnight.astimezone(UTC) + timedelta(minutes=5)


def call(endpoint: str, params: dict[str, str], target: str = "") -> dict | None:
    """yt.api with two extras: waits for the next Pacific day when the budget is used up, and turns
    a 403/404 (deleted or closed channel, private playlist) into None."""
    while True:
        try:
            return yt.api(endpoint, params, EXP, NOTE, target=target)
        except yt.BudgetError as e:
            if not str(e).startswith("API budget"):
                raise
            until = next_pacific_day()
            log_event(f"budget used up for today ({e}); waiting until {until:%Y-%m-%d %H:%M} UTC")
            time.sleep(max(60.0, (until - datetime.now(UTC)).total_seconds()))
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            if e.code >= 500:
                time.sleep(30)
                continue
            raise


def chunks(xs: list[str], n: int = 50) -> list[list[str]]:
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def get(endpoint: str, params: dict[str, str], target: str, live: bool) -> dict | None:
    """One request: made (live, during fetch) or only read from the cache (group, offline). Both go
    through the same request shapes below, so group finds exactly what fetch saved."""
    return call(endpoint, params, target) if live else yt.api_cached(endpoint, params, target)


def channel_items(ids: list[str], live: bool = False) -> dict[str, dict]:
    out = {}
    for chunk in chunks(sorted(ids)):
        d = get("channels", {"id": ",".join(chunk), "maxResults": "50",
                             "part": "snippet,statistics,brandingSettings,contentDetails"},
                f"{len(chunk)} channels from {chunk[0]}", live)
        out |= {it["id"]: it for it in (d or {}).get("items", [])}
    return out


def sections(cid: str, live: bool = False) -> dict | None:
    return get("channelSections", {"channelId": cid, "part": "snippet,contentDetails"}, cid, live)


def video_items(ids: list[str], live: bool = False) -> dict[str, dict]:
    out = {}
    for chunk in chunks(sorted(ids)):
        d = get("videos", {"id": ",".join(chunk), "part": "snippet"},
                f"{len(chunk)} videos from {chunk[0]}", live)
        out |= {it["id"]: it for it in (d or {}).get("items", [])}
    return out


def uploads(cid: str, live: bool = False) -> list[str]:
    d = get("playlistItems", {"playlistId": "UU" + cid[2:], "part": "contentDetails",
                              "maxResults": str(UPLOADS_PER_FAMILY)}, f"UU{cid[2:]}:first", live)
    return [it["contentDetails"]["videoId"] for it in (d or {}).get("items", [])]


def featured_of(secs: dict | None) -> list[tuple[str, str]]:
    """(channel ID, section title) for every channel in a channel's featured-channels sections."""
    out = []
    for s in (secs or {}).get("items", []):
        if s.get("snippet", {}).get("type") != "multiplechannels":
            continue
        title = s["snippet"].get("title", "")
        out += [(c, title) for c in s.get("contentDetails", {}).get("channels", [])]
    return out


def family_of(dataset_ids: list[str]) -> list[str]:
    """Channels a dataset channel features that aren't in the dataset (from saved responses)."""
    known = set(dataset_ids)
    return sorted({f for cid in dataset_ids for f, _ in featured_of(sections(cid))} - known)


def extra_seeds(dataset_ids: list[str], family: list[str]) -> list[str]:
    """Seed channels neither in the dataset nor featured by it (Kids Channel): fetched like family
    channels, in a request of their own so the family's saved requests stay valid."""
    return sorted(set(SEEDS) - set(dataset_ids) - set(family))


def fetch() -> None:
    data = dataset_channels()
    ids = sorted(data)
    log_event(f"fetch: {len(ids)} dataset channels")
    channel_items(ids, live=True)
    for i, cid in enumerate(ids):
        sections(cid, live=True)
        if i % 100 == 99:
            log_event(f"fetch: featured channels of {i + 1} of {len(ids)}")
    vids = sorted({v for c in data.values() for v in c["videos"]})
    video_items(vids, live=True)
    log_event(f"fetch: descriptions of {len(vids)} dataset videos")
    family = family_of(ids)
    log_event(f"fetch: {len(family)} family channels (featured by a dataset channel, not in the dataset)")
    # Cheapest evidence first; a family channel already strongly linked skips the later stages.
    channel_items(family, live=True)
    channel_items(extra_seeds(ids, family), live=True)
    open_ = unsettled()
    log_event(f"fetch: family stage 1 (channel descriptions): {len(family) - len(open_)} confirmed, "
              f"{len(open_)} open")
    for i, cid in enumerate(open_):
        video_items(uploads(cid, live=True), live=True)
        if i % 50 == 49:
            log_event(f"fetch: family stage 2 (video descriptions): {i + 1} of {len(open_)}")
    open_ = unsettled()
    log_event(f"fetch: family stage 2 done: {len(open_)} still open")
    for cid in open_:
        sections(cid, live=True)
    log_event(f"fetch: family stage 3 (their featured channels) done: {len(unsettled())} featured only")
    log_event(f"fetch: done; {yt.units_used_today()} API units used today (Pacific)")


def unsettled() -> list[str]:
    """Family channels without a strong link yet, most promising first: featured by more dataset
    channels, then more subscribers."""
    chans, _ = load()
    linked = {x for lk in build_links(chans) if lk.strength == "strong" for x in (lk.a, lk.b)}
    by = Counter(f for c in chans.values() if c.origin in IN_DATASET for f, _ in c.featured)
    open_ = [c for c in chans.values() if c.origin in ("family", "seed") and c.id not in linked]
    return [c.id for c in sorted(open_, key=lambda c: (-by[c.id], -c.subscribers, c.id))]


# --- Evidence ------------------------------------------------------------------------------


def norm_holder(name: str) -> str:
    """A copyright holder's name without company suffixes and punctuation; "" when it names nobody."""
    n = re.sub(r"\(c\)|©|®|™|\d{4}", " ", name.lower())
    n = COMPANY_SUFFIX_RE.sub(" ", n)
    n = re.sub(r"[^\w&]+", " ", n).strip()
    n = re.sub(r"\s+", " ", n)
    if len(n) < 3 or len(n) > 50 or JUNK_HOLDER_RE.search(n) or len(n.split()) > 6:
        return ""
    return n


def generic_host(host: str) -> bool:
    """A link host that says nothing about the owner (social, store, shortener), or a subdomain of one."""
    parts = host.split(".")
    return any(".".join(parts[i:]) in OTHER_HOSTS | md.COMMON_HOSTS for i in range(len(parts) - 1))


def text_evidence(text: str) -> dict[str, set[str]]:
    ev = md.owner_evidence(text)
    ev["copyright"] = {h for h in (norm_holder(x) for x in ev["copyright"]) if h}
    ev["domain"] = {d for d in ev["domain"] if not generic_host(d)}
    return ev


def channel_evidence(channel_text: str, video_texts: list[str]) -> dict[str, dict[str, int]]:
    """kind -> value -> support (number of texts it is in; the channel's own text counts 2). A value
    counts only when it is in the channel's text or in at least two of its videos (or its only one):
    a credit in one video's description (a guest, a song licensor) doesn't name the channel's owner."""
    support: dict[str, Counter] = {k: Counter() for k in EVIDENCE_KINDS}
    for k, vals in text_evidence(channel_text).items():
        for v in vals:
            support[k][v] += 2
    for t in video_texts:
        for k, vals in text_evidence(t).items():
            for v in vals:
                support[k][v] += 1
    need = 2 if len(video_texts) >= 2 else 1
    return {k: {v: n for v, n in c.items() if n >= need} for k, c in support.items()}


def primary_holder(ev: dict[str, dict[str, int]], skip: str = "") -> str:
    hs = {h: n for h, n in ev.get("copyright", {}).items() if h != skip}
    return max(sorted(hs), key=lambda h: hs[h]) if hs else ""


def language_of(channel: dict, videos: list[dict]) -> str:
    langs = Counter((v.get("snippet", {}).get("defaultAudioLanguage") or "").split("-")[0].lower()
                    for v in videos)
    langs.pop("", None)
    langs.pop("zxx", None)
    if langs:
        return langs.most_common(1)[0][0]
    sn = channel.get("snippet", {})
    return (sn.get("defaultLanguage") or "").split("-")[0].lower() or "und"


# --- Links and groups ----------------------------------------------------------------------


@dataclass
class Link:
    a: str
    b: str
    kind: str      # copyright, app, email, domain, featured, name
    value: str
    strength: str  # strong, weak, network


@dataclass
class Chan:
    id: str
    title: str
    origin: str                       # reference, collected, both, family
    evidence: dict[str, dict[str, int]]
    featured: list[tuple[str, str]] = field(default_factory=list)
    language: str = "und"
    country: str = ""
    created: str = ""
    videos: int = 0
    subscribers: int = 0
    views: int = 0


def family_section(title: str) -> bool:
    """A featured-channels section that lists the channel's own company (its other channels,
    languages), not friends or recommendations."""
    return bool(FAMILY_SECTION_RE.search(title)) and not NOT_FAMILY_SECTION_RE.search(title)


def norm_name(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def holder_clusters(members: list[str], chans: dict[str, Chan], skip: str = "") -> int:
    """How many unrelated companies the members' copyright holders name: holders named together in
    one channel's descriptions count as one company (a rename, an owner and its acquired studio)."""
    uf = UnionFind({h for c in members for h in chans[c].evidence.get("copyright", {}) if h != skip})
    for c in members:
        hs = sorted(h for h in chans[c].evidence.get("copyright", {}) if h != skip)
        for h in hs[1:]:
            uf.union(hs[0], h)
    return len({uf.find(h) for h in uf.p})


def value_role(kind: str, value: str, members: list[str], chans: dict[str, Chan]) -> str:
    """"owner" when the channels sharing a value look like one company; "network" when they belong
    to unrelated companies (a licensor, distributor or service several companies use)."""
    if kind == "copyright":
        own = sum(primary_holder(chans[c].evidence) == value for c in members)
        if own * 2 >= len(members):  # most of its channels name it first
            return "owner"
    return "network" if holder_clusters(members, chans, skip=value) >= 2 else "owner"


def build_links(chans: dict[str, Chan]) -> list[Link]:
    links: list[Link] = []
    for kind in EVIDENCE_KINDS:
        index: dict[str, list[str]] = defaultdict(list)
        for c in chans.values():
            for v in c.evidence.get(kind, {}):
                index[v].append(c.id)
        for v, members in sorted(index.items()):
            if len(members) < 2:
                continue
            members.sort()
            role = value_role(kind, v, members, chans)
            strength = ("network" if role == "network" else "strong" if kind in STRONG_KINDS else "weak")
            links += [Link(members[0], m, kind, v, strength) for m in members[1:]]
    feat = {c.id: {f: t for f, t in c.featured} for c in chans.values()}
    seen = set()
    for a, fs in feat.items():
        for b, title in fs.items():
            if b not in chans or a == b or (min(a, b), max(a, b)) in seen:
                continue
            seen.add((min(a, b), max(a, b)))
            mutual = a in feat.get(b, {})
            fam = family_section(title) or family_section(feat[b].get(a, ""))
            how = ("mutual" if mutual else "one-way") + (", family section" if fam else "")
            # Only a family section is strong: friends feature each other mutually too.
            links.append(Link(a, b, "featured", how, "strong" if fam else "weak"))
    names = {c.id: norm_name(c.title) for c in chans.values()}
    ids = sorted(names)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            na, nb = names[a], names[b]
            short, long_ = sorted((na, nb), key=len)
            if len(short) >= 6 and re.search(rf"\b{re.escape(short)}\b", long_):
                links.append(Link(a, b, "name", f"'{short}' in '{long_}'", "weak"))
    return links


class UnionFind:
    def __init__(self, items):
        self.p = {x: x for x in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def bridges(nodes: list[str], edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Edges whose removal splits their component (iterative Tarjan)."""
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    disc, low, out, t = {}, {}, set(), 0
    for root in nodes:
        if root in disc:
            continue
        disc[root] = low[root] = t
        t += 1
        stack = [(root, None, iter(adj[root]))]
        while stack:
            v, parent, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                if parent is not None:
                    low[parent] = min(low[parent], low[v])
                    if low[v] > disc[parent]:
                        out.add((min(parent, v), max(parent, v)))
            elif nxt == parent:
                continue
            elif nxt in disc:
                low[v] = min(low[v], disc[nxt])
            else:
                disc[nxt] = low[nxt] = t
                t += 1
                stack.append((nxt, v, iter(adj[nxt])))
    return out


def group(chans: dict[str, Chan], links: list[Link]) -> dict:
    """Groups over strong links; family channels without a strong link stay out (featured only)."""
    uf = UnionFind(chans)
    strong = [lk for lk in links if lk.strength == "strong"]
    for lk in strong:
        uf.union(lk.a, lk.b)
    members: dict[str, list[str]] = defaultdict(list)
    for c in chans:
        members[uf.find(c)].append(c)
    linked = {x for lk in strong for x in (lk.a, lk.b)}
    featured_only = sorted(c for c in chans if chans[c].origin == "family" and c not in linked)
    by_pair: dict[tuple[str, str], list[Link]] = defaultdict(list)
    for lk in strong:
        by_pair[(min(lk.a, lk.b), max(lk.a, lk.b))].append(lk)
    groups = []
    for ms in members.values():
        if len(ms) == 1 and ms[0] in featured_only:
            continue
        ms.sort(key=lambda c: (-chans[c].videos, c))
        mset = set(ms)
        pairs = {p for p in by_pair if p[0] in mset}
        weak_bridges = [p for p in bridges(ms, pairs) if len(by_pair[p]) == 1]
        size = Counter()
        for c in ms:
            size[chans[c].language] += max(1, chans[c].videos)
        size.pop("und", None)
        main = size.most_common(1)[0][0] if size else "und"
        dubs = [c for c in ms if main != "und" and chans[c].language not in ("und", main)]
        flags = []
        if weak_bridges:
            flags.append(f"{len(weak_bridges)} single-evidence link(s) hold it together")
        if len(ms) > 10:
            flags.append(f"large ({len(ms)} channels)")
        groups.append({"channels": ms, "language": main, "dubs": dubs, "flags": flags,
                       "single_links": [list(p) for p in weak_bridges],
                       "videos": sum(chans[c].videos for c in ms),
                       "subscribers": sum(chans[c].subscribers for c in ms),
                       "in_dataset": sum(chans[c].origin in IN_DATASET for c in ms)})
    groups.sort(key=lambda g: (-len(g["channels"]), -g["videos"]))
    for i, g in enumerate(groups, 1):
        g["id"] = f"G{i:03d}"
    return {"groups": groups, "featured_only": featured_only}


# --- Group (offline) -----------------------------------------------------------------------


def load() -> tuple[dict[str, Chan], list[str]]:
    data = dataset_channels()
    family = family_of(sorted(data))
    seeds = extra_seeds(sorted(data), family)
    items = channel_items(sorted(data)) | channel_items(family) | channel_items(seeds)  # as fetch asked
    family = family + seeds
    vids_of = {c: d["videos"] for c, d in data.items()} | {c: uploads(c) for c in family}
    vitems = video_items(sorted({v for c in data.values() for v in c["videos"]}))
    for c in family:
        vitems |= video_items(vids_of[c])
    chans: dict[str, Chan] = {}
    for cid in list(data) + family:
        it = items.get(cid)
        if it is None:
            continue  # deleted or closed
        sn, st = it.get("snippet", {}), it.get("statistics", {})
        vs = [vitems[v] for v in vids_of[cid] if v in vitems]
        sets = data[cid]["sets"] if cid in data else []
        origin = ("seed" if cid in SEEDS and not sets else "family" if not sets
                  else "both" if len(sets) == 2 else sets[0])
        chan_text = "\n".join([sn.get("description", ""),
                               it.get("brandingSettings", {}).get("channel", {}).get("description", "")])
        chans[cid] = Chan(
            id=cid, title=sn.get("title", data.get(cid, {}).get("title", "")), origin=origin,
            evidence=channel_evidence(chan_text, [v["snippet"].get("description", "") for v in vs]),
            featured=featured_of(sections(cid)),
            language=language_of(it, vs), country=sn.get("country", ""),
            created=sn.get("publishedAt", "")[:10],
            videos=int(st.get("videoCount", 0)), subscribers=int(st.get("subscriberCount", 0)),
            views=int(st.get("viewCount", 0)))
    frontier = sorted({f for c in chans.values() if c.origin not in IN_DATASET for f, _ in c.featured}
                      - set(chans) - set(data))
    return chans, frontier


def write_tsv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def run_group() -> dict:
    chans, frontier = load()
    links = build_links(chans)
    res = group(chans, links)
    gid = {c: g["id"] for g in res["groups"] for c in g["channels"]}
    OUT.mkdir(parents=True, exist_ok=True)
    write_tsv(OUT / "channels.tsv",
              ["channel_id", "title", "origin", "group", "dub", "language", "country", "created", "videos",
               "subscribers", "views", "holders", "featured"],
              [[c.id, c.title, c.origin, gid.get(c.id, "featured only"),
                int(any(c.id in g["dubs"] for g in res["groups"])), c.language, c.country, c.created,
                c.videos,
                c.subscribers, c.views, "; ".join(sorted(c.evidence["copyright"])), len(c.featured)]
               for c in sorted(chans.values(), key=lambda c: (gid.get(c.id, "Z"), -c.videos))])
    write_tsv(OUT / "links.tsv", ["a", "b", "group_a", "group_b", "kind", "value", "strength"],
              [[lk.a, lk.b, gid.get(lk.a, ""), gid.get(lk.b, ""), lk.kind, lk.value, lk.strength]
               for lk in links])
    net: dict[tuple[str, str], set[str]] = defaultdict(set)
    for lk in links:
        if lk.strength == "network":
            net[(lk.kind, lk.value)] |= {lk.a, lk.b}
    write_tsv(OUT / "networks.tsv", ["kind", "value", "channels", "groups", "channel_ids"],
              [[k, v, len(cs), len({gid.get(c, c) for c in cs}), ",".join(sorted(cs))]
               for (k, v), cs in sorted(net.items(), key=lambda x: -len(x[1]))])
    write_tsv(OUT / "frontier.tsv", ["channel_id"], [[c] for c in frontier])
    weak = defaultdict(set)  # channel -> other groups it links to only by weak evidence
    for lk in links:
        if lk.strength == "weak" and gid.get(lk.a) and gid.get(lk.b) and gid[lk.a] != gid[lk.b]:
            weak[lk.a].add(gid[lk.b])
            weak[lk.b].add(gid[lk.a])
    summary = {"at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "channels": len(chans),
               "dataset_channels": sum(c.origin in IN_DATASET for c in chans.values()),
               "family_channels": sum(c.origin == "family" for c in chans.values()),
               "featured_only": len(res["featured_only"]), "frontier": len(frontier),
               "groups": len(res["groups"]),
               "groups_2plus": sum(len(g["channels"]) > 1 for g in res["groups"]),
               "networks": len(net), "weak_only_candidates": {c: sorted(gs) for c, gs in weak.items()}}
    (OUT / "groups.json").write_text(json.dumps({**summary, **res}, indent=1, ensure_ascii=False))
    write_tsv(OUT / "groups.tsv",
              ["group", "channels", "in_dataset", "videos", "subscribers", "language", "dubs", "flags",
               "channel_ids"],
              [[g["id"], len(g["channels"]), g["in_dataset"], g["videos"], g["subscribers"], g["language"],
                len(g["dubs"]), "; ".join(g["flags"]), ",".join(g["channels"])] for g in res["groups"]])
    log_event(f"group: {summary['channels']} channels -> {summary['groups']} groups "
              f"({summary['groups_2plus']} with 2+), {summary['networks']} network values, "
              f"{summary['featured_only']} featured only, frontier {summary['frontier']}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fetch", "group"])
    a = ap.parse_args()
    fetch() if a.cmd == "fetch" else run_group()


if __name__ == "__main__":
    main()
