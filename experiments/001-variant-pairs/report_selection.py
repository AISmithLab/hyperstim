"""Groups, and which re-skin pairs get a full report (PLAN.md, Search, filter 7).

    uv run python 001-variant-pairs/report_selection.py

A group is a connected set of videos linked by confident labels (confidence ≥ 0.7) of one kind.
Re-skin and re-upload links count only once overlap.py has found that the pair's main content
overlaps: the shared part covers at least half of each video. Pairs under half of the shorter are
kept apart as "little shared"; pairs where it covers the shorter but under half of the longer as
"contained" (one video holds the other among more: a compilation, a short cut from it); pairs not
aligned yet as "waiting". For a re-skin group of n versions, n - 1 reports cover every
change from the original: each version against the group's earliest version where that pair was
labelled, else the path the labels give (a spanning tree, breadth first from the earliest).
Writes results/search/groups.json ({label: {"groups": [...], "little_shared": [...],
"contained": [...], "waiting": [...]}}) and results/search/report_selection.json
([{"a", "b", "type", "family"}]).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from overlap import LABELS as OVERLAP_LABELS  # noqa: E402
from overlap import MIN_SHARE, connect  # noqa: E402
from search import OUT  # noqa: E402

MIN_CONFIDENCE = 0.7
LABELS = ("re-skin", "re-upload", "same-song", "same-template", "shared-segments")  # unrelated: counted only


def families(edges: list[tuple[str, str]]) -> list[set[str]]:
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, out = set(), []
    for v in adj:
        if v in seen:
            continue
        comp, todo = set(), [v]
        while todo:
            x = todo.pop()
            if x not in comp:
                comp.add(x)
                todo.extend(adj[x] - comp)
        seen |= comp
        out.append(comp)
    return out


def spanning_pairs(fam: set[str], edges: set[frozenset], published: dict[str, str]) -> list[tuple[str, str]]:
    """Breadth first from the earliest version, preferring a direct link to it."""
    root = min(fam, key=lambda v: (published[v], v))
    adj = defaultdict(set)
    for e in edges:
        a, b = tuple(e)
        if a in fam:
            adj[a].add(b)
            adj[b].add(a)
    out, seen, todo = [], {root}, deque([root])
    for v in sorted(adj[root], key=lambda v: published[v]):  # direct links to the original first
        seen.add(v)
        out.append((root, v))
        todo.append(v)
    todo.popleft()
    while todo:
        x = todo.popleft()
        for v in sorted(adj[x] - seen, key=lambda v: published[v]):
            seen.add(v)
            out.append((x, v))
            todo.append(v)
    return out


def long_share(o: dict) -> float | None:
    """The shared part as a share of the longer video (overlap's share is of the shorter)."""
    da, db = o.get("dur_a"), o.get("dur_b")
    if not da or not db:
        return None
    return o["share"] * min(da, db) / max(da, db)


def split(rows: list[dict], overlaps: dict[tuple[str, str], dict],
          label: str) -> tuple[list, list, list, list]:
    """(linked, little_shared, contained, waiting) pairs: only re-skin and re-upload links need the
    overlap, of each video."""
    if label not in OVERLAP_LABELS:
        return rows, [], [], []
    linked, little, contained, waiting = [], [], [], []
    for r in rows:
        o = overlaps.get((r["a"], r["b"]))
        if o is None:
            waiting.append(r)
            continue
        r.update(o)
        r["long_share"] = long_share(o)
        if o["share"] < MIN_SHARE:
            little.append(r)
        elif r["long_share"] is not None and r["long_share"] < MIN_SHARE:
            contained.append(r)
        else:
            linked.append(r)
    return linked, little, contained, waiting


def build(con: sqlite3.Connection) -> tuple[dict, list[dict]]:
    published = dict(con.execute("SELECT id, published FROM videos"))
    overlaps = {(a, b): {"share": s, "source": src, "audio_share": au, "frame_share": fr,
                         "dur_a": da, "dur_b": db}
                for a, b, s, src, au, fr, da, db in con.execute(
                    "SELECT a, b, share, source, audio_share, frame_share, dur_a, dur_b FROM overlap")}
    groups, sel = {}, []
    for label in LABELS:
        rows = [{"a": a, "b": b, "type": t, "confidence": c, "score": s} for a, b, t, c, s in con.execute(
            "SELECT a, b, type, confidence, score FROM pairs WHERE label = ? AND confidence >= ?",
            (label, MIN_CONFIDENCE))]
        linked, little, contained, waiting = split(rows, overlaps, label)
        fams = sorted(families([(r["a"], r["b"]) for r in linked]), key=lambda f: (-len(f), min(f)))
        out = []
        for fam in fams:
            out.append({"videos": sorted(fam, key=lambda v: (published[v], v)),
                        "pairs": [r for r in linked if r["a"] in fam]})
        if label == "re-skin":
            oriented = {frozenset((r["a"], r["b"])): r for r in linked}
            for k, fam in enumerate(fams):
                for x, y in spanning_pairs(fam, set(oriented), published):
                    r = oriented[frozenset((x, y))]
                    sel.append({"a": r["a"], "b": r["b"], "type": r["type"], "family": k})
        # A pair whose two videos ended up in one group anyway (through other links) isn't listed apart.
        same = {v: k for k, fam in enumerate(fams) for v in fam}
        apart = [r for r in little if same.get(r["a"], -1) != same.get(r["b"], -2)]
        groups[label] = {"groups": out, "little_shared": apart, "contained": contained, "waiting": waiting}
    return groups, sel


def main() -> None:
    groups, sel = build(connect())
    (OUT / "groups.json").write_text(json.dumps(groups, indent=1))
    (OUT / "report_selection.json").write_text(json.dumps(sel, indent=1))
    for label, g in groups.items():
        print(f"{label}: {len(g['groups'])} groups of {sum(len(x['videos']) for x in g['groups'])} videos; "
              f"{len(g['little_shared'])} little shared, {len(g.get('contained', []))} contained, "
              f"{len(g['waiting'])} waiting")
    print(f"{len(sel)} re-skin reports selected")


if __name__ == "__main__":
    main()
