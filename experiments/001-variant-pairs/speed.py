"""Sped-up copies (PLAN.md, Search, "Sped-up copies"): videos re-published at 2x speed, each laid
next to the 1x video it was made from.

    uv run python 001-variant-pairs/speed.py match    # find each 2x video's 1x original
    uv run python 001-variant-pairs/speed.py page     # build cache/search/site/speed/

`match` takes the videos whose titles say they are sped up ("X2 Speed", "2x speed"), and compares
each with every downloaded candidate: the labelled pairs it is in, and same-song videos about twice
as long. A candidate is played at 2x (every second frame embedding) and aligned with the frame
check (visual.frame_alignment / frame_overlap); where they share at least half, frames at matched
moments are compared pixel by pixel. A median difference under SAME_PX (of 255) means the same
picture, only faster; a re-skin differs by 20-60. A 2x video longer than one sped-up candidate is
matched part by part (one was the same 2x song three times in a row). Results go to
results/search/speed.json; videos still to download are listed there and in cache/remote/todo.txt.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import build_search_report as base  # noqa: E402
import build_search_site as site  # noqa: E402
import gate_check  # noqa: E402
from search import DB, OUT  # noqa: E402

import visual as vis  # noqa: E402
import yt  # noqa: E402

SPEED = 2.0
SAME_PX = 10.0       # median abs pixel difference (0-255) at matched moments: the same picture
RATE = 2.0           # frame embeddings a second (gate_check.cached_embed)
NEAR_S = 1.0         # each moment takes the 1x frame closest to it within +-1 s: the lag from the
                     # 2 fps alignment can be off by a frame step, and 2x copies aren't cut exactly
FAST_TITLE = re.compile(r"\b(x\s?2|2\s?x)\b", re.I)
RESULT = OUT / "speed.json"
DEST = site.SITE / "speed"
GENERIC_LEAD = (" Videos linked by this label form a group; each group's versions are numbered by"
                " publish date.")
LEAD_END = " Each family's #1 is the 1x video, then its 2x copies by publish date."


def is_fast_title(title: str) -> bool:
    return bool(FAST_TITLE.search(title))


def to_1x(t: float, lag: float, speed: float = SPEED) -> float:
    """The 1x video's time for the 2x video's time t, with the alignment's lag in 2x time (the
    candidate's time at 2x = t + lag)."""
    return speed * (t + lag)


def parts(n: int, size: int) -> list[tuple[int, int]]:
    """Split n frames into parts of `size` (the last takes the rest when it is at least half)."""
    out, i = [], 0
    while i < n:
        j = min(n, i + size)
        if n - j < size / 2:
            j = n
        out.append((i, j))
        i = j
    return out


def frame_at(v: str, t: float, size=(96, 54)) -> np.ndarray | None:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.2f}", "-i", str(yt.video_path(v)),
                          "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) != size[0] * size[1] * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(size[1], size[0], 3).astype(float)


def frames_near(v: str, t: float, span: float = NEAR_S, fps: int = 8, size=(96, 54)) -> np.ndarray:
    """v's frames from t - span to t + span s, as (n, h, w, 3)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t - span, 0):.2f}", "-t", f"{2 * span:.2f}",
                          "-i", str(yt.video_path(v)), "-vf", f"fps={fps},scale={size[0]}:{size[1]}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    frame = size[0] * size[1] * 3
    n = len(raw) // frame
    return np.frombuffer(raw[:n * frame], np.uint8).reshape(n, size[1], size[0], 3).astype(float)


def best_diff(a: np.ndarray, near: np.ndarray) -> float | None:
    """Mean pixel difference between frame a and its closest frame in `near` (None if empty)."""
    return float(np.abs(near - a).mean(axis=(1, 2, 3)).min()) if len(near) else None


def compare(f: str, c: str, ef: np.ndarray, ec: np.ndarray, t0: float = 0.0) -> dict | None:
    """The 2x frames `ef` (from t0 s into f) against candidate c played at 2x."""
    sub = ec[::int(SPEED)]
    df, dc = len(ef) / RATE, len(sub) / RATE
    seg = vis.frame_alignment(ef, sub, RATE, df, dc)
    if seg is None:
        return None
    share = min(1.0, vis.frame_overlap(ef, sub, RATE, seg) / min(df, dc))
    out = {"cand": c, "share": round(share, 3), "lag": seg.lag, "from_s": t0, "to_s": t0 + df}
    if share >= 0.5:
        lo, hi = max(0.0, -seg.lag), min(df, dc - seg.lag)
        diffs = [d for t in np.linspace(lo, hi, 10)[1:-1]
                 if (a := frame_at(f, t0 + t)) is not None
                 and (d := best_diff(a, frames_near(c, to_1x(t, seg.lag)))) is not None]
        out["pixel_diff"] = round(float(np.median(diffs)), 1) if diffs else None
    return out


def match_fast(f: str, cands: list[str]) -> dict:
    """f's best 1x original: whole, or part by part when f is longer than one sped-up candidate."""
    ef = gate_check.cached_embed(yt.video_path(f))
    embs = {c: gate_check.cached_embed(yt.video_path(c)) for c in cands}
    found = []
    for c, ec in embs.items():
        size = len(ec) // int(SPEED)
        spans = parts(len(ef), size) if len(ef) > 1.5 * size else [(0, len(ef))]
        for i, j in spans:
            r = compare(f, c, ef[i:j], ec, i / RATE)
            if r and r.get("pixel_diff") is not None:
                found.append(r)
    same = [r for r in found if r["pixel_diff"] <= SAME_PX]
    by_part: dict[float, dict] = {}
    for r in sorted(same, key=lambda r: r["pixel_diff"]):
        by_part.setdefault(r["from_s"], r)
    return {"fast": f, "parts": sorted(by_part.values(), key=lambda r: r["from_s"]),
            "closest": sorted(found, key=lambda r: r["pixel_diff"])[:3]}


def song(title: str) -> str:
    """The song a title names: its first four words, lowercased ("wheels on the bus")."""
    return " ".join(re.findall(r"[a-z0-9']+", title.lower())[:4])


def candidates(con: sqlite3.Connection, f: str, vids: dict) -> list[str]:
    """Labelled partners of f, and videos naming the same song, 0.5-3x as long (a 2x video can
    hold the sped-up song several times)."""
    out = {b if a == f else a for a, b in con.execute(
        "SELECT a, b FROM pairs WHERE label IS NOT NULL AND (a = ? OR b = ?)", (f, f))}
    dur, name = vids[f]["duration"], song(vids[f]["title"])
    for v, r in vids.items():
        if r["duration"] and 0.5 <= r["duration"] / dur <= 3.0 and name in " ".join(
                re.findall(r"[a-z0-9']+", r["title"].lower())):
            out.add(v)
    return sorted(v for v in out if v != f and not is_fast_title(vids[v]["title"]))


def load_videos(con: sqlite3.Connection) -> dict:
    cols = ("side", "title", "published", "duration", "views", "likes")
    return {r[0]: dict(zip(cols, r[1:], strict=True))
            for r in con.execute(f"SELECT id, {', '.join(cols)} FROM videos")}


def run_match() -> dict:
    con = sqlite3.connect(DB, timeout=60)
    vids = load_videos(con)
    fast = sorted((v for v, r in vids.items() if is_fast_title(r["title"])),
                  key=lambda v: vids[v]["published"])
    results, missing = [], set()
    for f in fast:
        cands = candidates(con, f, vids)
        have = [c for c in cands if yt.video_path(c).exists()]
        missing |= {v for v in [f, *cands] if not yt.video_path(v).exists()}
        if not yt.video_path(f).exists():
            results.append({"fast": f, "parts": [], "closest": [], "waiting": True})
            continue
        r = match_fast(f, have)
        r["unchecked"] = sorted(set(cands) - set(have))
        results.append(r)
        print(f, [(p["cand"], p["pixel_diff"]) for p in r["parts"]], flush=True)
    out = {"fast": results, "missing": sorted(missing)}
    RESULT.write_text(json.dumps(out, indent=1))
    return out


# --- The page ---------------------------------------------------------------------------------


def ratio_text(r: float) -> str:
    """A 2x copy's views against its original's: "1.3× the original's", "1% of the original's"."""
    return f"{r:.1f}× the original's" if r >= 1 else f"{100 * r:.0f}% of the original's"


def inside_later(orig: str, fast: list[str], vids: dict) -> bool:
    """Whether the 1x video found isn't the original the copies were made from: a longer video (it
    holds more than the sped-up song) or one published after a 2x copy, like a later compilation."""
    song_s = SPEED * max(vids[v]["duration"] for v in fast)
    return (vids[orig]["duration"] > 1.5 * song_s
            or vids[orig]["published"] > min(vids[v]["published"] for v in fast))


def family_summary(fast: list[str], orig: str | None, vids: dict, loops: dict[str, int],
                   compare: bool = True) -> str:
    """One line: the 1x original's views against its 2x copies' (no ratio when `compare` is off)."""
    def views(v):
        return vids.get(v, {}).get("views")
    parts_ = []
    if orig:
        parts_.append(f"1x: {base.fmt(views(orig))} views")
    for v in fast:
        loop = f", played {loops[v]} times in a row" if loops.get(v, 1) > 1 else ""
        known = compare and orig and views(orig) and views(v) is not None
        ratio = (f" ({ratio_text(views(v) / views(orig))})" if known
                 else "")
        parts_.append(f"2x{loop}: {base.fmt(views(v))} views{ratio}")
    return " · ".join(parts_)


def families(res: dict) -> list[dict]:
    """Group the 2x videos by their 1x original (the part matched best decides); unmatched ones
    each on their own."""
    fams: dict[str, dict] = {}
    alone = []
    for r in res["fast"]:
        if not r["parts"]:
            alone.append({"orig": None, "fast": [r["fast"]], "loops": {}, "waiting": r.get("waiting", False),
                          "closest": r.get("closest", []), "unchecked": r.get("unchecked", [])})
            continue
        orig = min(r["parts"], key=lambda p: p["pixel_diff"])["cand"]
        fam = fams.setdefault(orig, {"orig": orig, "fast": [], "loops": {}})
        fam["fast"].append(r["fast"])
        fam["loops"][r["fast"]] = sum(1 for p in r["parts"] if p["cand"] == orig)
    return [*fams.values(), *alone]


def build_page(res: dict) -> Path:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    vids = load_videos(con)
    sources = site.saturation_sources()
    inten = {key: (site.saturation_by_video(sources, key),
                   sorted(site.read_saturation(site.REFERENCE, key).values()))
             for key, _, _ in site.LEVELS}
    DEST.mkdir(parents=True, exist_ok=True)
    strips = base.Strips(DEST, make=base.video_strip)
    strips.slots, strips.written = {}, {}
    fams = families(res)
    sections = []
    for k, fam in enumerate(fams, 1):
        fast = sorted(fam["fast"], key=lambda v: vids[v]["published"])
        videos = ([fam["orig"]] if fam["orig"] else []) + fast
        num = {v: i for i, v in enumerate(videos, 1)}
        rows = site.version_rows(videos, num, vids, strips, inten)
        name = site.esc(vids[videos[0]]["title"].split(" - ")[0].split(" | ")[0])
        if fam["orig"]:
            copies = "#2" if len(videos) == 2 else "#2–#" + str(len(videos))
            later = inside_later(fam["orig"], fam["fast"], vids)
            made = "copy was" if len(fam["fast"]) == 1 else "copies were"
            what = (f"#1 holds the same picture at 1x, inside a longer video "
                    f"({vids[fam['orig']]['duration'] / 60:.0f} min, published "
                    f"{vids[fam['orig']]['published'][:10]}): not the video the 2x {made} made from, "
                    f"which wasn't found. {copies}: the same picture at 2x (matched frame by frame)."
                    if later else
                    f"#1 is the 1x original; {copies} the same picture at 2x (matched frame by frame).")
            line = family_summary(fam["fast"], fam["orig"], vids, fam["loops"], compare=not later)
        else:
            what = ("Its videos aren't downloaded yet: waiting for the laptop." if fam.get("waiting") else
                    "No 1x original found among the downloaded candidates"
                    + (f"; {len(fam['unchecked'])} not downloaded ({', '.join(fam['unchecked'])})."
                       if fam["unchecked"] else "."))
            line = family_summary(fam["fast"], None, vids, {})
        sections.append(
            f"<section class='group' id='g{k}' data-key='{site.esc(videos[0])}' aria-labelledby='g{k}h'>"
            f"<div class='sec-head'><div class='ghead'><h2 id='g{k}h'>"
            f"<span class='gnum'>{k}.</span> {name}</h2>"
            f"<button type='button' class='star' aria-pressed='false' aria-label='Star family {k}, {name}' "
            f"hidden>☆</button></div><p>{site.esc(what)}</p><p class='muted'>{site.esc(line)}</p>"
            f"{site.note_box(k, name)}</div>"
            f"{site.versions_table(rows, f'Versions of family {k}')}</section>")
    strips.save()
    matched = [f for f in fams if f["orig"]]
    n_fast = sum(len(f["fast"]) for f in fams)
    facts = (f"<ul class='facts'><li><b>{n_fast}</b> videos titled as sped up (X2 / 2x speed)</li>"
             f"<li><b>{sum(len(f['fast']) for f in matched)}</b> matched to a 1x video</li>"
             f"<li><b>{len(res['missing'])}</b> candidate {'video' if len(res['missing']) == 1 else 'videos'}"
             f" not downloaded</li></ul>")
    head, style = site.split_style((HERE / "search_overview.html").read_text())
    title = "Sped-up Copies"
    tpl = (HERE / "search_groups.html").read_text()
    page = (tpl.replace("__TITLE__", title).replace("__HEAD__", head).replace("__STYLE__", style)
            .replace("__UPDATED__", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
            .replace("__H1__", title)
            .replace("__LEAD__", "Videos re-published at twice the speed, each next to the 1x video it was "
                                 "made from: same picture, only faster. Their stats side by side.")
            .replace("__BACK__", base.page_link("re-skin", base.links(), "Re-skin groups"))
            .replace("__FACTS__", facts).replace("__GROUPS__", "".join(sections))
            .replace(GENERIC_LEAD, LEAD_END))
    (DEST / "index.html").write_text(page)
    return DEST


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("match", "page"))
    args = ap.parse_args()
    if args.cmd == "match":
        run_match()
    else:
        print(build_page(json.loads(RESULT.read_text())))


if __name__ == "__main__":
    main()
