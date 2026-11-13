"""Overview sections 3 and 4 of the search (PLAN.md, Search, Overview sections), and the audit
note of section 1: the channel story (timeline, lags, families, thumbnail look over time) and
the strategy profiles of the full reports. build_search_report.py puts them on the page.

Everything here reads saved results only (cache/search.db, labels, cached thumbnails, results
JSON); no requests.
"""

from __future__ import annotations

import html
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from search import BOILERPLATE

import metadata as md

B_CREATED = "2014-10-30"   # Kids Channel's creation date (PLAN.md, Results: Owner)
CONFIDENT = 0.7
TYPE_NAME = {"AxB": "Across the channels", "AxA": "Within Kids TV", "BxB": "Within Kids Channel"}
TYPE_SHORT = {"AxB": "A × B", "AxA": "A × A", "BxB": "B × B"}
# Pair-type colors: A's and B's identity colors for within-channel pairs, a green for across
# (checked with the dataviz validator, all pairs: CVD ΔE ≥ 8.4, normal-vision ΔE ≥ 22, ≥ 3:1).
TYPE_VAR = {"AxB": "var(--axb)", "AxA": "var(--a)", "BxB": "var(--b)"}
STOP = BOILERPLATE | {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
                      "learn", "learning", "fun", "video", "videos", "cartoon", "cartoons", "3d", "s",
                      "toddlers", "preschool", "children", "educational", "lets", "let", "us", "official",
                      "episode", "ep", "part", "new", "best", "more", "abc", "vs"}


def esc(x) -> str:
    return html.escape(str(x))


def day(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def days_between(a: str, b: str) -> float:
    return (day(b) - day(a)).total_seconds() / 86400


def fmt_int(n) -> str:
    return f"{n:,}"


def signed(x: float) -> str:
    """A whole number with a true minus sign (or a plus)."""
    return f"{x:+.0f}".replace("-", "\u2212")


def big(n: float) -> str:
    return (f"{n / 1e9:.1f}B" if n >= 1e9 else f"{n / 1e6:.1f}M" if n >= 1e6
            else f"{n / 1e3:.1f}k" if n >= 1e3 else f"{n:.0f}")


def views_span(views: list[float]) -> str:
    """A family's views as min / median / max; a family of two has no median worth showing."""
    if len(views) <= 2:
        return (f"{big(min(views))} / <span class='muted' title='only two videos: no median'>–</span> / "
                f"{big(max(views))}")
    return f"{big(min(views))} / {big(statistics.median(views))} / {big(max(views))}"


# --- Re-skin pairs and families ---------------------------------------------------------------


def reskins(rows: list[tuple]) -> list[dict]:
    """Confident re-skins from pairs rows (a, b, type, score, label, confidence)."""
    return [{"a": a, "b": b, "type": t, "score": s} for a, b, t, s, lab, conf in rows
            if lab == "re-skin" and (conf or 0) >= CONFIDENT]


def families(pairs: list[dict]) -> list[set[str]]:
    """Connected components over re-skin pairs, largest first."""
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        parent[find(p["a"])] = find(p["b"])
    groups = defaultdict(set)
    for x in parent:
        groups[find(x)].add(x)
    return sorted(groups.values(), key=lambda g: (-len(g), sorted(g)))


def family_name(titles: list[str], n: int = 3) -> str:
    """The most common title words (each title counted once), boilerplate left out, in the order
    they appear in the titles."""
    count, first = Counter(), {}
    for t in titles:
        words = [w for w in md.tokens(t) if w not in STOP and not w.isdigit() and len(w) > 1]
        for k, w in enumerate(dict.fromkeys(words)):
            count[w] += 1
            first.setdefault(w, k)
    if not count:
        return "Untitled"
    top = [w for w, _ in sorted(count.items(), key=lambda kv: (-kv[1], first[kv[0]]))[:n]]
    return " ".join(sorted(top, key=lambda w: first[w])).title()


# --- Thumbnail look -------------------------------------------------------------------------


def thumb_look(path: Path) -> tuple[float, float]:
    """Mean HSV saturation (0-1) and mean Lab L* (0-100) of a thumbnail, letterbox bars cut."""
    import cv2
    from search import crop_bars

    img = crop_bars(cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB))
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    return float(hsv[..., 1].mean() / 255), float(lab[..., 0].mean() * 100 / 255)


def looks(vids: dict[str, dict], cache: Path, image_path) -> dict[str, tuple[float, float]]:
    """Thumbnail look per eligible video, cached in `cache` (JSON)."""
    out = json.loads(cache.read_text()) if cache.exists() else {}
    new = False
    for v in vids:
        if v in out:
            continue
        p = image_path(v, "thumb")
        if p is None:
            continue
        out[v] = [round(x, 4) for x in thumb_look(p)]
        new = True
    if new:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out))
    return {v: tuple(x) for v, x in out.items() if v in vids}


def yearly(vids: dict[str, dict], look: dict[str, tuple[float, float]]) -> dict[str, dict[int, tuple]]:
    """Per channel, per year: (median saturation, median L*, videos)."""
    acc = {"A": defaultdict(list), "B": defaultdict(list)}
    for v, r in vids.items():
        if v in look:
            acc[r["side"]][int(r["published"][:4])].append(look[v])
    return {side: {y: (statistics.median(x[0] for x in xs), statistics.median(x[1] for x in xs), len(xs))
                   for y, xs in sorted(d.items())} for side, d in acc.items()}


# --- SVG helpers ----------------------------------------------------------------------------


def year_frac(s: str) -> float:
    d = day(s)
    start = datetime(d.year, 1, 1, tzinfo=UTC)
    return d.year + (d - start).total_seconds() / (366 * 86400)


def timeline_svg(vids: dict[str, dict], pairs: list[dict], y0: int, y1: int, href=None) -> str:
    """Uploads of A and B as faint ticks on a time axis, re-skin pairs as links between the two
    versions (A × B: between the rows; within a channel: arcs on that channel's side). With `href`
    (pair -> URL), each link is a link there."""
    W, L, R = 1120, 92, 16
    yA, yB, H = 118, 228, 330
    x = lambda f: L + (f - y0) / (y1 + 1 - y0) * (W - L - R)  # noqa: E731
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-labelledby="tl-title tl-desc">',
           '<title id="tl-title">Uploads and re-skin pairs over time</title>',
           f'<desc id="tl-desc">Each faint tick is an upload of Kids TV (A, upper row) or Kids Channel '
           f'(B, lower '
           f'row). Each link joins the two versions of a re-skin pair: {len(pairs)} pairs.</desc>']
    for yr in range(y0, y1 + 2):
        gx = x(yr)
        out.append(f'<line x1="{gx:.1f}" x2="{gx:.1f}" y1="24" y2="{H - 26}" class="grid"/>')
        if yr <= y1:
            out.append(f'<text x="{x(yr + 0.5):.1f}" y="{H - 8}" class="tick" '
                       f'text-anchor="middle">{yr}</text>')
    for side, yy, name in (("A", yA, "Kids TV (A)"), ("B", yB, "Kids Channel (B)")):
        out.append(f'<text x="{L - 10}" y="{yy + 4}" class="lab" text-anchor="end">'
                   f'{name.split(" (")[0]}</text>')
        out.append(f'<text x="{L - 10}" y="{yy + 18}" class="tick" text-anchor="end">{side}</text>')
        ticks = "".join(f"M{x(year_frac(r['published'])):.1f} {yy - 7}v14"
                        for r in vids.values() if r["side"] == side)
        out.append(f'<path d="{ticks}" class="up up-{side.lower()}"/>')
    cx = x(year_frac(B_CREATED + "T00:00:00Z"))
    out.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="20" y2="{H - 26}" class="mark"/>')
    out.append(f'<text x="{cx + 6:.1f}" y="18" class="lab">Kids Channel created, 2014-10-30</text>')
    for p in sorted(pairs, key=lambda p: ("AxB", "AxA", "BxB").index(p["type"])):
        va, vb = vids[p["a"]], vids[p["b"]]
        xa, xb = x(year_frac(va["published"])), x(year_frac(vb["published"]))
        if p["type"] == "AxB":
            mid = (yA + yB) / 2
            d = f"M{xa:.1f} {yA + 8} C{xa:.1f} {mid:.1f} {xb:.1f} {mid:.1f} {xb:.1f} {yB - 8}"
        else:
            yy, up = (yA, -1) if p["type"] == "AxA" else (yB, 1)
            hgt = min(78, 10 + abs(xb - xa) * 0.35)
            ys = yy + up * 8
            yc = ys + up * hgt * 1.33
            d = f"M{xa:.1f} {ys} C{xa:.1f} {yc:.1f} {xb:.1f} {yc:.1f} {xb:.1f} {ys}"
        tip = (f"{TYPE_SHORT[p['type']]} re-skin: {va['title'][:60]} ({va['published'][:10]}) and "
               f"{vb['title'][:60]} ({vb['published'][:10]}), "
               f"{abs(days_between(va['published'], vb['published'])):.0f}"
               f" days apart")
        link = (f'<g class="link"><path d="{d}" class="hit"/><path d="{d}" class="ln" '
                f'style="stroke:{TYPE_VAR[p["type"]]}"/><title>{esc(tip)}</title></g>')
        if href:
            link = f'<a href="{esc(href(p))}" aria-label="{esc(tip)}">{link}</a>'
        out.append(link)
    out.append("</svg>")
    return "".join(out)


def look_svg(series: dict[str, dict[int, tuple]], k: int, title: str, lo: float, hi: float, unit: str,
             b_start: float) -> str:
    """One small line chart: a measure per year, A and B as two lines, B's first upload marked."""
    W, H, L, R, T, Bt = 520, 210, 46, 96, 16, 30
    years = sorted({y for s in series.values() for y in s})
    y0, y1 = years[0], years[-1]
    x = lambda f: L + (f - y0) / max(1, y1 - y0) * (W - L - R)  # noqa: E731
    yv = lambda v: T + (1 - (v - lo) / (hi - lo)) * (H - T - Bt)  # noqa: E731
    out = [f'<svg class="viz small" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)} by year, '
           f'median of each channel\'s thumbnails">']
    for g in np.linspace(lo, hi, 5):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{yv(g):.1f}" y2="{yv(g):.1f}" class="grid"/>'
                   f'<text x="{L - 6}" y="{yv(g) + 4:.1f}" class="tick" text-anchor="end">'
                   f'{g:.{0 if hi > 2 else 2}f}</text>')
    for yr in years:
        if (yr - y0) % 2 == 0:
            out.append(f'<text x="{x(yr):.1f}" y="{H - 10}" class="tick" text-anchor="middle">{yr}</text>')
    bx = x(b_start)
    out.append(f'<line x1="{bx:.1f}" x2="{bx:.1f}" y1="{T}" y2="{H - Bt}" class="mark"/>'
               f'<text x="{bx + 4:.1f}" y="{T + 10}" class="tick">B starts</text>')
    ends = {}
    for side, cls in (("A", "a"), ("B", "b")):
        pts = [(x(y), yv(v[k]), y, v[k], v[2]) for y, v in sorted(series[side].items())]
        if not pts:
            continue
        d = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py, *_ in pts)
        out.append(f'<path d="{d}" class="ln2 ln-{cls}"/>')
        for px, py, yr, val, n in pts:
            out.append(f'<g class="pt"><circle cx="{px:.1f}" cy="{py:.1f}" r="9" class="hit"/>'
                       f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" class="dot dot-{cls}"/>'
                       f'<title>{side} {yr}: {val:.{2 if hi <= 2 else 1}f}{unit} '
                       f'(median of {n} thumbnails)</title></g>')
        ends[side] = pts[-1][:2]
    # Direct labels at the line ends, pushed apart so they never overlap.
    if len(ends) == 2:
        (sa, (xa, ya)), (sb, (xb, yb)) = sorted(ends.items(), key=lambda e: e[1][1])
        if yb - ya < 14:
            mid = (ya + yb) / 2
            ends[sa], ends[sb] = (xa, mid - 7), (xb, mid + 7)
    for side, (lx, ly) in ends.items():
        name = "Kids TV" if side == "A" else "Kids Channel"
        out.append(f'<text x="{lx + 8:.1f}" y="{ly + 4:.1f}" class="lab">{name}</text>')
    out.append("</svg>")
    return "".join(out)


# --- Section 3 ------------------------------------------------------------------------------


def channel_story(vids: dict[str, dict], rows: list[tuple], notes: dict, look: dict) -> str:
    rs = reskins(rows)
    rs = [p for p in rs if p["a"] in vids and p["b"] in vids]
    if not vids:
        return "<p class='muted'>No videos yet.</p>"
    y0 = min(int(r["published"][:4]) for r in vids.values())
    y1 = max(int(r["published"][:4]) for r in vids.values())
    by_type = Counter(p["type"] for p in rs)
    legend = "".join(f"<span><i style='background:{TYPE_VAR[t]}'></i>{TYPE_NAME[t]} ({TYPE_SHORT[t]}): "
                     f"{by_type[t]}</span>" for t in ("AxB", "AxA", "BxB"))
    created = B_CREATED + "T00:00:00Z"

    # Lags: each B video that re-skins an A video, from its earliest A partner.
    partners = defaultdict(list)
    for p in rs:
        if p["type"] == "AxB":
            a, b = (p["a"], p["b"]) if vids[p["a"]]["side"] == "A" else (p["b"], p["a"])
            partners[b].append(a)
    lag_rows = []
    for b, aa in partners.items():
        a = min(aa, key=lambda v: vids[v]["published"])
        lag = days_between(vids[a]["published"], vids[b]["published"])
        lag_rows.append((vids[b]["published"], b, a, lag))
    lag_rows.sort()
    lags = [r[3] for r in lag_rows]

    def later(p):
        return max(vids[p["a"]]["published"], vids[p["b"]]["published"])

    windows = []
    for n in (30, 90, 365):
        cnt = Counter(p["type"] for p in rs if 0 <= days_between(created, later(p)) <= n)
        windows.append((n, cnt))
    near = Counter(p["type"] for p in rs
                   if abs(days_between(vids[p["a"]]["published"], vids[p["b"]]["published"])) <= 2)
    within = {t: (sum(1 for p in rs if p["type"] == t and later(p) < created),
                  sum(1 for p in rs if p["type"] == t and later(p) >= created)) for t in ("AxA", "BxB")}

    def cell(cnt):
        return "".join(f"<td>{cnt[t]}</td>" for t in ("AxB", "AxA", "BxB"))

    thead = ("<tr><th scope='col'></th>"
             + "".join(f"<th scope='col'>{TYPE_SHORT[t]}</th>" for t in ("AxB", "AxA", "BxB")) + "</tr>")
    count_rows = "".join(f"<tr><th scope='row'>Later version within {n} days after 2014-10-30</th>"
                         f"{cell(c)}</tr>"
                         for n, c in windows)
    count_rows += f"<tr><th scope='row'>Released 2 days apart or less</th>{cell(near)}</tr>"
    count_rows += f"<tr><th scope='row'>All confident re-skins</th>{cell(by_type)}</tr>"
    within_txt = (f"Within Kids TV, {within['AxA'][0]} re-skin pairs were complete before 2014-10-30 and "
                  f"{within['AxA'][1]} after; within Kids Channel, {within['BxB'][1]} "
                  "(the channel didn't exist before).")
    if lags:
        lag_txt = (f"{len(lags)} Kids Channel videos re-skin a Kids TV video. "
                   "Lag from the earliest Kids TV version: "
                   f"median {signed(statistics.median(lags))} days, from {signed(min(lags))} to "
                   f"{signed(max(lags))}; "
                   f"{sum(1 for x in lags if x < 0)} came out before their Kids TV version.")
    else:
        lag_txt = "No Kids Channel video is a confident re-skin of a Kids TV video yet."
    lag_table = "".join(
        f"<tr><td>{esc(vids[b]['published'][:10])}</td><td><a href='https://www.youtube.com/watch?v={b}'>"
        f"{esc(vids[b]['title'][:70])}</a></td><td>{esc(vids[a]['published'][:10])}</td>"
        f"<td><a href='https://www.youtube.com/watch?v={a}'>{esc(vids[a]['title'][:70])}</a></td>"
        f"<td class='num'>{signed(lag)}</td></tr>" for _, b, a, lag in lag_rows)

    # Families.
    fam_rows = []
    pair_notes = defaultdict(list)
    for p in rs:
        n = notes.get((p["a"], p["b"])) or notes.get((p["b"], p["a"]))
        if n:
            pair_notes[p["a"]].append(n)
    fams = families(rs)
    for g in fams:
        members = sorted(g, key=lambda v: vids[v]["published"])
        views = [vids[v]["views"] or 0 for v in members]
        top = max(members, key=lambda v: vids[v]["views"] or 0)
        side = Counter(vids[v]["side"] for v in members)
        ns = list(dict.fromkeys(n for v in members for n in pair_notes.get(v, [])))
        fam_rows.append(
            f"<tr><th scope='row'>{esc(family_name([vids[v]['title'] for v in members]))}</th>"
            f"<td class='num'>{len(members)}</td><td class='num'>{side['A']} / {side['B']}</td>"
            f"<td>{vids[members[0]]['published'][:10]} – "
            f"{vids[members[-1]]['published'][:10]}</td>"
            f"<td class='num'>{views_span(views)}</td>"
            f"<td>{'yes' if top == members[0] else 'no'}</td>"
            f"<td class='notes'>{'<br>'.join(esc(n) for n in ns[:3])}"
            f"{f' <span class=muted>(+{len(ns) - 3} more)</span>' if len(ns) > 3 else ''}</td></tr>")
    earliest_top = sum(1 for g in fams if max(g, key=lambda v: vids[v]["views"] or 0)
                       == min(g, key=lambda v: vids[v]["published"]))

    # Feedback: thumbnail look over time.
    ser = yearly(vids, look)
    b_first = min((r["published"] for r in vids.values() if r["side"] == "B"), default=created)
    bf = year_frac(b_first)
    a_side = [(v, r) for v, r in vids.items() if r["side"] == "A" and v in look]
    a_before = [look[v] for v, r in a_side if r["published"] < b_first]
    a_after = [look[v] for v, r in a_side if r["published"] >= b_first]
    b_all = [look[v] for v, r in vids.items() if r["side"] == "B" and v in look]

    def med(xs, k):
        return statistics.median(x[k] for x in xs) if xs else float("nan")

    look_txt = (f"Median thumbnail saturation: Kids TV {med(a_before, 0):.2f} before Kids Channel's "
                f"first upload ({b_first[:10]}, {len(a_before)} thumbnails) and {med(a_after, 0):.2f} after "
                f"({len(a_after)}); "
                f"Kids Channel {med(b_all, 0):.2f} ({len(b_all)}). Median lightness (L*): Kids TV "
                f"{med(a_before, 1):.0f} before and {med(a_after, 1):.0f} after; "
                f"Kids Channel {med(b_all, 1):.0f}. "
                "These numbers describe the thumbnails over time, not why they look the way they do.")
    have_looks = any(ser[k] for k in ser)
    sat_hi = max(0.2, math.ceil(max([v[0] for s in ser.values() for v in s.values()] + [0.5]) * 10) / 10)
    charts = "<p class='muted'>No thumbnails measured yet.</p>"
    if have_looks:
        charts = (f"<figure class='mini'>{look_svg(ser, 0, 'Thumbnail saturation', 0, sat_hi, '', bf)}"
                  f"<figcaption>Saturation, median per year (HSV, 0–1)</figcaption></figure>"
                  f"<figure class='mini'>{look_svg(ser, 1, 'Thumbnail lightness', 0, 100, ' L*', bf)}"
                  f"<figcaption>Lightness, median per year (L*, 0–100)</figcaption></figure>")
    look_table = "".join(
        f"<tr><th scope='row'>{y}</th>"
        + "".join(f"<td class='num'>{ser[s][y][0]:.2f}</td><td class='num'>{ser[s][y][1]:.0f}</td>"
                  f"<td class='num'>{ser[s][y][2]}</td>" if y in ser[s] else "<td>–</td><td>–</td><td>–</td>"
                  for s in ("A", "B")) + "</tr>"
        for y in sorted({y for s in ser.values() for y in s}))

    more_fams = (f"<details><summary>The other {len(fam_rows) - 12} families</summary>"
                 f"{fam_table(fam_rows[12:])}</details>" if len(fam_rows) > 12 else "")
    lag_head = ("<tr><th scope='col'>B published</th><th scope='col'>Kids Channel video</th>"
                "<th scope='col'>A published</th><th scope='col'>Earliest Kids TV version</th>"
                "<th scope='col'>Lag, days</th></tr>")
    look_head = ("<tr><th scope='col'>Year</th><th scope='col'>A saturation</th><th scope='col'>A L*</th>"
                 "<th scope='col'>A videos</th><th scope='col'>B saturation</th><th scope='col'>B L*</th>"
                 "<th scope='col'>B videos</th></tr>")
    return f"""
<div class="legend-row">{legend}<span><i class="tickkey"></i>Upload (all {fmt_int(len(vids))} eligible
videos)</span></div>
<div class="viz-scroll" tabindex="0" role="region" aria-label="Timeline, scrolls sideways">
{timeline_svg(vids, rs, y0, y1)}</div>
<p class="muted">Hover a link for its two videos. Links above the Kids TV row join two Kids TV videos;
below the Kids Channel row, two Kids Channel videos.</p>
<h3>Timing of the re-skins</h3>
<p>{esc(lag_txt)} {esc(within_txt)}</p>
<div class="scroll"><table class="data"><thead>{thead}</thead><tbody>{count_rows}</tbody></table></div>
<details><summary>Kids Channel re-skins of Kids TV videos, with the lag ({len(lag_rows)})</summary>
<div class="scroll"><table class="data"><thead>{lag_head}</thead><tbody>{lag_table}</tbody></table></div>
</details>
<h3>Families</h3>
<p>Videos joined by re-skin pairs, directly or through each other: {len(fams)} families. In
{earliest_top} of them the most-viewed member is also the earliest. Names are the most common words of
the members' titles; notes are the reviewers'.</p>
{fam_table(fam_rows[:12])}
{more_fams}
<h3>Feedback: did Kids TV's look move?</h3>
<p>{esc(look_txt)}</p>
<div class="legend-row"><span><i style="background:var(--a)"></i>Kids TV (A)</span>
<span><i style="background:var(--b)"></i>Kids Channel (B)</span></div>
<div class="minis">{charts}</div>
<details><summary>The numbers per year</summary><div class="scroll"><table class="data">
<thead>{look_head}</thead><tbody>{look_table}</tbody></table></div></details>
"""


def fam_table(rows: list[str]) -> str:
    return ("<div class='scroll'><table class='data fam'><thead><tr><th scope='col'>Family</th>"
            "<th scope='col'>Videos</th><th scope='col'>A / B</th><th scope='col'>Published</th>"
            "<th scope='col'>Views min / median / max</th><th scope='col'>Most viewed is earliest</th>"
            f"<th scope='col'>Reviewers' notes</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


# --- Section 4 ------------------------------------------------------------------------------


def _seg_cover(d: dict) -> bool:
    segs = d["alignment"].get("segments") or []
    if not segs:
        return False
    va, vb = (d["videos"][d["pair"][k]] for k in ("a", "b"))
    return segs[0]["a1"] - segs[0]["a0"] >= 0.8 * min(va["duration_s"], vb["duration_s"])


def _features(d: dict) -> bool:
    fb = d["signals"]["changes"].get("features_baseline") or {}
    return bool(fb) and sum(1 for f in fb.values() if f.get("fires")) >= 0.75 * len(fb)


def _audience(d: dict) -> bool:
    st = d["signals"]["changes"].get("audience") or {}
    a, b = (st.get(d["pair"][k], {}) for k in ("a", "b"))
    va, vb = a.get("viewCount", 0), b.get("viewCount", 0)
    if not va or not vb:
        return False
    la, lb = a.get("likeCount", 0) / va, b.get("likeCount", 0) / vb
    r = max(va, vb) / min(va, vb)
    lr = max(la, lb) / min(la, lb) if la and lb else math.inf
    return r < 2 and lr < 1.5


def _parts(d: dict) -> float:
    p = d["signals"]["changes"]["parts"]
    return sum(b - a for a, b in p["only_a"]) + sum(b - a for a, b in p["only_b"])


# The inspection sheet's rows (report.html, SHEET) and their same/different rules.
SHEET = [
    ("Metadata", "Owner", lambda d: d["signals"]["metadata"]["owner"].get("fires")),
    ("Metadata", "Timing", lambda d: d["signals"]["metadata"]["timing_days"].get("fires")),
    ("Metadata", "Title", lambda d: d["signals"]["metadata"]["title"].get("fires")),
    ("Metadata", "Description and tags", lambda d: any(d["signals"]["metadata"][k].get("fires")
                                                       for k in ("description", "tags",
                                                                 "description_lines"))),
    ("Metadata", "Duration", lambda d: d["signals"]["metadata"]["duration"].get("fires")),
    ("Visual", "Thumbnail", lambda d: d["signals"]["visual"]["thumbnail_embedding"].get("fires")
     or d["signals"]["visual"]["thumbnail_hash"].get("fires")),
    ("Visual", "Storyboard", lambda d: d["signals"]["visual"]["storyboard"].get("fires")),
    ("Visual", "Aligned cuts", lambda d: d["signals"]["visual"]["aligned_cuts"].get("fires")),
    ("Visual", "Motion curve", lambda d: d["signals"]["visual"]["motion_magnitude"].get("fires")),
    ("Visual", "Structure", lambda d: d["signals"]["visual"]["structure_edges"].get("fires")),
    ("Visual", "Frame content", lambda d: d["signals"]["visual"]["frame_content"].get("fires")),
    ("Audio", "Audio level",
     lambda d: d["signals"]["audio"].get("level") in ("exact", "adjusted", "backing")),
    ("Audio", "Offset and longest match", _seg_cover),
    ("What changed", "Color", lambda d: (d["signals"]["changes"]["color"].get("delta_e_mean") or 99) < 10),
    ("What changed", "Changed area", lambda d: (d["signals"]["changes"]["area"].get("changed") or 1) < 0.1),
    ("What changed", "Added or cut parts", lambda d: _parts(d) < 2),
    ("What changed", "Our features", _features),
    ("What changed", "Audience", _audience),
]
LEVEL = {"exact": "exact same audio", "adjusted": "same audio, adjusted", "backing": "same backing",
         "rerecorded": "same song, re-recorded", "none": "no shared audio"}


def shared_animation(d: dict) -> bool:
    v = d["signals"]["visual"]
    return bool(v["aligned_cuts"].get("fires") or v["motion_magnitude"].get("fires")
                or v["structure_edges"].get("fires"))


def profile(d: dict) -> str:
    """The pair's strategy in words: what it shares and what changed (PLAN.md, Signal framework)."""
    ch = d["signals"]["changes"]
    out = ["same animation" if shared_animation(d) else "different animation",
           LEVEL.get(d["signals"]["audio"].get("level"), "audio unknown")]
    if not d["signals"]["metadata"]["title"].get("fires"):
        out.append("new title")
    if (ch["color"].get("delta_e_mean") or 0) >= 10:
        out.append("recolored")
    if (ch["area"].get("reshaped") or 0) > 0.3:
        out.append("redrawn parts")
    if _parts(d) >= 2:
        out.append("added or cut parts")
    return ", ".join(out)


def strategy_profiles(reports: list[tuple[str, dict]], labels: dict[tuple[str, str], tuple]) -> str:
    if not reports:
        return "<p class='muted'>No full reports yet.</p>"
    n = len(reports)
    fire = Counter()
    rows = []
    profs = Counter()
    disagree = []
    for name, d in reports:
        same = {row for _, row, rule in SHEET if _safe(rule, d)}
        fire.update(same)
        prof = profile(d)
        profs[prof] += 1
        a, b = d["pair"]["a"], d["pair"]["b"]
        lab, conf = labels.get((a, b)) or labels.get((b, a)) or (None, None)
        anim = shared_animation(d)
        audio = d["signals"]["audio"].get("level")
        src = d["alignment"].get("source") or "audio"
        verdict = "re-skin" if anim else "same song" if audio in ("rerecorded",) else "no shared animation"
        agrees = (lab == "re-skin" and anim) or (lab in ("same-song", "unrelated") and not anim) or (
            lab == "re-upload" and anim)
        if not agrees:
            disagree.append((name, lab, verdict))
        settled = d["signals"]["audio"].get("settled_by")
        rows.append(f"<tr><th scope='row'><a href='#' data-report='{esc(name)}'>{esc(name)}</a></th>"
                    f"<td>{esc(lab or '–')}{f' · {conf:.0%}' if conf else ''}</td><td>{esc(prof)}</td>"
                    f"<td>{len(same)} of {len(SHEET)}</td><td>{esc(src)}</td>"
                    f"<td>{esc(settled or '–')}</td></tr>")
    bars = "".join(
        f"<tr><th scope='row'><span class='cat'>{esc(cat)}</span> {esc(row)}</th>"
        f"<td class='num'>{fire[row]}</td>"
        f"<td class='barcell'><span class='bar' style='width:{fire[row] / n * 100:.1f}%'></span></td>"
        f"<td class='num'>{fire[row] / n:.0%}</td></tr>" for cat, row, _ in SHEET)
    prof_rows = "".join(f"<tr><td>{esc(p)}</td><td class='num'>{c}</td></tr>" for p, c in profs.most_common())
    n_reskin = sum(1 for _, d in reports
                   if (labels.get((d["pair"]["a"], d["pair"]["b"])) or (None,))[0] == "re-skin")
    n_no_anim = sum(1 for name, lab, v in disagree if lab == "re-skin")
    dis = "".join(f"<li><a href='#' data-report='{esc(nm)}'>{esc(nm)}</a>: labelled {esc(lab or '–')}, "
                  f"full report: {esc(v)}</li>" for nm, lab, v in disagree)
    verb = "shows" if n_no_anim == 1 else "show"
    return f"""
<p>{n} pairs have a full report. Of the {n_reskin} the agent labelled re-skins, {n_no_anim} {verb}
no shared animation in the full report (no aligned cuts, motion or outlines beyond other moments of
the same pair).</p>
<h3>How often each signal says “same”</h3>
<div class="scroll"><table class="data sig"><thead><tr><th scope="col">Signal</th><th scope="col">Pairs</th>
<th scope="col"><span class="sr">Share of pairs, as a bar</span></th><th scope="col">Share</th></tr>
</thead><tbody>{bars}</tbody></table></div>
<h3>Strategy profiles</h3>
<p>What each pair shares and what changed, in words: animation (cuts, motion or outlines), the audio
level, and the changes.</p>
<div class="scroll"><table class="data"><thead><tr><th scope="col">Profile</th><th scope="col">Pairs</th>
</tr></thead>
<tbody>{prof_rows}</tbody></table></div>
<h3>Agent label and full report</h3>
{f"<ul class='dis'>{dis}</ul>" if dis else "<p>Every agent label agrees with its full report.</p>"}
<details><summary>Every pair with a full report ({n})</summary><div class="scroll"><table class="data">
<thead><tr>
<th scope="col">Report</th><th scope="col">Agent label</th><th scope="col">Profile</th>
<th scope="col">Sheet rows same</th>
<th scope="col">Aligned by</th><th scope="col">Audio settled by</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></details>
"""


def _safe(rule, d) -> bool:
    try:
        return bool(rule(d))
    except (KeyError, TypeError, ValueError):
        return False


def audit_note(con) -> str:
    reviewed, reskin = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(label = 're-skin' AND confidence >= ?), 0) FROM pairs "
        "WHERE review = 'done' AND gate_state = 'stop'", (CONFIDENT,)).fetchone()
    waiting = con.execute("SELECT COUNT(*) FROM pairs WHERE review = 'audit' "
                          "AND gate_state = 'stop'").fetchone()[0]
    return ("Search audit: a random sample of pairs the gate stopped goes to the agent anyway, to see "
            f"what the gate misses. {reviewed} reviewed so far, {reskin} of them confident re-skins; "
            f"{waiting} more wait for review.")


def report_list(log: Path) -> list[str]:
    if not log.exists():
        return []
    state = {}
    for ln in log.read_text().splitlines()[1:]:
        f = ln.split("\t")
        if len(f) >= 3:
            state[f[1]] = f[2]
    return [n for n, s in state.items() if s == "ok"]
