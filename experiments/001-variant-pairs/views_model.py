"""Part 4 of experiment 001: within a re-skin family, does the more stimulating version get more views?

    uv run python 001-variant-pairs/views_model.py run     # fit; writes results/views/model.json
    uv run python 001-variant-pairs/views_model.py page    # page from model.json -> cache/views/index.html

No YouTube requests: views come from the search run's saved inventory, features from the saved
feature tables, Shorts from the downloaded files' aspect ratio. Method: PLAN.md, "Views and stimulation".

Outcome: log views minus the channel's typical log views for a video released around the same time
(its other videos within +-90 days, same length class): that "expected" value takes age and era in one,
so publish order (`later`) can be tested apart from age. Within-family model, permutation test,
Holm across the three measures; re-upload families give the noise floor; cuts per minute is the placebo.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import optimize, stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

OUT = HERE / "results" / "views"
PAGE_DIR = HERE.parent / "cache" / "views"
TEMPLATE = HERE / "views_report.html"

MEASURES = (
    ("mean_saturation", "Saturation", 10.0, "10 points of saturation (0–255)"),
    ("mean_lstar", "Lightness", 10.0, "10 points of lightness (L*, 0–100)"),
    ("lufs", "Loudness", 3.0, "3 dB of loudness (LUFS)"),
)
PLACEBO = ("cuts_per_min", "Cuts per minute (placebo)", 5.0, "5 cuts a minute")
WINDOW_DAYS = 90  # the channel's other videos within this many days set a video's expected views
MIN_NEIGHBOURS = 10  # fewer: the window doubles until there are enough
SHORT_LEN = 240.0  # length classes for the expected views: up to 4 min, longer
HOLIDAY_RE = re.compile(r"christmas|xmas|santa|halloween|easter|thanksgiving|valentine|new year|diwali", re.I)
N_PERM = 10_000
N_BOOT = 2_000
SEED = 1


# --- Pure helpers ---------------------------------------------------------------------------


def is_holiday(title: str) -> bool:
    return bool(HOLIDAY_RE.search(title or ""))


def days_between(start: str, end: str) -> float:
    """Days from ISO `start` (publish) to ISO `end` (fetch)."""
    a = datetime.fromisoformat(start.replace("Z", "+00:00"))
    b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return (b - a).total_seconds() / 86400


def length_class(duration: float) -> int:
    return 0 if duration <= SHORT_LEN else 1


def expected_log_views(
    target: dict, pool: list[dict], window: float = WINDOW_DAYS, min_n: int = MIN_NEIGHBOURS
) -> tuple[float, int, float] | None:
    """Median log views of `pool` videos on the target's channel, in its length class, published
    within `window` days of it; the window doubles until `min_n` are found (up to 8x).
    Returns (expected, neighbours, window used) or None. `pool` rows: side, t (days), dur, lv."""
    rows = sorted(
        (r["t"], r["lv"])
        for r in pool
        if r["side"] == target["side"] and length_class(r["dur"]) == length_class(target["dur"])
    )
    ts = [t for t, _ in rows]
    w = window
    while w <= window * 8:
        lo, hi = bisect.bisect_left(ts, target["t"] - w), bisect.bisect_right(ts, target["t"] + w)
        if hi - lo >= min_n:
            return float(np.median([lv for _, lv in rows[lo:hi]])), hi - lo, w
        w *= 2
    return None


def split_by_format(videos: list[str], short: dict[str, bool]) -> list[list[str]]:
    """A family that mixes Shorts and long videos becomes one family per format (2 or more kept);
    a video of unknown format stays with the long ones."""
    parts = [[v for v in videos if short.get(v)], [v for v in videos if not short.get(v)]]
    return [p for p in parts if len(p) >= 2]


def demean(a: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Subtract each group's mean (rows of `a`, which may be 1-D or 2-D)."""
    a = np.asarray(a, float)
    out = a.copy()
    for g in np.unique(groups):
        m = groups == g
        out[m] = a[m] - a[m].mean(axis=0)
    return out


def ols_within(y: np.ndarray, X: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Family fixed effects (within transform), then OLS. Returns (beta, cluster-robust SE by group,
    CR1 small-sample correction)."""
    yd, Xd = demean(y, groups), demean(X, groups)
    keep = np.abs(Xd).sum(axis=0) > 1e-12  # a column constant within every family drops out
    beta = np.full(X.shape[1], np.nan)
    se = np.full(X.shape[1], np.nan)
    Xk = Xd[:, keep]
    if Xk.shape[1] == 0:
        return beta, se
    bread = np.linalg.pinv(Xk.T @ Xk)
    b = bread @ Xk.T @ yd
    e = yd - Xk @ b
    meat = np.zeros((Xk.shape[1], Xk.shape[1]))
    ug = np.unique(groups)
    for g in ug:
        m = groups == g
        s = Xk[m].T @ e[m]
        meat += np.outer(s, s)
    G, n, k = len(ug), len(y), Xk.shape[1] + len(ug)
    c = G / max(G - 1, 1) * (n - 1) / max(n - k, 1)
    V = c * bread @ meat @ bread
    beta[keep], se[keep] = b, np.sqrt(np.clip(np.diag(V), 0, None))
    return beta, se


def permute_within(x: np.ndarray, groups: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = x.copy()
    for g in np.unique(groups):
        idx = np.flatnonzero(groups == g)
        out[idx] = x[rng.permutation(idx)]
    return out


def permutation_p(
    y: np.ndarray, X: np.ndarray, col: int, groups: np.ndarray, n: int = N_PERM, seed: int = SEED
) -> float:
    """Two-sided p of X[:, col]'s coefficient, shuffling that column among each family's versions."""
    rng = np.random.default_rng(seed)
    yd, Xd = demean(y, groups), demean(X, groups)
    obs = np.linalg.lstsq(Xd, yd, rcond=None)[0][col]
    hits = 0
    for _ in range(n):
        Xp = Xd.copy()
        Xp[:, col] = permute_within(Xd[:, col], groups, rng)
        hits += abs(np.linalg.lstsq(Xp, yd, rcond=None)[0][col]) >= abs(obs) - 1e-12
    return (hits + 1) / (n + 1)


def holm(ps: list[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


def within_pairs(groups: np.ndarray) -> list[tuple[int, int]]:
    return [
        (i, j)
        for g in np.unique(groups)
        for k, i in enumerate(np.flatnonzero(groups == g))
        for j in np.flatnonzero(groups == g)[k + 1 :]
    ]


def pair_logit(
    lv: np.ndarray,
    offset: np.ndarray,
    X: np.ndarray,
    pairs: list[tuple[int, int]],
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """P(i has more views than j) = logistic(offset_i - offset_j + (X_i - X_j) b), no intercept
    (a pair's order is arbitrary). Ties are left out. Returns b."""
    pairs = [(i, j) for i, j in pairs if lv[i] != lv[j]]
    if not pairs:
        return np.full(X.shape[1], np.nan)
    i, j = np.array(pairs).T
    D, off = X[i] - X[j], offset[i] - offset[j]
    yv = (lv[i] > lv[j]).astype(float)
    w = np.ones(len(yv)) if weights is None else weights[i]

    def nll(b):
        z = off + D @ b
        return float(np.sum(w * (np.logaddexp(0, z) - yv * z))) + 1e-6 * float(b @ b)

    return optimize.minimize(nll, np.zeros(X.shape[1]), method="BFGS").x


def family_weights(groups: np.ndarray) -> np.ndarray:
    """Each family counts once in the pairwise fit: 1 / its number of pairs."""
    out = np.zeros(len(groups))
    for g in np.unique(groups):
        m = groups == g
        k = m.sum()
        out[m] = 1 / (k * (k - 1) / 2)
    return out


def bootstrap_families(groups: np.ndarray, n: int, rng: np.random.Generator, size: int | None = None):
    """Yield (row index, new group labels) for family-resampled data sets of `size` families."""
    fams = np.unique(groups)
    rows = {g: np.flatnonzero(groups == g) for g in fams}
    for _ in range(n):
        pick = rng.choice(fams, size=size or len(fams), replace=True)
        idx = np.concatenate([rows[g] for g in pick])
        lab = np.concatenate([np.full(len(rows[g]), k) for k, g in enumerate(pick)])
        yield idx, lab


# --- Data -----------------------------------------------------------------------------------


def fetch_dates(api_dir: Path) -> dict[str, str]:
    """video -> when its views were first saved (the cached videos.list response's file time)."""
    out: dict[str, float] = {}
    for p in api_dir.glob("videos-*.json"):
        t = p.stat().st_mtime
        try:
            items = json.loads(p.read_text()).get("items", [])
        except (OSError, ValueError):
            continue
        for it in items:
            out[it["id"]] = min(t, out.get(it["id"], t))
    return {v: datetime.fromtimestamp(t, UTC).isoformat() for v, t in out.items()}


def aspect_short(path: Path) -> bool | None:
    """True for a vertical or square video (a Short), None when the file can't be read."""
    if not path.exists():
        return None
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except ValueError:
        return None
    return h >= w


def load() -> dict:
    import build_search_site as s

    from tools import yt

    groups = json.loads((HERE / "results" / "search" / "groups.json").read_text())
    con = sqlite3.connect(f"file:{s.DB}?mode=ro", uri=True)
    cols = ("side", "title", "published", "duration", "views", "likes", "compilation")
    vids = {
        r[0]: dict(zip(cols, r[1:], strict=True))
        for r in con.execute(f"SELECT id, {', '.join(cols)} FROM videos")
    }
    fetched = fetch_dates(yt.CACHE / "api")
    src = s.saturation_sources()
    feats = {m: s.saturation_by_video(src, m) for m, *_ in (*MEASURES, PLACEBO)}
    fam = {k: [g["videos"] for g in groups[k]["groups"]] for k in ("re-skin", "re-upload")}
    members = {v for k in fam for g in fam[k] for v in g}
    short = {v: aspect_short(yt.video_path(v)) for v in members}
    return {"vids": vids, "fetched": fetched, "feats": feats, "fam": fam, "short": short}


def build_rows(data: dict, window: float = WINDOW_DAYS) -> dict:
    """Per family kind: one row per usable video (expected views set, views > 0)."""
    vids, fetched = data["vids"], data["fetched"]
    epoch = "2005-01-01T00:00:00Z"
    members = {v for k in data["fam"] for g in data["fam"][k] for v in g}
    pool = [
        {
            "side": r["side"],
            "t": days_between(epoch, r["published"]),
            "dur": r["duration"] or 0,
            "lv": math.log(r["views"]),
        }
        for v, r in vids.items()
        if v not in members and not r["compilation"] and (r["views"] or 0) > 0
    ]
    out, dropped = {}, {}
    for kind, fams in data["fam"].items():
        rows, drop = [], {"no views": 0, "no expected": 0, "split or too small": 0}
        for gi, g in enumerate(fams):
            g = [v for v in g if v in vids]
            for part_i, part in enumerate(split_by_format(g, data["short"])):
                part_rows = []
                for v in part:
                    r = vids[v]
                    if not r["views"]:
                        drop["no views"] += 1
                        continue
                    tgt = {
                        "side": r["side"],
                        "t": days_between(epoch, r["published"]),
                        "dur": r["duration"] or 0,
                    }
                    exp = expected_log_views(tgt, pool, window)
                    if exp is None:
                        drop["no expected"] += 1
                        continue
                    part_rows.append(
                        {
                            "family": f"{kind[:2]}{gi:03d}-{part_i}",
                            "video": v,
                            "side": r["side"],
                            "title": r["title"],
                            "published": r["published"],
                            "views": r["views"],
                            "likes": r["likes"],
                            "duration": r["duration"],
                            "age_days": days_between(r["published"], fetched.get(v, "2026-11-12T00:00:00Z")),
                            "expected": exp[0],
                            "neighbours": exp[1],
                            "window": exp[2],
                            "short": bool(data["short"].get(v)),
                            "holiday": is_holiday(r["title"]),
                            **{m: data["feats"][m].get(v) for m, *_ in (*MEASURES, PLACEBO)},
                        }
                    )
                if len(part_rows) >= 2:
                    first = min(x["published"] for x in part_rows)
                    for x in part_rows:
                        x["later"] = int(x["published"] != first)
                    rows += part_rows
                else:
                    drop["split or too small"] += len(part_rows)
        out[kind], dropped[kind] = rows, drop
    return {"rows": out, "dropped": dropped}


# --- Analysis -------------------------------------------------------------------------------


def arrays(rows: list[dict], measure: str | None):
    rows = [r for r in rows if measure is None or r.get(measure) is not None]
    # families still with 2 or more versions
    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["family"]] = cnt.get(r["family"], 0) + 1
    rows = [r for r in rows if cnt[r["family"]] >= 2]
    fam_ids = {f: i for i, f in enumerate(sorted({r["family"] for r in rows}))}
    groups = np.array([fam_ids[r["family"]] for r in rows])
    lv = np.array([math.log(r["views"]) for r in rows])
    off = np.array([r["expected"] for r in rows])
    cov = [[r["later"], int(r["holiday"])] for r in rows]
    X = np.array([[r[measure], *c] if measure else c for r, c in zip(rows, cov, strict=True)], float)
    return rows, groups, lv, off, X


def analyse_measure(
    rows: list[dict], measure: str, per: float, n_perm: int = N_PERM, n_boot: int = N_BOOT
) -> dict:
    rows, groups, lv, off, X = arrays(rows, measure)
    y = lv - off
    beta, se = ols_within(y, X, groups)
    p_perm = permutation_p(y, X, 0, groups, n_perm)
    df = max(len(np.unique(groups)) - 1, 1)
    p_t = float(2 * stats.t.sf(abs(beta[0] / se[0]), df)) if se[0] > 0 else float("nan")
    w = family_weights(groups)
    pairs = within_pairs(groups)
    b_pair = pair_logit(lv, off, X, pairs, w)
    rng = np.random.default_rng(SEED)
    boot_b, boot_pair = [], []
    for idx, lab in bootstrap_families(groups, n_boot, rng):
        boot_b.append(ols_within(y[idx], X[idx], lab)[0][0])
        boot_pair.append(pair_logit(lv[idx], off[idx], X[idx], within_pairs(lab), family_weights(lab))[0])
    ci = np.nanpercentile(boot_b, [2.5, 97.5])
    ci_pair = np.nanpercentile(boot_pair, [2.5, 97.5])
    # Plain count: families where the version highest on the measure beats its family's mean residual
    wins, n_fam = 0, 0
    for g in np.unique(groups):
        m = np.flatnonzero(groups == g)
        if np.ptp(X[m, 0]) < 1e-9:
            continue
        n_fam += 1
        top = m[np.argmax(X[m, 0])]
        wins += y[top] > y[m].mean()
    return {
        "measure": measure,
        "n_videos": len(rows),
        "n_families": int(len(np.unique(groups))),
        "beta": float(beta[0]),
        "se": float(se[0]),
        "ci95": [float(ci[0]), float(ci[1])],
        "ratio_per": per,
        "views_ratio": float(math.exp(beta[0] * per)),
        "views_ratio_ci": [float(math.exp(ci[0] * per)), float(math.exp(ci[1] * per))],
        "p_perm": p_perm,
        "p_t": p_t,
        "later": {"beta": float(beta[1]), "se": float(se[1]), "views_ratio": float(math.exp(beta[1]))},
        "holiday": {
            "beta": None if np.isnan(beta[2]) else float(beta[2]),
            "se": None if np.isnan(se[2]) else float(se[2]),
        },
        "pair_odds_ratio": float(math.exp(b_pair[0] * per)),
        "pair_odds_ci": [float(math.exp(ci_pair[0] * per)), float(math.exp(ci_pair[1] * per))],
        "top_wins": int(wins),
        "top_families": n_fam,
        "spread": float(np.std(demean(X[:, 0], groups))),
    }


def noise_floor(rows: list[dict]) -> dict:
    """Within-family spread of views around expected, and the later-version effect, with no measure."""
    rows, groups, lv, off, X = arrays(rows, None)
    y = lv - off
    beta, se = ols_within(y, X, groups)
    resid = demean(y, groups)
    raw = demean(lv, groups)
    return {
        "n_videos": len(rows),
        "n_families": int(len(np.unique(groups))),
        "sd_resid": float(np.std(resid)),
        "sd_raw": float(np.std(raw)),
        "later": {
            "beta": float(beta[0]),
            "se": float(se[0]),
            "views_ratio": float(math.exp(beta[0])),
            "p_t": float(2 * stats.t.sf(abs(beta[0] / se[0]), max(len(np.unique(groups)) - 1, 1)))
            if se[0] > 0
            else None,
        },
    }


def power(
    rows: list[dict], measure: str, sizes=(34, 50, 100, 150, 200), n: int = 400, alpha: float = 0.05 / 3
) -> dict:
    """Share of family-resampled data sets of each size where the measure's cluster-robust t-test
    has p < alpha (Holm's strictest step), taking the pilot's estimate as the truth."""
    rows, groups, lv, off, X = arrays(rows, measure)
    y = lv - off
    rng = np.random.default_rng(SEED + 1)
    out = {}
    for size in sizes:
        hit = 0
        for idx, lab in bootstrap_families(groups, n, rng, size):
            b, s = ols_within(y[idx], X[idx], lab)
            if s[0] > 0 and 2 * stats.t.sf(abs(b[0] / s[0]), size - 1) < alpha:
                hit += 1
        out[str(size)] = hit / n
    return out


def run(n_perm: int = N_PERM, n_boot: int = N_BOOT) -> dict:
    data = load()
    built = build_rows(data)
    skins = built["rows"]["re-skin"]
    res = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "dropped": built["dropped"],
        "measures": [],
        "n_perm": n_perm,
        "n_boot": n_boot,
    }
    for m, label, per, per_text in MEASURES:
        r = analyse_measure(skins, m, per, n_perm, n_boot)
        res["measures"].append({**r, "label": label, "per_text": per_text})
    for r, adj in zip(res["measures"], holm([r["p_perm"] for r in res["measures"]]), strict=True):
        r["p_holm"] = adj
    m, label, per, per_text = PLACEBO
    res["placebo"] = {**analyse_measure(skins, m, per, n_perm, n_boot), "label": label, "per_text": per_text}
    res["noise"] = {"re-skin": noise_floor(skins), "re-upload": noise_floor(built["rows"]["re-upload"])}
    res["power"] = {m: power(skins, m) for m, *_ in MEASURES}
    # Robustness: a wider window for the expected views
    wide = build_rows(data, WINDOW_DAYS * 2)["rows"]["re-skin"]
    res["robust_window"] = {
        m: analyse_measure(wide, m, per, 2_000, 200)["views_ratio"] for m, _, per, _ in MEASURES
    }
    res["rows"] = skins
    res["reupload_rows"] = built["rows"]["re-upload"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "page"))
    args = ap.parse_args()
    if args.cmd == "run":
        res = run()
        for r in res["measures"] + [res["placebo"]]:
            print(
                f"{r['label']:28} n={r['n_videos']:3}/{r['n_families']:2}  x{r['views_ratio']:.2f} per "
                f"{r['per_text']}  CI {r['views_ratio_ci'][0]:.2f}-{r['views_ratio_ci'][1]:.2f}  "
                f"p_perm={r['p_perm']:.3f}  p_holm={r.get('p_holm', float('nan')):.3f}  "
                f"top wins {r['top_wins']}/{r['top_families']}  later x{r['later']['views_ratio']:.2f}"
            )
        for k, n in res["noise"].items():
            print(k, json.dumps(n))
        print("power", json.dumps(res["power"]))
        print("wider window", json.dumps(res["robust_window"]))
        print("dropped", json.dumps(res["dropped"]))
    else:
        import views_page

        views_page.build(json.loads((OUT / "model.json").read_text()), PAGE_DIR)


if __name__ == "__main__":
    main()
