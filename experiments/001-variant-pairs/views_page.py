"""The results page for part 4 (views and stimulation), from results/views/model.json.

    uv run python 001-variant-pairs/views_model.py page   -> cache/views/index.html

Data goes into the page as JSON; charts are drawn by the page's own script (no libraries).
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "views_report.html"


def x(v: float) -> str:
    """A views ratio as text: 1.18×."""
    return f"{v:.2f}×"


def p_text(p: float | None) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "–"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def families(rows: list[dict]) -> list[dict]:
    """Rows grouped by family, versions in publish order, with views against expected."""
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["family"], []).append(r)
    fams = []
    for f, vs in out.items():
        vs = sorted(vs, key=lambda r: r["published"])
        fams.append(
            {
                "family": f,
                "versions": [
                    {
                        "video": r["video"],
                        "title": r["title"],
                        "side": r["side"],
                        "published": r["published"][:10],
                        "views": r["views"],
                        "expected": round(math.exp(r["expected"])),
                        "vs_expected": r["views"] / math.exp(r["expected"]),
                        "short": r["short"],
                        "holiday": r["holiday"],
                        "sat": r.get("mean_saturation"),
                        "lstar": r.get("mean_lstar"),
                        "lufs": r.get("lufs"),
                    }
                    for r in vs
                ],
            }
        )
    return sorted(fams, key=lambda f: f["versions"][0]["published"])


def later_beats_first(rows: list[dict]) -> tuple[int, int]:
    """(later versions with more raw views than their family's first version, later versions)."""
    fam: dict[str, list[dict]] = {}
    for r in rows:
        fam.setdefault(r["family"], []).append(r)
    wins = n = 0
    for vs in fam.values():
        first = [r for r in vs if not r["later"]]
        if len(first) != 1:
            continue
        for r in vs:
            if r["later"]:
                n += 1
                wins += r["views"] > first[0]["views"]
    return wins, n


def summary(res: dict) -> dict:
    sat = res["measures"][0]
    return {
        "lead_ratio": x(sat["views_ratio"]),
        "lead_ci": f"{x(sat['views_ratio_ci'][0])} to {x(sat['views_ratio_ci'][1])}",
        "n_fam": sat["n_families"],
        "n_vid": sat["n_videos"],
        "skin_later": "{} of {}".format(*later_beats_first(res["rows"])),
        "upload_later": "{} of {}".format(*later_beats_first(res["reupload_rows"])),
    }


def build(res: dict, out_dir: Path) -> Path:
    data = {
        "measures": [
            {
                k: m[k]
                for k in (
                    "label",
                    "per_text",
                    "views_ratio",
                    "views_ratio_ci",
                    "p_perm",
                    "p_holm",
                    "top_wins",
                    "top_families",
                    "pair_odds_ratio",
                    "pair_odds_ci",
                    "n_videos",
                    "n_families",
                    "measure",
                    "beta",
                )
            }
            for m in res["measures"]
        ],
        "placebo": {
            k: res["placebo"][k]
            for k in (
                "label",
                "per_text",
                "views_ratio",
                "views_ratio_ci",
                "p_perm",
                "top_wins",
                "top_families",
                "pair_odds_ratio",
                "pair_odds_ci",
                "measure",
                "beta",
            )
        },
        "noise": res["noise"],
        "power": res["power"],
        "robust": res["robust_window"],
        "families": families(res["rows"]),
        "dropped": res["dropped"],
        "at": res["at"],
        "window": res["window_days"],
        "n_perm": res["n_perm"],
        "n_boot": res["n_boot"],
    }
    page = TEMPLATE.read_text()
    s = summary(res)
    for k, v in s.items():
        page = page.replace("{{" + k + "}}", html.escape(str(v)))
    page = page.replace("{{data}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(page)
    return out
