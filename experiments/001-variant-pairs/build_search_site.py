"""Build the search deliverable (PLAN.md, Search, Deliverables, "More than 5"): a base page with the
overall results, and one page per label that lists its groups.

    uv run python 001-variant-pairs/build_search_site.py [--skip-base] [--only LABEL ...]

Writes one folder per page under cache/search/site/, each published as its own private artifact
(they hold YouTube's images):
- base/index.html: build_search_report.py's page (facts, filter chain, channel story, profiles).
- <label>/ for re-skin, re-upload, same-song, same-template, shared-segments: index.html (template
  search_groups.html) with the label's groups from results/search/groups.json, biggest first; each
  group's versions together as strips (thumbnail and auto-frames at 1/4, 1/2, 3/4, packed 25 to a
  sheet in strips/), then its pairs. Re-skin and re-upload pages end with the pairs that looked
  alike but share under half of the shorter video, and a count of pairs not aligned yet.
- re-skin/ also holds the groups' full reports: pairs/<name>/ (the report shell, data.json and the
  stills), each opened inside its group, and loaded, only when asked for. videos.json maps each
  report to its two videos in the artifact's asset store (cache/viewer/assets.json, video ID ->
  URL), so re-skin/ goes to the artifact that holds those assets; a report without both shows its
  stills instead.
- links.json: each page's published URL, filled in by hand after publishing; pages link to each
  other through it (rebuild after filling it in).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import html
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import build_report  # noqa: E402
import build_search_report as base  # noqa: E402
import search_story as story  # noqa: E402

SITE = base.SITE
REPORTS = ROOT / "cache" / "report"
ASSETS = ROOT / "cache" / "viewer" / "assets.json"
DB = ROOT / "cache" / "search.db"
OUT = HERE / "results" / "search"
LOG = OUT / "reports.tsv"
TYPES = ("AxB", "AxA", "BxB")
TYPE_SHORT = {"AxB": "A × B", "AxA": "A × A", "BxB": "B × B"}
SIDE = {"A": "Kids TV", "B": "Kids Channel"}
TOKEN_RE = re.compile(r"[A-Za-z0-9._~-]+")
QUALITY = 65
SCALE = 2 / 3     # stills at 256 × 144 a tile (from 384 × 216)
BUDGET = 256e6    # bytes an artifact version can hold
MAX_FILES = 511   # files an artifact version can hold
NOTE_MAX = 500    # characters in a group's note
SHOWN = 12        # versions shown before "show all"; pairs tables longer than this start closed
# Visual intensity and brightness, as the site shows them: the percentile of a video's mean color
# saturation, and of its mean lightness (L*), among the reference set.
LEVELS = (("mean_saturation", "Visual intensity", "saturation"),
          ("mean_lstar", "Visual brightness", "lightness"))
BACKEND_DATA = ROOT.parent / "backend" / "data"
REFERENCE = BACKEND_DATA / "videos.tsv"                        # the site's percentile pool
DATASET = [REFERENCE, *sorted((BACKEND_DATA / "collected").glob("*.tsv"))]
FEATURES = ROOT / "cache" / "features"


def esc(x) -> str:
    return html.escape(str(x))


def ok_reports(log: Path) -> list[str]:
    """Report names whose latest state in reports.tsv is ok, in first-seen order."""
    if not log.exists():
        return []
    state: dict[str, str] = {}
    for ln in log.read_text().splitlines()[1:]:
        f = ln.split("\t")
        if len(f) >= 3:
            state[f[1]] = f[2]
    return [n for n, s in state.items() if s == "ok"]


def token(name: str) -> str:
    """A report name when it fits a URL fragment, else its safe characters."""
    if TOKEN_RE.fullmatch(name):
        return name
    return "".join(c if TOKEN_RE.fullmatch(c) else "~" for c in name)


def short_title(data: dict, n: int = 26) -> str:
    """The song both titles share, else the start of A's title."""
    title = data.get("signals", {}).get("metadata", {}).get("title", {})
    song = (title.get("detail") or {}).get("song") or ""
    if song:
        text = song.title()
    else:
        a = data["videos"][data["pair"]["a"]]["title"]
        text = re.split(r"\s[|\-–]\s|\|", a)[0].strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def pair_type(name: str, data: dict) -> str:
    t = name.split("-", 1)[0]
    if t in TYPES:
        return t
    va, vb = (data["videos"][data["pair"][k]] for k in ("a", "b"))
    return "AxA" if va["channel_id"] == vb["channel_id"] else "AxB"


def name_of(p: dict) -> str:
    return f"{p['type']}-{p['a']}-{p['b']}"


def asset_videos(names: list[str], assets: dict[str, str]) -> dict:
    """videos.json: each report's two videos from the asset store; null when one isn't uploaded."""
    out = {}
    for n in names:
        a, b = n[4:15], n[16:]
        out[n] = {"a": assets[a], "b": assets[b]} if a in assets and b in assets else {"a": None, "b": None}
    return out


def group_reports(groups: list[dict], selection: list[dict], ok: set[str]) -> list[list[str]]:
    """For each group, its selected re-skin reports that are built, in selection order."""
    out = []
    for g in groups:
        vids = set(g["videos"])
        out.append([name_of(p) for p in selection if p["a"] in vids and p["b"] in vids and name_of(p) in ok])
    return out


def read_saturation(path: Path, col: str = "mean_saturation") -> dict[str, float]:
    """video_id -> one feature (mean_saturation unless `col` says otherwise) from a pipeline or
    dataset TSV; blanks left out."""
    out = {}
    with path.open(newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            v = (r.get(col) or "").strip()
            if v and r.get("video_id"):
                out[r["video_id"]] = float(v)
    return out


def saturation_sources(features: Path = FEATURES, dataset: list[Path] | None = None) -> list[Path]:
    """Where a video's features come from, first found wins: the dataset, then the clips the full
    reports measured (cache/features/pairs/*/features.tsv), then cache/features/videos/."""
    pairs = sorted(features.glob("pairs/*/features.tsv"))
    every = [*(DATASET if dataset is None else dataset), *pairs, features / "videos" / "features.tsv"]
    return [p for p in every if p.exists()]


def saturation_by_video(sources: list[Path], col: str = "mean_saturation") -> dict[str, float]:
    out: dict[str, float] = {}
    for path in sources:
        for v, x in read_saturation(path, col).items():
            out.setdefault(v, x)
    return out


def percentile_rank(value: float, pool: list[float]) -> float | None:
    """As the site's (backend scoring.percentile_rank): share of the sorted pool at or below
    `value`, scaled so the pool's minimum is 0 and its maximum 100."""
    n = len(pool)
    if n == 0:
        return None
    if n == 1:
        return 50.0
    return max(0.0, min(100.0, 100 * (bisect.bisect_right(pool, value) - 1) / (n - 1)))


def intensity(v: str, sat: dict[str, float], pool: list[float]) -> float | None:
    return percentile_rank(sat[v], pool) if v in sat else None


def intensity_cell(v: str, sat: dict[str, float], pool: list[float], raw: str = "saturation") -> str:
    """The percentile in bold, then the raw value it comes from (`raw` names it)."""
    if v not in sat:
        return "<span class='muted'>not measured</span>"
    score = percentile_rank(sat[v], pool)
    return (f"<b>{score:.0f}</b> <span class='muted raw'>{raw} {sat[v]:.0f}</span>"
            if score is not None else f"<span class='muted raw'>{raw} {sat[v]:.0f}</span>")


def no_levels() -> dict[str, tuple]:
    return {key: ({}, []) for key, _, _ in LEVELS}


def pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def like_rate(views, likes) -> float | None:
    return likes / views if views and likes is not None else None


def rate_text(r: float | None) -> str:
    return "–" if r is None else f"{100 * r:.2f}%"


def sort_key(x) -> str:
    """A cell's data-v: blank (sorted last) when unknown."""
    return "" if x is None else esc(x)


def version_rows(videos: list[str], num: dict[str, int], vids: dict, strips: base.Strips,
                 inten: dict) -> list[str]:
    """One table row per video: its strip, then title, channel, date, views, likes, like rate, visual
    intensity and visual brightness (`inten`: LEVELS key -> (values, reference pool)). Each cell's
    data-v is what the column sorts by."""
    rows = []
    for v in videos:
        r = vids.get(v) or {"side": "?", "title": v, "published": "", "views": None, "likes": None}
        side = r["side"].lower() if r["side"] in ("A", "B") else "a"
        views = base.fmt(r["views"]) if r.get("views") is not None else "–"
        likes = base.fmt(r["likes"]) if r.get("likes") is not None else "–"
        rate = like_rate(r.get("views"), r.get("likes"))
        levels = "".join(
            f"<td data-label='{name}' class='num' data-v='{sort_key(intensity(v, *inten[key]))}'>"
            f"<span>{intensity_cell(v, *inten[key], raw)}</span></td>" for key, name, raw in LEVELS)
        rows.append(
            f"<tr data-n='{num[v]}'><td class='img' data-v='{num[v]}'><div class='vstrip' role='img' "
            f"aria-label='#{num[v]}: thumbnail and frames at 1/4, 1/2, 3/4' "
            f"style='{strips.css(v)}'></div></td>"
            f"<th scope='row' class='ttl' data-v='{esc(r['title'].lower())}'>"
            f"<span class='num'>#{num[v]}</span>"
            f"<a href='https://www.youtube.com/watch?v={esc(v)}'>{esc(r['title'])}</a></th>"
            f"<td data-label='Channel' class='chan' data-v='{esc(r['side'])}'><span>"
            f"<span class='tag {side}'>{esc(r['side'])}</span>{esc(SIDE.get(r['side'], ''))}</span></td>"
            f"<td data-label='Published' class='date' data-v='{esc(r['published'] or '')}'>"
            f"<span>{esc((r['published'] or '')[:10])}</span></td>"
            f"<td data-label='Views' class='num' data-v='{sort_key(r.get('views'))}'>"
            f"<span>{views}</span></td>"
            f"<td data-label='Likes' class='num' data-v='{sort_key(r.get('likes'))}'>"
            f"<span>{likes}</span></td>"
            f"<td data-label='Like rate' class='num' data-v='{sort_key(rate)}'>"
            f"<span>{rate_text(rate)}</span></td>"
            f"{levels}</tr>")
    return rows


# Every column sorts (sort.js in search_groups.html): text columns A to Z first, numbers high to low.
COLUMNS = [("Thumbnail and frames", "num", "img", True), ("Title", "text", "", False),
           ("Channel", "text", "", False), ("Published", "text", "", False), ("Views", "num", "num", False),
           ("Likes", "num", "num", False), ("Like rate", "num", "num", False),
           *((name, "num", "num", False) for _, name, _ in LEVELS)]


def sort_head() -> str:
    cells = []
    for i, (name, kind, cls, hidden) in enumerate(COLUMNS):
        text = f"<span class='sr'>{name}, by publish order</span>#" if hidden else name
        cells.append(f"<th scope='col' class='{cls}' aria-sort='none'><button type='button' class='sort' "
                     f"data-col='{i}' data-kind='{kind}'>{text}<span class='arrow' aria-hidden='true'>"
                     "↕</span></button></th>")
    return f"<thead><tr>{''.join(cells)}</tr></thead>"


def versions_table(rows: list[str], caption: str) -> str:
    """All rows in one table; past SHOWN they stay hidden until "Show all" (sorting keeps that)."""
    more = ""
    if len(rows) > SHOWN:
        more = (f"<button type='button' class='more' aria-expanded='false'>Show all {len(rows)} versions"
                "</button>")
    return (f"<div class='vscroll'><table class='vtable sortable' data-shown='{SHOWN}'>"
            f"<caption class='sr'>{esc(caption)}</caption>{sort_head()}<tbody>{''.join(rows)}</tbody>"
            f"</table></div>{more}")


def pairs_table(pairs: list[dict], num: dict[str, int], label: str, notes: dict) -> str:
    overlap = label in base.OVERLAP_LABELS
    head = ("<th scope='col'>Versions</th><th scope='col'>Pair type</th>"
            "<th scope='col' class='num'>Confidence</th>"
            + ("<th scope='col' class='num'>Overlap</th><th scope='col'>Aligned by</th>" if overlap else "")
            + "<th scope='col'>Agent's note</th>")
    rows = []
    for p in sorted(pairs, key=lambda p: (num[p["a"]], num[p["b"]])):
        i, j = sorted((num[p["a"]], num[p["b"]]))
        cells = (f"<th scope='row'>#{i} ↔ #{j}</th><td>{TYPE_SHORT.get(p['type'], p['type'])}</td>"
                 f"<td class='num'>{p['confidence']:.0%}</td>")
        if overlap:
            cells += f"<td class='num'>{pct(p.get('share'))}</td><td>{esc(p.get('source', ''))}</td>"
        cells += f"<td class='notes'>{esc(notes.get((p['a'], p['b']), ''))}</td>"
        rows.append(f"<tr>{cells}</tr>")
    table = (f"<div class='scroll'><table class='data'><thead><tr>{head}</tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table></div>")
    word = "pair" if len(pairs) == 1 else "pairs"
    return (f"<details class='pairs'{' open' if len(pairs) <= SHOWN else ''}><summary>{len(pairs)} {word} "
            f"linking them</summary>{table}</details>")


def report_button(src: str, ident: str, title: str, text: str, sub: str) -> str:
    """Opens a report in the side panel (search_groups.html); #<ident> in the URL opens it too."""
    return (f"<li><button type='button' class='rep' data-src='{esc(src)}' data-id='{esc(ident)}' "
            f"data-title='{esc(title)}'>{text} <span class='muted'>{sub}</span></button></li>")


def group_section(k: int, g: dict, label: str, vids: dict, strips: base.Strips, notes: dict,
                  reports: list[str], titles: dict[str, str], inten: dict) -> str:
    num = {v: i for i, v in enumerate(g["videos"], 1)}
    name = story.family_name([vids.get(v, {}).get("title", "") for v in g["videos"]])
    sides = "".join(sorted({vids.get(v, {}).get("side", "?") for v in g["videos"]}))
    where = {"A": "Kids TV only", "B": "Kids Channel only", "AB": "both channels"}.get(sides, sides)
    vers = versions_table(version_rows(g["videos"], num, vids, strips, inten),
                          f"{k}. {name}: its versions, by publish date")
    reps = ""
    if reports:
        items = [report_button(f"group.html#g={k}", f"group-{k}", f"{k}. {name}: all versions",
                               f"All {len(g['videos'])} versions together",
                               "played in sync, with their measures side by side")]
        for n in reports:
            a, b = n[4:15], n[16:]
            items.append(report_button(f"pairs/{n}/index.html", token(n),
                                       f"{k}. {name}: #{num[a]} → #{num[b]}",
                                       f"#{num[a]} → #{num[b]}",
                                       f"{esc(titles.get(n, ''))}, {TYPE_SHORT.get(n[:3], n[:3])}"))
        reps = (f"<div class='reps'><h3>Reports</h3><p class='muted'>Pair reports: each version against the "
                f"group's earliest where the agent linked them, else along the links: {len(reports)} of "
                f"{len(g['videos']) - 1}.</p><ul class='replist'>{''.join(items)}</ul></div>")
    key = g["videos"][0]   # the earliest version: what a star is saved under
    return (f"<section class='group' id='g{k}' data-key='{esc(key)}' aria-labelledby='g{k}h'>"
            f"<div class='sec-head'><div class='ghead'><h2 id='g{k}h'><span class='gnum'>{k}.</span> "
            f"{esc(name)}</h2><button type='button' class='star' aria-pressed='false' "
            f"aria-label='Star group {k}, {esc(name)}' hidden>☆</button></div>"
            f"<p>{len(g['videos'])} versions · {where}</p>{note_box(k, name)}</div>{vers}"
            f"{pairs_table(g['pairs'], num, label, notes)}{reps}</section>")


def note_box(k: int, name: str) -> str:
    """A group's short note: shown under its head, edited in place (the page script saves it like the
    stars); hidden until the script runs."""
    return (f"<div class='gnote' hidden><p class='note-text' hidden></p>"
            f"<button type='button' class='note-edit' aria-expanded='false' aria-controls='g{k}n'>"
            f"Add note</button><form class='note-form' id='g{k}n' hidden>"
            f"<label for='g{k}nt'>Note on group {k}, {esc(name)}</label>"
            f"<textarea id='g{k}nt' rows='3' maxlength='{NOTE_MAX}'></textarea>"
            f"<div class='note-actions'><button type='submit'>Save</button>"
            f"<button type='button' class='note-cancel'>Cancel</button>"
            f"<span class='muted note-status' role='status'></span></div></form></div>")


def pair_items(pairs: list[dict], vids: dict, strips: base.Strips, inten: dict, longer: bool = False) -> str:
    items = []
    for p in pairs:
        share = (f"{pct(p.get('share'))} of the shorter, {pct(p.get('long_share'))} of the longer" if longer
                 else f"{pct(p.get('share'))} shared")
        items.append(f"<div class='lpair'><p class='meta'><span class='pill'>{share}"
                     f"{', by ' + esc(p['source']) if p.get('source') else ''}</span>"
                     f"<span>{TYPE_SHORT.get(p['type'], p['type'])}</span>"
                     f"<span>agent {p['confidence']:.0%}</span></p>"
                     + versions_table(version_rows([p["a"], p["b"]], {p["a"]: 1, p["b"]: 2}, vids, strips,
                                                   inten), "The pair's two videos") + "</div>")
    return "".join(items)


def overview_section(groups: list[dict], vids: dict, eligible: dict, reports: list[list[str]],
                     notes: dict) -> str:
    """Before the re-skin groups: the channel story's timeline (every link opens its pair's full
    report, else jumps to its group) and the families table, one row per group linking to it."""
    built = {n for g in reports for n in g}
    where: dict[tuple[str, str], int] = {}
    pairs = []
    for k, g in enumerate(groups, 1):
        for q in g["pairs"]:
            where[(q["a"], q["b"])] = k
            pairs.append(q)

    def href(q: dict) -> str:
        n = name_of(q)
        return f"#{token(n)}" if n in built else f"#g{where[(q['a'], q['b'])]}"

    tl_vids = {**eligible, **{v: vids[v] for q in pairs for v in (q["a"], q["b"]) if v in vids}}
    years = [int(r["published"][:4]) for r in tl_vids.values() if r.get("published")]
    by_type = Counter(q["type"] for q in pairs)
    legend = "".join(f"<span><i style='background:{story.TYPE_VAR[t]}'></i>{story.TYPE_NAME[t]} "
                     f"({TYPE_SHORT[t]}): {by_type[t]}</span>" for t in TYPES)
    timeline = (f"<div class='legend-row'>{legend}<span><i class='tickkey'></i>Upload (all "
                f"{base.fmt(len(eligible))} eligible videos)</span></div>"
                "<div class='viz-scroll' tabindex='0' role='region' aria-label='Timeline, scrolls sideways'>"
                f"{story.timeline_svg(tl_vids, pairs, min(years), max(years), href)}</div>"
                "<p class='muted'>Each link is a re-skin pair: click it for the pair's full report, or its "
                "group when it has none. Links above the Kids TV row join two Kids TV videos; below the Kids "
                "Channel row, two Kids Channel videos.</p>")
    rows = []
    for k, g in enumerate(groups, 1):
        members = g["videos"]
        r = [vids.get(v, {}) for v in members]
        views = [x.get("views") or 0 for x in r]
        top = max(members, key=lambda v: vids.get(v, {}).get("views") or 0)
        side = Counter(x.get("side") for x in r)
        ns = list(dict.fromkeys(notes[(q["a"], q["b"])] for q in g["pairs"] if notes.get((q["a"], q["b"]))))
        name = story.family_name([x.get("title", "") for x in r])
        more = f" <span class='muted'>(+{len(ns) - 3} more)</span>" if len(ns) > 3 else ""
        rows.append(
            f"<tr><th scope='row'><a href='#g{k}'>{k}. {esc(name)}</a></th>"
            f"<td class='num'>{len(members)}</td><td class='num'>{side['A']} / {side['B']}</td>"
            f"<td>{esc((r[0].get('published') or '')[:10])} – {esc((r[-1].get('published') or '')[:10])}</td>"
            f"<td class='num'>{story.views_span(views)}</td><td>{'yes' if top == members[0] else 'no'}</td>"
            f"<td class='notes'>{'<br>'.join(esc(n) for n in ns[:3])}{more}</td></tr>")
    def most_viewed(g: dict) -> str:
        return max(g["videos"], key=lambda v: vids.get(v, {}).get("views") or 0)

    earliest_top = sum(1 for g in groups if most_viewed(g) == g["videos"][0])
    families = (f"<p>One row per group below: {len(groups)} families. In {earliest_top} of them the "
                "most-viewed version is also the earliest. Click a family to go to its group.</p>"
                f"{story.fam_table(rows)}")
    return (f"<section class='group overview' aria-labelledby='story-h'><div class='sec-head'>"
            "<h2 id='story-h'>Channel story</h2><p>Uploads of both channels over time, and every re-skin "
            f"pair that links the groups below.</p></div>{timeline}</section>"
            f"<section class='group overview' aria-labelledby='fam-h'><div class='sec-head'>"
            f"<h2 id='fam-h'>Families</h2></div>{families}</section>")


def little_section(little: list[dict], waiting: int, vids: dict, strips: base.Strips, inten: dict,
                   contained: list[dict] | None = None) -> str:
    contained = contained or []
    if not little and not waiting and not contained:
        return ""
    verb = "pair waits" if waiting == 1 else "pairs wait"
    wait = f"<p>{waiting} more {verb} for their downloads and alignment.</p>" if waiting else ""
    out = ""
    if little or wait:
        out += (f"<section class='group little'><div class='sec-head'><h2>Looked alike, little shared</h2>"
                "<p>The agent linked these from their images, but aligned they share under half of the "
                "shorter "
                f"video (often just an intro), so they aren't in any group.</p>{wait}</div>"
                f"{pair_items(sorted(little, key=lambda p: -(p.get('share') or 0)), vids, strips, inten)}"
                "</section>")
    if contained:
        out += (f"<section class='group little'><div class='sec-head'><h2>One inside a longer video</h2>"
                "<p>The shorter video is all there, but it's under half of the longer one: a compilation, a "
                "short cut from a longer video, or a longer version with more added. "
                "They aren't in any group."
                f"</p></div><details class='pairs'><summary>{len(contained)} pairs</summary>"
                f"{pair_items(sorted(contained, key=lambda p: p.get('long_share') or 0), vids, strips, inten,
                              True)}"
                "</details></section>")
    return out


MEASURES = ("duration_s", "cuts_per_min", "lstar_flash_per_min", "palette_change_per_min", "motion_frac",
            "mean_saturation", "mean_lstar", "lufs")


def features_by_video(sources: list[Path]) -> dict[str, dict[str, float]]:
    """video_id -> the MEASURES it has, first source wins (as saturation_by_video)."""
    out: dict[str, dict[str, float]] = {}
    for path in sources:
        with path.open(newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                v = r.get("video_id")
                if not v or v in out:
                    continue
                out[v] = {m: float(r[m]) for m in MEASURES if (r.get(m) or "").strip()}
    return out


def offsets(root: str, edges: list[tuple[str, str, float]]) -> dict[str, float]:
    """Seconds to add to the root's time to reach the same moment in each video, along the links
    (each (a, b, lag) says B time = A time + lag); the first link that reaches a video wins."""
    adj: dict[str, list[tuple[str, float]]] = {}
    for a, b, lag in edges:
        adj.setdefault(a, []).append((b, lag))
        adj.setdefault(b, []).append((a, -lag))
    out, todo = {root: 0.0}, deque([root])
    while todo:
        x = todo.popleft()
        for y, lag in adj.get(x, []):
            if y not in out:
                out[y] = out[x] + lag
                todo.append(y)
    return out


def rounded(xs: list | None, nd: int = 3) -> list:
    return [None if x is None else round(float(x), nd) for x in xs or []]


def link_frames(n: str, data: dict) -> dict:
    """From a built pair report's data.json, what group.html's frame-by-frame view needs: the pair's
    A and B, its lag, the per-frame curves (on A's clock), and the change map and outline sprites
    (one a second on A's clock, cut from the report's stills sheet)."""
    cf = data.get("curves", {}).get("frames", {})
    sprites = {}
    for k in ("mask", "edges"):
        sp = dict((data.get("sprites") or {}).get(k) or {})
        if sp.get("sheet"):
            sp["sheet"] = f"pairs/{n}/{sp['sheet']}"
            sp.pop("file", None)
            sprites[k] = sp
    return {"a": data["pair"]["a"], "b": data["pair"]["b"], "lag": float(data["alignment"]["lag"]),
            "times": rounded(cf.get("times"), 2), "edge": rounded(cf.get("edge_ssim")),
            "recolored": rounded(cf.get("recolored")), "reshaped": rounded(cf.get("reshaped")),
            "sprites": sprites}


def group_data(k: int, g: dict, name: str, reports: list[str], vids: dict, assets: dict[str, str],
               feats: dict[str, dict], inten: dict, lags: dict[tuple[str, str], float],
               site: Path | None = None) -> dict:
    """What group.html shows for one group: each version with its video, offset, cuts and measures,
    and for each version the full report that links it back towards the earliest, with that
    report's frame-by-frame data when `site` holds the built reports."""
    edges, parent, cuts = [], {}, {}
    for n in reports:   # the reports' own alignment first: it's the refined one
        a, b = n[4:15], n[16:]
        r = json.loads((HERE / "results" / f"{n}.json").read_text())
        edges.append((a, b, float(r["alignment"]["lag"])))
        ch = r["signals"]["changes"]
        info = {"report": n, "changed": (ch.get("area") or {}).get("changed"),
                "audio": r["signals"]["audio"].get("level"), "share": r["alignment"].get("share")}
        built = site / "pairs" / n / "data.json" if site else None
        if built and built.exists():
            info["frames"] = link_frames(n, json.loads(built.read_text()))
        ac = ((r["signals"].get("visual") or {}).get("aligned_cuts") or {}).get("detail") or {}
        cuts.setdefault(a, rounded(ac.get("cuts_a"), 2))
        cuts.setdefault(b, rounded(ac.get("cuts_b"), 2))
        parent[b if a in parent or a == g["videos"][0] else a] = info
    edges += [(p["a"], p["b"], lags[(p["a"], p["b"])]) for p in g["pairs"] if (p["a"], p["b"]) in lags]
    off = offsets(g["videos"][0], edges)
    out = []
    for i, v in enumerate(g["videos"], 1):
        r = vids.get(v) or {}
        out.append({"n": i, "id": v, "title": r.get("title", v), "side": r.get("side", "?"),
                    "published": (r.get("published") or "")[:10], "views": r.get("views"),
                    "likes": r.get("likes"), "url": assets.get(v), "offset": off.get(v),
                    "intensity": intensity(v, *inten["mean_saturation"]),
                    "brightness": intensity(v, *inten["mean_lstar"]), "measures": feats.get(v, {}),
                    "cuts": cuts.get(v, []), "link": parent.get(v)})
    return {"k": k, "name": name, "versions": out}


def split_style(tpl: str) -> tuple[str, str]:
    """search_overview.html's head links and style block, for the label pages."""
    i, j = tpl.index("<style>"), tpl.index("</style>") + len("</style>")
    head = re.sub(r"<title>.*?</title>\s*", "", tpl[:i], flags=re.S)
    return head.strip(), tpl[i:j]


def label_page(label: str, body: str, facts: str, urls: dict[str, str], updated: str) -> str:
    head, style = split_style((HERE / "search_overview.html").read_text())
    title = f"{base.LABEL_NAME[label]} Groups"
    back = base.page_link("base", urls, "Re-skin search: overall results")
    tpl = (HERE / "search_groups.html").read_text()
    return (tpl.replace("__TITLE__", esc(title)).replace("__HEAD__", head)
            .replace("__STYLE__", style).replace("__UPDATED__", esc(updated)).replace("__H1__", esc(title))
            .replace("__LEAD__", esc(base.LABEL_ABOUT[label])).replace("__BACK__", back)
            .replace("__FACTS__", facts).replace("__GROUPS__", body))


def check_reports(dest: Path, selected: list[str], ok: set[str], assets: dict[str, str]) -> list[str]:
    """Problems with the re-skin page's reports: a selected report that is ok in reports.tsv but
    isn't built with its shell, data and stills, or whose videos aren't in the asset store."""
    problems = []
    videos = json.loads((dest / "videos.json").read_text()) if (dest / "videos.json").exists() else {}
    for n in selected:
        if n not in ok:
            continue
        missing = [f for f in ("index.html", "data.json", "stills.jpg")
                   if not (dest / "pairs" / n / f).exists()]
        if missing:
            problems.append(f"{n}: missing {', '.join(missing)}")
        for k, v in (("a", n[4:15]), ("b", n[16:])):
            url = (videos.get(n) or {}).get(k)
            if not url:
                problems.append(f"{n}: no video for {k} ({v})")
            elif assets.get(v) != url:
                problems.append(f"{n}: {k} video {url} isn't {v}'s asset")
    return problems


def manifest(dest: Path) -> Path:
    """<page>.files.json beside the page folder: every file to publish with its index.html (each
    report's own index.html too), as the Artifact tool's `files` list."""
    out = dest.parent / f"{dest.name}.files.json"
    paths = sorted(str(f.relative_to(dest)) for f in files(dest) if f != dest / "index.html")
    out.write_text(json.dumps([{"path": x} for x in paths]))
    return out


def size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def files(path: Path) -> list[Path]:
    return [f for f in path.rglob("*") if f.is_file() and f.name != "slots.json"]


def group_page(head: str, style: str) -> str:
    """group.html: the all-versions report, a page of its own inside the re-skin artifact."""
    tpl = (HERE / "search_group_report.html").read_text()
    return tpl.replace("__HEAD__", head).replace("__STYLE__", style)


def build_label(label: str, groups: dict, vids: dict, notes: dict, urls: dict[str, str],
                updated: str, inten: dict, lags: dict | None = None,
                eligible: dict | None = None) -> Path:
    dest = SITE / label
    dest.mkdir(parents=True, exist_ok=True)
    gl = groups.get(label, {"groups": [], "little_shared": [], "waiting": []})
    strips = base.Strips(dest, make=base.video_strip)
    strips.slots, strips.written = {}, {}   # slots follow this build's order; unchanged sheets are rewritten
    reports_by_group: list[list[str]] = [[] for _ in gl["groups"]]
    titles: dict[str, str] = {}
    if label == "re-skin":
        sel_path = OUT / "report_selection.json"
        selection = json.loads(sel_path.read_text()) if sel_path.exists() else []
        ok = {n for n in ok_reports(LOG)
              if (HERE / "results" / f"{n}.json").exists() and (REPORTS / n).exists()}
        reports_by_group = group_reports(gl["groups"], selection, ok)
        names = [n for g in reports_by_group for n in g]
        assets = json.loads(ASSETS.read_text()) if ASSETS.exists() else {}
        videos = asset_videos(names, assets)
        (dest / "videos.json").write_text(json.dumps(videos, indent=1))
        for n in names:
            data = build_report.public_data(HERE / "results" / f"{n}.json")
            titles[n] = short_title(data)
            has_video = bool(videos[n]["a"])
            build_report.write_pair(n, data, dest / "pairs" / n, site=True, quality=QUALITY, scale=SCALE,
                                    stills_from=REPORTS / n, frames=not has_video)
            for k in ("a", "b"):   # videos come from the asset store, never copied in
                (dest / "pairs" / n / f"{k}.mp4").unlink(missing_ok=True)
        for d in (dest / "pairs").glob("*") if (dest / "pairs").exists() else []:
            if d.name not in names:
                shutil.rmtree(d)
    sections = [group_section(k, g, label, vids, strips, notes, reports_by_group[k - 1], titles, inten)
                for k, g in enumerate(gl["groups"], 1)]
    if label == "re-skin":
        feats = features_by_video(saturation_sources())
        data = [group_data(k, g, story.family_name([vids.get(v, {}).get("title", "") for v in g["videos"]]),
                           reports_by_group[k - 1], vids, assets, feats, inten, lags or {}, dest)
                for k, g in enumerate(gl["groups"], 1)]
        (dest / "group-data.json").write_text(json.dumps(data))
        style = split_style((HERE / "search_overview.html").read_text())
        (dest / "group.html").write_text(group_page(*style))
    if label == "re-skin" and gl["groups"]:
        sections.insert(0, overview_section(gl["groups"], vids, eligible or {}, reports_by_group, notes))
    if label in base.OVERLAP_LABELS:
        sections.append(little_section(gl["little_shared"], len(gl["waiting"]), vids, strips, inten,
                                       gl.get("contained", [])))
    body = "".join(sections) or "<p class='muted'>No groups yet.</p>"
    n_v = sum(len(g["videos"]) for g in gl["groups"])
    n_p = sum(len(g["pairs"]) for g in gl["groups"])
    fact_rows = [("Groups", base.fmt(len(gl["groups"])),
                  f"{base.fmt(n_v)} videos, linked by {base.fmt(n_p)} pairs")]
    if label in base.OVERLAP_LABELS:
        fact_rows.append(("Little shared", base.fmt(len(gl["little_shared"])),
                          "pairs under half of the shorter video"))
        fact_rows.append(("Inside a longer one", base.fmt(len(gl.get("contained", []))),
                          "pairs under half of the longer video: compilations"))
        fact_rows.append(("Waiting", base.fmt(len(gl["waiting"])), "pairs not downloaded and aligned yet"))
    if label == "re-skin":
        fact_rows.append(("Full reports", base.fmt(sum(map(len, reports_by_group))),
                          f"of {base.fmt(sum(len(g['videos']) - 1 for g in gl['groups']))} (n − 1 a group)"))
    facts = "".join(f"<div class='fact'><span class='eyebrow'>{esc(k)}</span><b>{v}</b><span>{x}</span></div>"
                    for k, v, x in fact_rows)
    (dest / "index.html").write_text(label_page(label, body, facts, urls, updated))
    strips.save()
    if label == "re-skin":
        problems = check_reports(dest, [name_of(p) for p in selection], set(ok_reports(LOG)), assets)
        print(f"{label} check: " + ("all ok reports built, every video in the asset store" if not problems
                                    else f"{len(problems)} problems\n  " + "\n  ".join(problems)))
    manifest(dest)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-base", action="store_true", help="don't rebuild the base page")
    ap.add_argument("--only", nargs="*", choices=base.PAGES, help="build only these label pages")
    args = ap.parse_args()
    urls = base.links()
    if not args.skip_base:
        base.build_base(SITE / "base")
    groups = base.load_groups()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    cols = ("side", "title", "published", "duration", "views", "likes")
    vids = {r[0]: dict(zip(cols, r[1:], strict=True))
            for r in con.execute(f"SELECT id, {', '.join(cols)} FROM videos")}
    eligible = {r[0]: vids[r[0]] for r in con.execute("SELECT id FROM videos WHERE compilation = 0")}
    sources = saturation_sources()
    inten = {key: (saturation_by_video(sources, key), sorted(read_saturation(REFERENCE, key).values()))
             for key, _, _ in LEVELS}
    notes = {}
    for p in sorted((OUT / "labels").glob("*.json")):
        for it in json.loads(p.read_text()):
            notes[(it["a"], it["b"])] = it.get("note", "")
    fin = OUT / "finish.json"
    at = json.loads(fin.read_text())["at"] if fin.exists() else ""
    updated = at.replace("T", " ").rstrip("Z") + " UTC"
    pages = ["base"] * (not args.skip_base) + list(args.only or base.PAGES)
    lags = {(a, b): lag for a, b, lag in con.execute("SELECT a, b, lag FROM overlap WHERE lag IS NOT NULL")}
    for label in args.only or base.PAGES:
        build_label(label, groups, vids, notes, urls, updated, inten, lags, eligible)
    for page in pages:
        d = SITE / page
        n, total = len(files(d)), size(d)
        warn = [w for w, bad in (("OVER 511 files", n > MAX_FILES), ("OVER 256 MB", total > BUDGET)) if bad]
        print(f"{d}: {n} files, {total / 1e6:.1f} MB" + (f"  ({', '.join(warn)})" if warn else ""))


if __name__ == "__main__":
    main()
