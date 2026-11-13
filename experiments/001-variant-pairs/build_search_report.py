"""Build the search's base page (PLAN.md, Search, Deliverables): the re-skin results from
cache/search.db and results/search/, linking to the re-skin groups page (build_search_site.py).

    uv run python 001-variant-pairs/build_search_report.py [DEST]

Writes DEST/index.html (default cache/search/site/base/): facts, the filter chain by pair type
(through download, overlap and groups), what stood out, the channel story and the strategy
profiles, for re-skins only _(human decision, 2026-11-12)_: the other labels' pages stand on their
own. One file, no images. The label pages' URLs come from
cache/search/site/links.json, filled in after they're published. Strips (Strips) are packed
25 to a sheet for the label pages.
"""

from __future__ import annotations

import html
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import report_selection as rs  # noqa: E402
import search_story as story  # noqa: E402
from overlap import MIN_SHARE  # noqa: E402
from review import image_path, tile  # noqa: E402
from search import DB, OUT, TYPES  # noqa: E402

import yt  # noqa: E402

SITE = ROOT / "cache" / "search" / "site"
DEST = SITE / "base"
LINKS = SITE / "links.json"
TYPE_NAME = {"AxB": "Across the channels", "AxA": "Within Kids TV", "BxB": "Within Kids Channel"}
LABEL_NAME = {"re-skin": "Re-skin", "re-upload": "Re-upload", "same-song": "Same song, new animation",
              "same-template": "Same template", "shared-segments": "Shared segments",
              "unrelated": "Unrelated"}
LABEL_ABOUT = {
    "re-skin": "The same animation, re-skinned: new colors, backgrounds or characters over the same timing.",
    "re-upload": "The same video published again, nothing changed.",
    "same-song": "The same song with a new animation.",
    "same-template": "Episodes of one series on one template, with different content.",
    "shared-segments": "Videos that share some footage: compilations, or a short cut from a long video.",
}
PAGES = tuple(LABEL_ABOUT)          # one page per label; unrelated pairs are only counted
OVERLAP_LABELS = ("re-skin", "re-upload")
LABEL = "re-skin"                   # the base page covers re-skins only
CONFIDENT = 0.7
STAGES = [("2", "Candidates", "Any of five image or title signals beats the 99th percentile of random pairs"),
          ("3", "Score", "Screen score from all image and API signals above the cut the seed pair passes"),
          ("4", "Gate", "Auto-frames at 1/4, 1/2, 3/4 (3 × 3) or the thumbnail beat random pairs"),
          ("5", "Agent review", "Labelled re-skin (confidence ≥ 70%) from a sheet of both videos' "
                                "thumbnails and auto-frames"),
          ("6", "Download", "Both videos of confident re-skin pairs"),
          ("6b", "Overlap", "Aligned by audio, or by frames when the audio covers under half: the main "
                            "content (at least half of the shorter video) must overlap")]


def esc(x) -> str:
    return html.escape(str(x))


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def pct(a: int, b: int) -> str:
    if not b:
        return "–"
    p = 100 * a / b
    return f"{p:.2f}%" if p < 10 else f"{p:.0f}%"


STRIP = (1286, 90)   # one strip: A's thumbnail and auto-frames at 1/4, 1/2, 3/4, a gap, then B's
SHEET_ROWS = 25       # strips per sheet (strips/sheet-NN.jpg), stacked top to bottom


def strip_image(a: str, b: str) -> np.ndarray:
    small = (160, 90)
    ts = [cv2.resize(tile(v, k), small, interpolation=cv2.INTER_AREA)
          for v in (a, b) for k in ("thumb", "hq1", "hq2", "hq3")]
    gap = np.full((90, 6, 3), 255, np.uint8)
    return np.hstack(ts[:4] + [gap] + ts[4:])


class Strips:
    """Strips packed into sheets, so a page stays a few files however many strips it shows. Each
    key keeps the slot it got when first shown (DEST/slots.json), so a rebuild only rewrites the
    sheets that gained strips. A key is the IDs the strip shows, joined by spaces; `make` draws
    it (default: a pair's strip_image)."""

    def __init__(self, dest: Path, make=None):
        self.dir, self.file = dest / "strips", dest / "slots.json"
        self.make = make
        saved = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.slots: dict[str, int] = saved.get("slots", {})
        self.written: dict[str, int] = saved.get("written", {})  # sheet -> strips it held when written

    def css(self, *ids: str) -> str:
        """The style that shows the strip: its sheet as a background, at its row."""
        key = " ".join(ids)
        if key not in self.slots:
            self.slots[key] = len(self.slots)
        sheet, row = divmod(self.slots[key], SHEET_ROWS)
        return (f"background-image:url(strips/sheet-{sheet:02d}.jpg);"
                f"background-position:0 {row / (SHEET_ROWS - 1) * 100:.4f}%")

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        make = self.make or strip_image
        by_sheet: dict[int, list[tuple[int, str]]] = {}
        for key, n in self.slots.items():
            by_sheet.setdefault(n // SHEET_ROWS, []).append((n % SHEET_ROWS, key))
        for sheet, rows in by_sheet.items():
            out = self.dir / f"sheet-{sheet:02d}.jpg"
            if self.written.get(str(sheet)) == len(rows) and out.exists():
                continue
            ims = {row: make(*key.split(" ")) for row, key in rows}
            h, w = next(iter(ims.values())).shape[:2]
            img = np.full((h * SHEET_ROWS, w, 3), 255, np.uint8)
            for row, im in ims.items():
                img[row * h:(row + 1) * h] = im
            cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 72])
            self.written[str(sheet)] = len(rows)
        for f in self.dir.glob("*.jpg"):  # single strips of the earlier layout, and dropped sheets
            if not f.name.startswith("sheet-") or int(f.stem[6:]) not in by_sheet:
                f.unlink()
        self.file.write_text(json.dumps({"slots": self.slots, "written": self.written}, indent=0))


def report_links() -> dict[str, str]:
    p = OUT / "reports.tsv"
    if not p.exists():
        return {}
    out = {}
    for ln in p.read_text().splitlines()[1:]:
        f = ln.split("\t")
        out[f[1]] = f[2]
    return out


def video_strip(v: str) -> np.ndarray:
    """One video's strip: its thumbnail and auto-frames at 1/4, 1/2, 3/4."""
    small = (160, 90)
    return np.hstack([cv2.resize(tile(v, k), small, interpolation=cv2.INTER_AREA)
                      for k in ("thumb", "hq1", "hq2", "hq3")])


def links() -> dict[str, str]:
    """Published URLs of the pages (filled in by hand after publishing); "" until then."""
    saved = json.loads(LINKS.read_text()) if LINKS.exists() else {}
    out = {k: saved.get(k, "") for k in ("base", *PAGES)}
    if out != saved:
        LINKS.parent.mkdir(parents=True, exist_ok=True)
        LINKS.write_text(json.dumps(out, indent=1))
    return out


def page_link(label: str, urls: dict[str, str], text: str | None = None) -> str:
    text = esc(text or LABEL_NAME.get(label, label))
    url = urls.get(label, "")
    if url:
        return f"<a href='{esc(url)}'>{text}</a>"
    return f"{text} <span class='muted'>(page not published yet)</span>"


def load_groups() -> dict:
    p = OUT / "groups.json"
    return json.loads(p.read_text()) if p.exists() else {}


def little_shared(groups: dict) -> set[tuple[str, str]]:
    """Pairs that don't count: under half of the shorter video shared, or of the longer (contained)."""
    return {(r["a"], r["b"]) for lab in OVERLAP_LABELS for k in ("little_shared", "contained")
            for r in groups.get(lab, {}).get(k, [])}


def chain_table(con, prog: dict, groups: dict) -> str:
    """The filter chain by pair type, for re-skins: stages 2-4 (before any label) from progress.json,
    5 (confident re-skins), 6, 6b and 7 (groups) from the database."""
    c, s, g = prog["candidates"], prog["score"], prog["gate"]
    conf = con.execute("SELECT a, b, type FROM pairs WHERE label = ? AND confidence >= ?",
                       (LABEL, CONFIDENT)).fetchall()
    have = {v for v in {x for r in conf for x in r[:2]} if yt.video_path(v).exists()}
    shares = {(a, b): {"share": sh, "dur_a": da, "dur_b": db} for a, b, sh, da, db in con.execute(
        "SELECT a, b, share, dur_a, dur_b FROM overlap")} if con.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'overlap'").fetchone() else {}
    labelled = Counter(dict(con.execute("SELECT type, COUNT(*) FROM pairs WHERE label IS NOT NULL "
                                        "GROUP BY type").fetchall()))
    five, six, sixb = {}, {}, {}
    for t in TYPES:
        mine = [r for r in conf if r[2] == t]
        both = [r for r in mine if r[0] in have and r[1] in have]
        aligned = [r for r in both if (r[0], r[1]) in shares]
        main = [r for r in aligned if shares[(r[0], r[1])]["share"] >= MIN_SHARE]
        passed = [r for r in main if (rs.long_share(shares[(r[0], r[1])]) or 1.0) >= MIN_SHARE]
        five[t] = (len(mine), g["passed"][t], f"{fmt(labelled[t])} labelled in all")
        six[t] = (len(both), len(mine), "")
        wait = len(both) - len(aligned)
        sixb[t] = (len(passed), len(aligned), f"{len(aligned) - len(main)} little shared · "
                   f"{len(main) - len(passed)} contained" + (f" · {wait} waiting" if wait else ""))
    cells = {
        "2": [(c["passed"][t], c["pairs_compared"].get(t, 0), "") for t in TYPES],
        "3": [(s["passed"][t], c["passed"][t], "") for t in TYPES],
        "4": [(g["passed"][t], g["passed"][t] + g["stopped"][t], "") for t in TYPES],
        "5": [five[t] for t in TYPES],
        "6": [six[t] for t in TYPES],
        "6b": [sixb[t] for t in TYPES],
    }
    head = "".join(f"<th scope='col'>{esc(TYPE_NAME[t])}<span>{t.replace('x', ' × ')}</span></th>"
                   for t in TYPES)
    total = "".join(f"<td><b>{fmt(c['pairs_total'][t])}</b>"
                    f"<span>{fmt(c['pairs_compared'].get(t, 0))} compared</span></td>" for t in TYPES)
    body = ["<tr><th scope='row'><b>All pairs</b><span>videos up to 30 min, no compilations</span></th>"
            f"{total}</tr>"]
    verbs = {"5": "re-skins", "6": "downloaded", "6b": "overlap"}
    for num, name, rule in STAGES:
        tds = []
        for n_pass, n_in, extra in cells[num]:
            if num == "5":
                sub = f"of {fmt(n_in)} gated pairs and the gate's audit sample · {extra}"
            else:
                sub = f"{pct(n_pass, n_in)} of {fmt(n_in)}" + (f" · {extra}" if extra else "")
            tds.append(f"<td><b>{fmt(n_pass)}</b> {verbs.get(num, 'passed')}<span>{sub}</span></td>")
        body.append(f"<tr><th scope='row'><b>{num}. {esc(name)}</b><span>{esc(rule)}</span></th>"
                    f"{''.join(tds)}</tr>")
    # 7: the re-skin groups, by pair type of their links.
    gl = groups.get(LABEL, {})
    by_t = Counter(r["type"] for grp in gl.get("groups", []) for r in grp["pairs"])
    tds = "".join(f"<td><b>{fmt(by_t[t])}</b> pairs<span>link the groups</span></td>" for t in TYPES)
    n_g = len(gl.get("groups", []))
    n_v = sum(len(x["videos"]) for x in gl.get("groups", []))
    body.append(f"<tr><th scope='row'><b>7. Groups</b>"
                f"<span>{n_g} re-skin groups of {n_v} videos</span></th>{tds}</tr>")
    return (f"<table class='chain'><thead><tr><th></th>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def facts(con, prog: dict, groups: dict) -> str:
    inv, im = prog["inventory"], prog["images"]
    fin = json.loads((OUT / "finish.json").read_text()) if (OUT / "finish.json").exists() else {}
    dl = fin.get("downloads", {})
    rep = fin.get("reports", {})
    sk = groups.get("re-skin", {}).get("groups", [])
    labelled = con.execute("SELECT COUNT(*) FROM pairs WHERE label = ? AND confidence >= ?",
                           (LABEL, CONFIDENT)).fetchone()[0]
    rows = [
        ("Videos", fmt(inv["eligible"]),
         f"of {fmt(inv['videos'])}; {fmt(inv['compilations'])} compilations left out"),
        ("Images", fmt(im["requests_this_run"]), f"requests, {im['errors']} errors"),
        ("Re-skins labelled", fmt(labelled), "pairs the agent took for re-skins (70% or more)"),
        ("Re-skin groups", fmt(len(sk)),
         f"{sum(len(x['videos']) for x in sk)} videos whose main content overlaps"),
    ]
    if dl:
        rows.append(("Downloads", f"{dl['videos_left']} left",
                     f"{dl['player_used_today']} of {dl['player_per_day']} player requests today; "
                     f"{esc(dl['state'])}"))
    if rep:
        rows.append(("Full reports", f"{rep['ok']} / {rep['selected']}",
                     f"selected re-skin pairs done; about {rep['mean_min']:.0f} min each"))
    return "".join(f"<div class='fact'><span class='eyebrow'>{esc(k)}</span><b>{v}</b><span>{x}</span></div>"
                   for k, v, x in rows)


def label_cards(groups: dict, urls: dict[str, str]) -> str:
    """One card: the re-skin groups page."""
    gl = groups.get(LABEL, {"groups": [], "little_shared": [], "waiting": []})
    n_g, n_v = len(gl["groups"]), sum(len(x["videos"]) for x in gl["groups"])
    extra = (f" {len(gl['little_shared'])} more pairs looked alike but share under half;"
             f" {len(gl.get('contained', []))} are one video inside a longer one (a compilation);"
             f" {len(gl['waiting'])} wait for their download and alignment.")
    return (f"<div class='facts'><div class='fact'><span class='eyebrow'>"
            f"{page_link(LABEL, urls, 'Re-skin groups')}</span><b>{fmt(n_g)} groups</b>"
            f"<span>{fmt(n_v)} videos. {esc(LABEL_ABOUT[LABEL])}{esc(extra)}</span></div></div>")


def stood_out(groups: dict) -> str:
    sk = groups.get("re-skin", {}).get("groups", [])
    by_t = Counter(r["type"] for grp in sk for r in grp["pairs"])
    little = len(groups.get("re-skin", {}).get("little_shared", []))
    big = max(sk, key=lambda x: len(x["videos"]), default=None)
    text = (f"{len(sk)} re-skin groups so far, linked by {sum(by_t.values())} pairs: "
            f"{by_t['AxB']} across the "
            f"channels, {by_t['AxA']} within Kids TV, {by_t['BxB']} within Kids Channel.")
    if big:
        text += f" The largest group has {len(big['videos'])} versions."
    contained = len(groups.get("re-skin", {}).get("contained", []))
    if little:
        text += (f" {little} pairs the agent took for re-skins share less than half of the shorter video "
                 "(often just an intro), so they don't count.")
    if contained:
        text += (f" {contained} more hold one video inside a longer one (a compilation, or a short cut from "
                 "a longer video), so they don't count either.")
    return text


def build_base(dest: Path = DEST) -> Path:
    con = sqlite3.connect(DB, timeout=120)
    prog = json.loads((OUT / "progress.json").read_text())
    groups = load_groups()
    urls = links()
    notes = {}
    for p in sorted((OUT / "labels").glob("*.json")):
        for it in json.loads(p.read_text()):
            notes[(it["a"], it["b"])] = it.get("note", "")
    # The story and profiles count only re-skins whose main content overlaps (or not aligned yet).
    out = little_shared(groups)
    eligible = {r[0]: {"side": r[1], "title": r[2], "published": r[3], "views": r[4] or 0}
                for r in con.execute("SELECT id, side, title, published, views FROM videos "
                                     "WHERE compilation = 0")}
    labelled_all = [r for r in con.execute("SELECT a, b, type, score, label, confidence FROM pairs "
                                           "WHERE label = ?", (LABEL,)) if (r[0], r[1]) not in out]
    look = story.looks(eligible, ROOT / "cache" / "search" / "overview" / "thumb_look.json", image_path)
    story_html = story.channel_story(eligible, labelled_all, notes, look)
    # Full reports of pairs the agent labelled re-skin (the seed pair and older reports may be others).
    reskin = {(a, b) for a, b, *_ in labelled_all}
    full = []
    for name in story.report_list(OUT / "reports.tsv"):
        t, rest = name.split("-", 1)
        ab = (rest[:11], rest[12:])
        if ab in out or (ab not in reskin and ab[::-1] not in reskin):
            continue
        p = HERE / "results" / f"{name}.json"
        if p.exists():
            full.append((name, json.loads(p.read_text())))
    label_of = {(a, b): (lab, conf) for a, b, _t, _s, lab, conf in labelled_all}
    profiles_html = story.strategy_profiles(full, label_of)
    at = json.loads((OUT / "finish.json").read_text())["at"] if (OUT / "finish.json").exists() else prog["at"]
    page = (HERE / "search_overview.html").read_text()
    page = (page.replace("__UPDATED__", esc(at.replace("T", " ").rstrip("Z") + " UTC"))
            .replace("__FACTS__", facts(con, prog, groups))
            .replace("__CHAIN__", chain_table(con, prog, groups))
            .replace("__STOOD__", esc(stood_out(groups))).replace("__LABELS__", label_cards(groups, urls))
            .replace("__AUDIT__", esc(story.audit_note(con))).replace("__STORY__", story_html)
            .replace("__PROFILES__", profiles_html))
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(page)
    return dest / "index.html"


if __name__ == "__main__":
    print(build_base(Path(sys.argv[1]) if len(sys.argv) > 1 else DEST))
