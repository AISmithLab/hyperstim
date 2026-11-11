"""Metadata signals from Data API snippets: owner, timing, title, description and tags, duration.

All text measures go through one normalization, so baseline pairs are scored exactly like the pair.
"""

from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse

NUMBERS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
           "8": "eight", "9": "nine", "10": "ten"}
# Link hosts that say nothing about who owns a channel.
COMMON_HOSTS = {"youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com", "goo.gl", "bit.ly",
                "google.com", "www.google.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
                "tiktok.com", "pinterest.com", "www.facebook.com", "www.instagram.com", "www.tiktok.com"}
URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
COPYRIGHT_RE = re.compile(r"(?:©|\(c\)|copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?)?\s*([^\n|•]{3,80})", re.I)


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [NUMBERS.get(w, w) for w in words]


def song_name(title_a: str, title_b: str) -> list[str]:
    """The longest run of words both titles share (the song, for two versions of one song)."""
    ta, tb = tokens(title_a), tokens(title_b)
    m = SequenceMatcher(None, ta, tb, autojunk=False).find_longest_match(0, len(ta), 0, len(tb))
    return ta[m.a:m.a + m.size] if m.size >= 2 else []


def without(seq: list[str], run: list[str]) -> list[str]:
    if not run:
        return seq
    for i in range(len(seq) - len(run) + 1):
        if seq[i:i + len(run)] == run:
            return seq[:i] + seq[i + len(run):]
    return seq


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else float("nan")


def title_signal(title_a: str, title_b: str) -> dict:
    song = song_name(title_a, title_b)
    ra, rb = without(tokens(title_a), song), without(tokens(title_b), song)
    return {"song": " ".join(song), "rest_a": " ".join(ra), "rest_b": " ".join(rb),
            "jaccard": jaccard(ra, rb),
            "ratio": SequenceMatcher(None, " ".join(ra), " ".join(rb)).ratio(),
            "shared": sorted(set(ra) & set(rb)), "only_a": sorted(set(ra) - set(rb)),
            "only_b": sorted(set(rb) - set(ra))}


def norm_tag(t: str) -> str:
    return " ".join(tokens(t))


def text_signal(desc_a: str, desc_b: str, tags_a: list[str], tags_b: list[str]) -> dict:
    lines = lambda d: {ln.strip().lower() for ln in d.splitlines() if len(ln.strip()) > 3}  # noqa: E731
    la, lb = lines(desc_a), lines(desc_b)
    na, nb = {norm_tag(t) for t in tags_a}, {norm_tag(t) for t in tags_b}
    wa, wb = tokens(URL_RE.sub(" ", desc_a)), tokens(URL_RE.sub(" ", desc_b))
    return {
        "description_words": jaccard(wa, wb),
        "description_lines": jaccard(la, lb),
        "shared_lines": sorted(la & lb, key=lambda s: (desc_a.lower().find(s))),
        "tags": jaccard(na, nb) if na or nb else float("nan"),
        "shared_tags": sorted(na & nb), "only_a_tags": sorted(na - nb), "only_b_tags": sorted(nb - na),
        "n_tags": [len(na), len(nb)],
    }


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def timing_signal(pub_a: str, pub_b: str) -> dict:
    a, b = parse_time(pub_a), parse_time(pub_b)
    days = abs((b - a).total_seconds()) / 86400
    ha = a.hour + a.minute / 60 + a.second / 3600
    hb = b.hour + b.minute / 60 + b.second / 3600
    tod = abs(ha - hb)
    return {"days": days, "time_of_day_h": min(tod, 24 - tod), "first": "a" if a <= b else "b"}


def duration_signal(dur_a: float, dur_b: float) -> dict:
    return {"diff_s": abs(dur_a - dur_b), "ratio": min(dur_a, dur_b) / max(dur_a, dur_b)}


def iso_duration(s: str) -> float:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s)
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


# --- Owner ------------------------------------------------------------------------------


def owner_evidence(text: str) -> dict[str, set[str]]:
    """Patterns that name an owner in free text: copyright holders, link domains, app IDs, emails."""
    out: dict[str, set[str]] = {"copyright": set(), "domain": set(), "app": set(), "email": set()}
    for m in COPYRIGHT_RE.finditer(text):
        name = re.sub(r"[™®]|all rights reserved.*", "", m.group(1), flags=re.I).strip(" .,:-")
        name = re.sub(r"\s+", " ", name).lower()
        if len(name) >= 3 and not name.startswith("http"):
            out["copyright"].add(name)
    for url in URL_RE.findall(text):
        u = urlparse(url.rstrip(".,"))
        host = (u.hostname or "").lower()
        if host in ("play.google.com",):
            app = parse_qs(u.query).get("id", [""])[0]
            if app:
                out["app"].add(f"android:{app}")
        elif host == "apps.apple.com":
            m = re.search(r"id(\d+)", u.path)
            if m:
                out["app"].add(f"ios:{m.group(1)}")
        elif host and host not in COMMON_HOSTS:
            out["domain"].add(host.removeprefix("www."))
    out["email"] = {e.lower() for e in EMAIL_RE.findall(text)}
    return out


def owner_signal(texts_a: list[str], texts_b: list[str], featured_a: set[str], featured_b: set[str],
                 channel_a: str, channel_b: str) -> dict:
    """Shared owner evidence between two videos (their descriptions and their channels')."""
    ea = owner_evidence("\n".join(texts_a))
    eb = owner_evidence("\n".join(texts_b))
    shared = {k: sorted(ea[k] & eb[k]) for k in ea}
    featured = {"a_lists_b": channel_b in featured_a, "b_lists_a": channel_a in featured_b,
                "n_a": len(featured_a), "n_b": len(featured_b)}
    same_channel = channel_a == channel_b
    strongest = ("same channel" if same_channel else
                 "featured channels" if featured["a_lists_b"] or featured["b_lists_a"] else
                 "copyright line" if shared["copyright"] else
                 "app link" if shared["app"] else
                 "email" if shared["email"] else
                 "domain" if shared["domain"] else None)
    return {"same_owner": strongest is not None, "strongest": strongest, "shared": shared,
            "featured": featured, "evidence_a": {k: sorted(v) for k, v in ea.items()},
            "evidence_b": {k: sorted(v) for k, v in eb.items()}}
