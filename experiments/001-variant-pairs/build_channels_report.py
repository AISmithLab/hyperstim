"""The channel groups page (PLAN.md, Search: other channels, Step 1): results/channels/ -> one HTML page.

Run (from experiments/): uv run python 001-variant-pairs/build_channels_report.py
Writes cache/channels/report.html (a private artifact page).
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results" / "channels"
OUT = HERE.parent / "cache" / "channels" / "report.html"
SEEDS = {"UC7Pq3Ko42YpkCB_Q4E981jw": "Kids TV", "UCv7TYWhF5jhtuY3FDPf06Aw": "Kids Channel"}


def rows(name: str) -> list[dict]:
    with (RES / name).open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def fetch_status() -> list[str]:
    """The fetch's latest stage lines from events.log."""
    lines = [ln.strip() for ln in (RES / "events.log").read_text().splitlines() if " fetch: " in ln]
    keep, seen = [], set()
    for ln in reversed(lines):
        key = re.sub(r"\d+ of \d+|\d+", "#", ln.split(" fetch: ", 1)[1])[:40]
        if key not in seen:
            seen.add(key)
            keep.append(ln)
    return list(reversed(keep))[-6:]


def link_summary(links: list[dict]) -> dict[str, list]:
    """Per group: evidence counted by kind and value (strong links inside the group)."""
    out: dict[str, Counter] = defaultdict(Counter)
    for lk in links:
        if lk["strength"] == "strong" and lk["group_a"] == lk["group_b"]:
            out[lk["group_a"]][(lk["kind"], lk["value"])] += 1
    return {g: [[k, v, n] for (k, v), n in c.most_common(12)] for g, c in out.items()}


def data() -> dict:
    summary = json.loads((RES / "groups.json").read_text())
    chans = rows("channels.tsv")
    links = rows("links.tsv")
    by_group: dict[str, list] = defaultdict(list)
    for c in chans:
        by_group[c["group"]].append([c["channel_id"], c["title"], c["origin"], c["language"], int(c["dub"]),
                                     int(c["videos"] or 0), int(c["subscribers"] or 0), c["holders"]])
    weak = summary.get("weak_only_candidates", {})
    groups = []
    ev = link_summary(links)
    for g in summary["groups"]:
        groups.append({"id": g["id"], "n": len(g["channels"]), "in": g["in_dataset"], "videos": g["videos"],
                       "subs": g["subscribers"], "lang": g["language"], "dubs": len(g["dubs"]),
                       "flags": g["flags"], "channels": by_group[g["id"]], "evidence": ev.get(g["id"], []),
                       "weak": sorted({x for c in g["channels"] for x in weak.get(c, [])})})
    seed_groups = {SEEDS[c["channel_id"]]: c["group"] for c in chans if c["channel_id"] in SEEDS}
    nets = [[r["kind"], r["value"], int(r["channels"]), int(r["groups"])] for r in rows("networks.tsv")]
    return {"summary": {k: v for k, v in summary.items() if k not in ("groups", "featured_only",
                                                                       "weak_only_candidates")},
            "groups": groups, "networks": nets, "seeds": seed_groups, "status": fetch_status(),
            "origins": Counter(c["origin"] for c in chans)}


TEMPLATE = HERE / "channels_report.html"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(TEMPLATE.read_text().replace("__DATA__", payload))
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
