"""Step 2 of "Search: other channels" (PLAN.md): learn a cascade of cheap classifiers from the
seed search's labelled pairs. Offline: no YouTube requests.

    uv run python 001-variant-pairs/learn.py features      # pair features for all pairs -> cache/learn/
    uv run python 001-variant-pairs/learn.py fit [--with-audit]  # tiers, cascade -> results/learn/
    uv run python 001-variant-pairs/learn.py audit sample  # recall-audit pairs, from the fitted cascade
    uv run python 001-variant-pairs/learn.py audit next [--n 10]  # next audit sheet for the agent
    uv run python 001-variant-pairs/learn.py audit check FILE

Inputs: cache/search.db (videos, labels, overlap; read fresh each run), cache/search/*.npz (image
features per video). Audit labels: results/learn/audit/labels/batch-NNN.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import string
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import metadata as md  # noqa: E402

DB = ROOT / "cache" / "search.db"
FEAT = ROOT / "cache" / "search"
CACHE = ROOT / "cache" / "learn"
OUT = HERE / "results" / "learn"
AUDIT_SHEETS = CACHE / "audit"
AUDIT_LABELS = OUT / "audit" / "labels"

END_SCREEN_S = 30
CONFIDENT = 0.7
OVERLAP_MIN = 0.5
SEED = 0
N_RANDOM = 200_000          # unlabelled pairs sampled as easy negatives
RECALLS = (1.0, 0.99, 0.98, 0.97, 0.95, 0.90)
MEDLEY_RATIO = 2.0         # one video at least this many times longer: a re-skinned song inside a medley
# Screen cut-offs: with ~150 re-skins, 99 % would be set by a single pair, so 98 %.
M_RECALL = 0.98             # recall kept by the metadata screen in the cascade
CASCADE_RECALL = 0.97       # recall kept by metadata + thumbnail screens together
SCREEN_MODEL = "logreg"     # smooth ranking; boosted trees fall off a cliff when a few hard pairs move
AGENT_RECALL = 0.95         # the look-alike model's cut-off: pairs above it go to the agent

# Pair classes
UNLABELLED, POS, REUPLOAD, HARD_NEG, UNSURE, AUDIT_POS = 0, 1, 2, 3, 4, 5
CLASS_NAMES = {UNLABELLED: "unlabelled", POS: "re-skin (confirmed)", REUPLOAD: "re-upload",
               HARD_NEG: "other label", UNSURE: "re-skin or re-upload, unconfirmed",
               AUDIT_POS: "re-skin found by the audit"}

META = ["title_sim", "title_words", "desc", "tags", "dur_logratio", "dur_fit", "dur_min", "days_log",
        "type_axb", "type_axa"]
THUMB = ["thumb_emb", "thumb_outline"]
MID = ["hq2_emb", "hq2_outline", "cross_emb"]
FRAMES = ["frames_emb", "frames_outline"]
TIERS = {"M": META, "I1": META + THUMB, "I2": META + THUMB + MID, "G": META + THUMB + MID + FRAMES}
TIER_NAMES = {"M": "Metadata (0 images)", "I1": "Metadata + thumbnail (1 image)",
              "I2": "Metadata + thumbnail + middle frame (2 images)",
              "G": "Metadata + 4 images (gate frames)",
              "I2f": "Metadata + thumbnail + middle frame, on the pairs that have gate frames"}
# Signals for the narrowing analysis (radius search), higher is closer unless listed.
NARROW = ["title_sim", "title_words", "thumb_emb", "thumb_outline", "hq2_emb", "hq2_outline", "cross_emb",
          "frames_emb", "dur_logratio"]
LOWER_IS_CLOSER = {"dur_logratio", "dur_fit", "days_log"}


# --- Pure helpers (tested) ----------------------------------------------------------------


def pair_pos(i: np.ndarray, j: np.ndarray, n: int) -> np.ndarray:
    """Position of pair (i, j), i != j, in np.triu_indices(n, 1) order."""
    i, j = np.minimum(i, j).astype(np.int64), np.maximum(i, j).astype(np.int64)
    return i * n - i * (i + 1) // 2 + (j - i - 1)


def jaccard_matrix(sets: list[set]) -> np.ndarray:
    """Jaccard similarity of every two sets, as a dense n x n matrix (0 when both are empty)."""
    vocab: dict[str, int] = {}
    rows, cols = [], []
    for r, s in enumerate(sets):
        for x in s:
            rows.append(r)
            cols.append(vocab.setdefault(x, len(vocab)))
    shape = (len(sets), max(1, len(vocab)))
    b = sparse.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=shape)
    inter = (b @ b.T).toarray()
    size = np.asarray(b.sum(axis=1)).ravel()
    union = size[:, None] + size[None, :] - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(union > 0, inter / union, 0.0).astype(np.float32)


def max_dot(mats: list[np.ndarray]) -> np.ndarray:
    """Best match over all combinations of rows' vectors: max over a, b of mats[a] @ mats[b].T.
    Symmetric, since every (a, b) combination is taken."""
    out = None
    for a in mats:
        for b in mats:
            m = a @ b.T
            out = m if out is None else np.maximum(out, m)
    return out


def groups_of(n: int, edges: list[tuple[int, int]]) -> np.ndarray:
    """Connected component id per node (union-find)."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(x) for x in range(n)])


def cut_for_recall(pos_scores: np.ndarray, recall: float) -> float:
    """Lowest score that keeps at least `recall` of the positives (pairs with score >= cut pass)."""
    s = np.sort(pos_scores)[::-1]
    keep = max(1, math.ceil(recall * len(s) - 1e-9))
    return float(s[keep - 1])


def videos_touched(i: np.ndarray, j: np.ndarray, n: int) -> int:
    seen = np.zeros(n, bool)
    seen[i] = True
    seen[j] = True
    return int(seen.sum())


def sample_weights(cls: np.ndarray, n_unlabelled_total: int) -> np.ndarray:
    """Weights for a training sample: sampled unlabelled pairs stand for all unlabelled pairs, hard
    negatives count once, and positives together weigh as much as all negatives."""
    w = np.ones(len(cls))
    unl = cls == UNLABELLED
    if unl.any():
        w[unl] = n_unlabelled_total / unl.sum()
    pos = cls == POS
    if pos.any():
        w[pos] = w[~pos].sum() / pos.sum()
    return w


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    from scipy.stats import beta

    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


# --- Data ----------------------------------------------------------------------------------


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_videos(con: sqlite3.Connection) -> list[dict]:
    cur = con.execute("SELECT id, side, title, published, duration, views, description, tags FROM videos "
                      "WHERE compilation = 0 ORDER BY id")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur]


def class_labels(con: sqlite3.Connection, index: dict[str, int], n: int, with_audit: bool = True) -> dict:
    """Pair classes from the search's labels (fresh from the DB) and the audit's label files."""
    share = {(a, b): s for a, b, s in con.execute("SELECT a, b, share FROM overlap")}
    out: dict[int, int] = {}
    info: dict[int, dict] = {}
    for a, b, label, conf in con.execute("SELECT a, b, label, confidence FROM pairs WHERE label IS NOT NULL"):
        if a not in index or b not in index:
            continue
        p = int(pair_pos(np.array([index[a]]), np.array([index[b]]), n)[0])
        sh = share.get((a, b), share.get((b, a)))
        if label == "re-skin":
            c = POS if conf >= CONFIDENT and sh is not None and sh >= OVERLAP_MIN else UNSURE
        elif label == "re-upload":
            c = REUPLOAD if conf >= CONFIDENT else UNSURE
        else:
            c = HARD_NEG
        out[p] = c
        info[p] = {"a": a, "b": b, "label": label, "confidence": conf, "share": sh, "source": "search"}
    for f in sorted(AUDIT_LABELS.glob("*.json")) if with_audit else []:
        for it in json.loads(f.read_text()):
            a, b = it["a"], it["b"]
            if a not in index or b not in index:
                continue
            p = int(pair_pos(np.array([index[a]]), np.array([index[b]]), n)[0])
            if p in out:
                continue
            lab, conf = it["label"], float(it["confidence"])
            if lab == "re-skin":
                c = AUDIT_POS if conf >= CONFIDENT else UNSURE
            elif lab == "re-upload":
                c = REUPLOAD if conf >= CONFIDENT else UNSURE
            else:
                c = HARD_NEG
            out[p] = c
            info[p] = {"a": a, "b": b, "label": lab, "confidence": conf, "share": None, "source": "audit",
                       "note": it.get("note", "")}
    return {"cls": out, "info": info}


# --- features ------------------------------------------------------------------------------


def build_features() -> None:
    import search

    con = sqlite3.connect(DB, timeout=60)
    vids = load_videos(con)
    n = len(vids)
    ids = [v["id"] for v in vids]
    iu, ju = np.triu_indices(n, 1)
    iu, ju = iu.astype(np.int32), ju.astype(np.int32)
    f: dict[str, np.ndarray] = {}
    print(f"{n} videos, {len(iu):,} pairs", flush=True)

    title_m = search.TitleIndex({v["id"]: v["title"] for v in vids}).m
    f["title_sim"] = (title_m @ title_m.T).toarray()[iu, ju].astype(np.float32)
    f["title_words"] = jaccard_matrix([set(search.title_text(v["title"]).split()) for v in vids])[iu, ju]
    desc = [set(md.tokens(md.URL_RE.sub(" ", v["description"] or ""))) for v in vids]
    f["desc"] = jaccard_matrix(desc)[iu, ju]
    tags = [{md.norm_tag(t) for t in json.loads(v["tags"] or "[]")} for v in vids]
    f["tags"] = jaccard_matrix(tags)[iu, ju]
    d = np.array([max(1.0, v["duration"] or 1.0) for v in vids])
    ld = np.log(d)
    f["dur_logratio"] = np.abs(ld[iu] - ld[ju]).astype(np.float32)
    f["dur_fit"] = np.maximum(0, np.abs(d[iu] - d[ju]) - END_SCREEN_S).astype(np.float32)
    f["dur_min"] = np.minimum(ld[iu], ld[ju]).astype(np.float32)
    t = np.array([md.parse_time(v["published"]).timestamp() / 86400 for v in vids])
    f["days_log"] = np.log1p(np.abs(t[iu] - t[ju])).astype(np.float32)
    side = np.array([v["side"] for v in vids])
    f["type_axb"] = (side[iu] != side[ju]).astype(np.float32)
    f["type_axa"] = ((side[iu] == "A") & (side[ju] == "A")).astype(np.float32)
    print("metadata features done", flush=True)

    feats = [dict(np.load(FEAT / f"{v}.npz")) if (FEAT / f"{v}.npz").exists() else {} for v in ids]

    def mat(key: str, dim: int) -> tuple[np.ndarray, np.ndarray]:
        m = np.zeros((n, dim), np.float32)
        ok = np.zeros(n, bool)
        for r, x in enumerate(feats):
            if key in x:
                m[r] = x[key]
                ok[r] = True
        return m, ok

    def masked(m: np.ndarray, ok: np.ndarray) -> np.ndarray:
        out = m[iu, ju].astype(np.float32)
        out[~(ok[iu] & ok[ju])] = np.nan
        return out

    th, th_ok = mat("thumb_emb", 384)
    f["thumb_emb"] = masked(th @ th.T, th_ok)
    to, to_ok = mat("thumb_outline", 2304)
    f["thumb_outline"] = masked(to @ to.T, to_ok)
    h2, h2_ok = mat("hq2_emb", 384)
    f["hq2_emb"] = masked(h2 @ h2.T, h2_ok)
    ho, ho_ok = mat("hq2_outline", 2304)
    f["hq2_outline"] = masked(ho @ ho.T, ho_ok)
    c = th @ h2.T
    f["cross_emb"] = masked(np.maximum(c, c.T), th_ok & h2_ok)
    del c, to, ho
    print("image features done", flush=True)

    frames_e, frames_o, fr_ok = [], [], np.ones(n, bool)
    for k in ("hq1", "hq2", "hq3"):
        e, ok_e = mat(f"{k}_emb", 384)
        o, ok_o = mat(f"{k}_outline", 2304)
        frames_e.append(e)
        frames_o.append(o)
        fr_ok &= ok_e & ok_o
    f["frames_emb"] = masked(max_dot(frames_e), fr_ok)
    f["frames_outline"] = masked(max_dot(frames_o), fr_ok)
    print("frame features done", flush=True)

    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / "features.npz", **f)
    (CACHE / "videos.json").write_text(json.dumps({"ids": ids, "at": now(),
                                                   "frames_videos": int(fr_ok.sum())}))
    print(f"saved {len(f)} features for {len(iu):,} pairs", flush=True)


def load_features() -> tuple[list[str], dict[str, np.ndarray]]:
    ids = json.loads((CACHE / "videos.json").read_text())["ids"]
    with np.load(CACHE / "features.npz") as z:
        return ids, {k: z[k] for k in z.files}


# --- fit -----------------------------------------------------------------------------------


def make_models() -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "logreg": lambda: make_pipeline(SimpleImputer(strategy="constant", fill_value=0, add_indicator=True),
                                        StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)),
        "boosted": lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=15,
                                                          min_samples_leaf=20, l2_regularization=1.0,
                                                          random_state=SEED),
    }


def matrix(f: dict, cols: list[str], rows: np.ndarray | slice) -> np.ndarray:
    return np.column_stack([f[c][rows] for c in cols]).astype(np.float32)


def fit_tier(f: dict, cols: list[str], cls: np.ndarray, groups_pair: np.ndarray, usable: np.ndarray,
             rng: np.random.Generator, positive=(POS,)) -> dict:
    """Cross-validated models of one tier. Returns per model: score of every pair (out-of-fold for
    training pairs, the fold models' mean for the rest; NaN where the tier can't be used)."""
    from sklearn.model_selection import StratifiedGroupKFold

    is_pos = np.isin(cls, positive)
    unl = np.nonzero(usable & (cls == UNLABELLED))[0]
    rnd = rng.choice(unl, size=min(N_RANDOM, len(unl)), replace=False)
    train = np.concatenate([np.nonzero(usable & (is_pos | (cls == HARD_NEG)))[0], rnd])
    train.sort()
    cls_t = np.where(is_pos[train], POS, cls[train])
    y = (cls_t == POS).astype(int)
    w = sample_weights(cls_t, len(unl))
    x = matrix(f, cols, train)
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
                 .split(x, y, groups_pair[train]))
    out = {}
    for name, mk in make_models().items():
        oof = np.zeros(len(train))
        models = []
        for tr, te in folds:
            m = mk()
            if name == "logreg":
                m.fit(x[tr], y[tr], logisticregression__sample_weight=w[tr])
            else:
                m.fit(x[tr], y[tr], sample_weight=w[tr])
            oof[te] = m.decision_function(x[te])
            models.append(m)
        score = np.full(len(cls), np.nan, np.float32)
        idx = np.nonzero(usable)[0]
        for s in range(0, len(idx), 1_000_000):
            chunk = idx[s:s + 1_000_000]
            xc = matrix(f, cols, chunk)
            score[chunk] = np.mean([m.decision_function(xc) for m in models], axis=0)
        score[train] = oof
        out[name] = {"score": score, "models": models}
        print(f"  {name}: done", flush=True)
    return {"models": out, "train": train, "n_train": len(train), "n_pos": int(y.sum())}


def tier_table(score: np.ndarray, cls: np.ndarray, pos_mask: np.ndarray, medley: np.ndarray, iu, ju,
               n: int, info: dict) -> list[dict]:
    """Pairs kept at each recall of same-length re-skins (the cut is set on them); medley re-skins
    (a song inside a longer video) are reported at the same cut."""
    rows = []
    usable = ~np.isnan(score)
    total = int(usable.sum())
    pos_idx = np.nonzero(pos_mask & ~medley & usable)[0]
    med_idx = np.nonzero(pos_mask & medley & usable)[0]
    for r in RECALLS:
        cut = cut_for_recall(score[pos_idx], r)
        keep = usable & (score >= cut)
        kept = np.nonzero(keep)[0]
        lost = [int(p) for p in pos_idx if score[p] < cut]
        rows.append({
            "recall_target": r, "cut": cut, "pairs_kept": int(keep.sum()), "pairs_total": total,
            "share_kept": keep.sum() / total, "share_ruled_out": 1 - keep.sum() / total,
            "videos_kept": videos_touched(iu[kept], ju[kept], n), "videos_total": n,
            "positives_kept": int((score[pos_idx] >= cut).sum()), "positives": len(pos_idx),
            "medley_kept": int((score[med_idx] >= cut).sum()), "medley": len(med_idx),
            "reuploads_kept": int((keep & (cls == REUPLOAD)).sum()),
            "reuploads": int((usable & (cls == REUPLOAD)).sum()),
            "hard_neg_kept": int((keep & (cls == HARD_NEG)).sum()),
            "lost": [{**info[p], "score": float(score[p])} for p in lost][:20],
        })
    return rows


def importance(tier: dict, f: dict, cols: list[str], cls: np.ndarray) -> list[dict]:
    """Logistic regression coefficients (standardized features) of the first fold, as a readable
    ranking of what carries the tier."""
    m = tier["models"]["logreg"]["models"][0]
    lr = m[-1]
    names = cols + [f"{c} missing" for c in np.array(cols)[m[0].indicator_.features_]] \
        if m[0].indicator_ is not None else cols
    coef = lr.coef_[0]
    return sorted(({"feature": nm, "coef": float(c)} for nm, c in zip(names, coef, strict=False)),
                  key=lambda r: -abs(r["coef"]))


def readable_tree(f: dict, cols: list[str], train: np.ndarray, cls: np.ndarray) -> str:
    from sklearn.tree import DecisionTreeClassifier, export_text

    cls_t = cls[train]
    y = (cls_t == POS).astype(int)
    w = sample_weights(cls_t, int((cls == UNLABELLED).sum()))
    x = np.nan_to_num(matrix(f, cols, train), nan=-1)
    t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=50, random_state=SEED).fit(x, y, sample_weight=w)
    return export_text(t, feature_names=cols, decimals=3)


def narrowing(f: dict, cls: np.ndarray, pos_mask: np.ndarray, n: int, cand_part2: np.ndarray) -> dict:
    out = {"signals": [], "union": [], "part2": {}}
    pos_idx = np.nonzero(pos_mask)[0]
    radii = {}
    for s in NARROW:
        v = f[s]
        low = s in LOWER_IS_CLOSER
        vals = -v if low else v
        ok = ~np.isnan(vals)
        pv = vals[pos_idx]
        pv_ok = pv[~np.isnan(pv)]
        for r in (1.0, 0.98, 0.95):
            if len(pv_ok) == 0:
                continue
            # recall among positives where the signal exists
            cut = cut_for_recall(pv_ok, r)
            within = ok & (vals >= cut)
            k = int(within.sum())
            radii[(s, r)] = cut
            out["signals"].append({"signal": s, "recall_target": r, "radius": float(-cut if low else cut),
                                   "positives_with_signal": len(pv_ok), "pairs_within": k,
                                   "share_of_pairs": k / int(ok.sum()), "neighbours_per_video": 2 * k / n})
    # A union of several ways in: any image signal or title within its 98% radius.
    for r in (0.98, 0.95):
        sigs = ["title_sim", "thumb_emb", "thumb_outline", "hq2_emb", "hq2_outline", "cross_emb"]
        any_in = np.zeros(len(cls), bool)
        for s in sigs:
            any_in |= np.nan_to_num(f[s], nan=-9) >= radii[(s, r)]
        out["union"].append({"signals": sigs, "recall_each": r,
                             "recall": float(any_in[pos_idx].mean()), "pairs": int(any_in.sum()),
                             "neighbours_per_video": 2 * int(any_in.sum()) / n})
    out["part2"] = {"pairs": int(cand_part2.sum()), "recall": float(cand_part2[pos_idx].mean()),
                    "neighbours_per_video": 2 * int(cand_part2.sum()) / n}
    return out


def fit_lookalike(f: dict, cols: list[str], cls: np.ndarray, positive, groups_pair: np.ndarray,
                  usable: np.ndarray, survivors: np.ndarray) -> dict:
    """Second stage: re-skins against everything else that survives the screens (look-alikes the agent
    labelled otherwise, re-uploads, and unlabelled pairs), trained on the survivors themselves.
    Returns per model: reviews needed (in score order, among the survivors) for each recall, and an
    out-of-fold score for every survivor."""
    from sklearn.model_selection import StratifiedGroupKFold

    rows = np.nonzero(survivors & usable & np.isin(cls, (*positive, HARD_NEG, REUPLOAD, UNLABELLED)))[0]
    y = np.isin(cls[rows], positive).astype(int)
    x = matrix(f, cols, rows)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    folds = list(cv.split(x, y, groups_pair[rows]))
    surv = np.nonzero(survivors & usable)[0]
    xs = matrix(f, cols, surv)
    out = {}
    for name, mk in make_models().items():
        oof = np.zeros(len(rows))
        models = []
        for tr, te in folds:
            m = mk()
            m.fit(x[tr], y[tr])
            oof[te] = m.decision_function(x[te])
            models.append(m)
        o = np.argsort(-oof)
        tp = np.cumsum(y[o])
        reviews = {str(r): int(np.searchsorted(tp, math.ceil(r * y.sum() - 1e-9))) + 1
                   for r in (0.90, 0.95, 0.98, 1.0)}
        reviews["of"] = len(rows)
        score = np.full(len(cls), -np.inf, np.float32)
        score[surv] = np.mean([m.decision_function(xs) for m in models], axis=0)  # unsure pairs
        score[rows] = oof
        out[name] = {"reviews_for_recall": reviews, "score": score}
    return out


def fit(with_audit: bool) -> None:
    rng = np.random.default_rng(SEED)
    ids, f = load_features()
    n = len(ids)
    index = {v: i for i, v in enumerate(ids)}
    iu, ju = np.triu_indices(n, 1)
    npairs = len(iu)
    con = sqlite3.connect(DB, timeout=60)
    lab = class_labels(con, index, n, with_audit)
    cls = np.zeros(npairs, np.int8)
    for p, c in lab["cls"].items():
        cls[p] = c
    positive = (POS, AUDIT_POS) if with_audit else (POS,)
    if not with_audit:
        cls[cls == AUDIT_POS] = UNSURE  # left out of training, but not counted as negatives
    pos_mask = np.isin(cls, positive)
    medley = f["dur_logratio"] > math.log(MEDLEY_RATIO)
    counts = zip(*np.unique(cls, return_counts=True), strict=True)
    print("classes:", {CLASS_NAMES[int(k)]: int(v) for k, v in counts}, flush=True)

    # Groups: videos linked by re-skin or re-upload labels stay in one fold.
    edges = [(index[i["a"]], index[i["b"]]) for i in lab["info"].values()
             if i["label"] in ("re-skin", "re-upload")]
    comp = groups_of(n, edges)
    groups_pair = comp[iu]

    # Part 2's candidates (any signal above its p99), for comparison.
    cand = np.zeros(npairs, bool)
    scored = np.zeros(npairs, bool)
    gated = np.zeros(npairs, bool)
    for a, b, sc, gs in con.execute("SELECT a, b, scored, gate_state FROM pairs"):
        if a in index and b in index:
            p = pair_pos(np.array([index[a]]), np.array([index[b]]), n)[0]
            cand[p] = True
            scored[p] = bool(sc)
            gated[p] = gs == "pass"

    info = lab["info"]
    for p, it in info.items():
        it["title_a"] = con.execute("SELECT title FROM videos WHERE id = ?", (it["a"],)).fetchone()[0]
        it["title_b"] = con.execute("SELECT title FROM videos WHERE id = ?", (it["b"],)).fetchone()[0]
        it["pos"] = int(p)

    results = {"at": now(), "with_audit": with_audit, "videos": n, "pairs": npairs,
               "classes": {CLASS_NAMES[int(k)]: int(v) for k, v in zip(*np.unique(cls, return_counts=True),
                                                                      strict=True)},
               "tiers": {}, "importance": {}}
    scores = {}
    frames_ok = ~np.isnan(f["frames_emb"])
    for t, cols in TIERS.items():
        print(f"tier {t}", flush=True)
        usable = frames_ok if t == "G" else np.ones(npairs, bool)
        tier = fit_tier(f, cols, cls, groups_pair, usable, rng, positive)
        results["tiers"][t] = {"name": TIER_NAMES[t], "features": cols, "n_train": tier["n_train"],
                               "n_pos": tier["n_pos"], "models": {}}
        for mname, m in tier["models"].items():
            results["tiers"][t]["models"][mname] = tier_table(m["score"], cls, pos_mask, medley, iu, ju, n,
                                                              info)
            scores[(t, mname)] = m["score"]
        results["importance"][t] = importance(tier, f, cols, cls)
        if t == "M":
            results["tree_M"] = readable_tree(f, cols, tier["train"], np.where(pos_mask, POS, cls))
        del tier

    # Pick the better model per tier: fewer pairs kept at 98 % recall.
    best = {}
    for t in TIERS:
        rows = results["tiers"][t]["models"]
        best[t] = min(rows, key=lambda m: next(r["pairs_kept"] for r in rows[m]
                                               if r["recall_target"] == 0.98))
    results["best_model"] = best

    # Cascade: the M screen keeps M_RECALL of same-length re-skins; the better image screen (I1 or I2)
    # keeps CASCADE_RECALL overall; the look-alike model (L) then orders the survivors for the agent,
    # who reviews from the top down to L's cut-off for a recall target. Agent-confirmed re-skins are
    # downloaded.
    def kept_at_98(t: str) -> int:
        rows = results["tiers"][t]["models"][SCREEN_MODEL]
        return next(r["pairs_kept"] for r in rows if r["recall_target"] == 0.98)

    i_tier = min(("I1", "I2"), key=kept_at_98)
    sm, si = scores[("M", SCREEN_MODEL)], scores[(i_tier, SCREEN_MODEL)]
    all_pos = np.nonzero(pos_mask)[0]
    pos_idx = np.nonzero(pos_mask & ~medley)[0]
    med_idx = np.nonzero(pos_mask & medley)[0]
    cut_m = cut_for_recall(sm[pos_idx], M_RECALL)
    keep_m = sm >= cut_m
    pos_after_m = pos_idx[keep_m[pos_idx]]
    need = math.ceil(CASCADE_RECALL * len(pos_idx) - 1e-9)
    cut_i = cut_for_recall(si[pos_after_m], min(1.0, need / max(1, len(pos_after_m))))
    keep_i = keep_m & (si >= cut_i)
    kept_i = np.nonzero(keep_i)[0]
    kept_m = np.nonzero(keep_m)[0]

    print("look-alike model", flush=True)
    look = {}
    for t in ("M", "I2", "I2f", "G"):
        usable = frames_ok if t in ("G", "I2f") else np.ones(npairs, bool)
        look[t] = fit_lookalike(f, TIERS[t.rstrip("f")], cls, positive, groups_pair, usable, keep_i)
    results["lookalike"] = {t: {m: v["reviews_for_recall"] for m, v in d.items()} for t, d in look.items()}
    l_model = min(look["I2"], key=lambda m: look["I2"][m]["reviews_for_recall"]["0.95"])
    sl = look["I2"][l_model]["score"]
    pos_after_i = pos_idx[keep_i[pos_idx]]
    agent = []
    for r in (0.97, 0.95, 0.90):
        need = math.ceil(r * len(pos_idx) - 1e-9)
        if need > len(pos_after_i):
            continue
        cut_l = cut_for_recall(sl[pos_after_i], need / len(pos_after_i))
        review = keep_i & (sl >= cut_l)
        found = np.nonzero(review & pos_mask)[0]
        agent.append({"recall_target": r, "cut": cut_l, "pairs_reviewed": int(review.sum()),
                      "sheets": math.ceil(review.sum() / 10),
                      "same_length_found": int(review[pos_idx].sum()),
                      "medley_found": int(review[med_idx].sum()),
                      "reuploads_reviewed": int((review & (cls == REUPLOAD)).sum()),
                      "lookalikes_reviewed": int((review & (cls == HARD_NEG)).sum()),
                      "unlabelled_reviewed": int((review & (cls == UNLABELLED)).sum()),
                      "download_videos": videos_touched(iu[found], ju[found], n)})
    order = kept_i[np.argsort(-sl[kept_i])]
    top = {k: {"re_skins": int(pos_mask[order[:k]].sum()),
               "reuploads": int((cls[order[:k]] == REUPLOAD).sum()),
               "lookalikes": int((cls[order[:k]] == HARD_NEG).sum())} for k in (50, 100, 200, 500)}
    lost_i = [p for p in all_pos if not keep_i[p]]
    cascade = {
        "models": {"M": SCREEN_MODEL, "I": f"{i_tier} {SCREEN_MODEL}", "L": f"I2 {l_model}"},
        "m_recall": M_RECALL, "cascade_recall": CASCADE_RECALL, "cut_m": cut_m, "cut_i": cut_i,
        "pairs_total": npairs, "videos_total": n, "positives": len(pos_idx), "medley": len(med_idx),
        "m": {"pairs_kept": int(keep_m.sum()),
              "videos_needing_images": videos_touched(iu[kept_m], ju[kept_m], n),
              "positives_kept": int(keep_m[pos_idx].sum()), "medley_kept": int(keep_m[med_idx].sum())},
        "i": {"pairs_kept": int(keep_i.sum()),
              "videos_needing_gate_frames": videos_touched(iu[kept_i], ju[kept_i], n),
              "positives_kept": int(keep_i[pos_idx].sum()), "medley_kept": int(keep_i[med_idx].sum()),
              "reuploads_kept": int((keep_i & (cls == REUPLOAD)).sum()),
              "lookalikes_kept": int((keep_i & (cls == HARD_NEG)).sum())},
        "agent": agent, "top": top,
        "lost_by_screens": [{**info[int(p)], "medley": bool(medley[p]),
                             "where": "metadata" if not keep_m[p] else "images"} for p in lost_i],
    }
    results["cascade"] = cascade
    results["part2"] = {"candidates": int(cand.sum()), "scored": int(scored.sum()),
                        "gate_pass": int(gated.sum()),
                        "labelled": int(sum(1 for i in info.values() if i["source"] == "search")),
                        "sheets": 583, "download_videos": 364,
                        "positives_in_candidates": int(cand[pos_idx].sum())}
    results["narrowing"] = narrowing(f, cls, pos_mask, n, cand)

    OUT.mkdir(parents=True, exist_ok=True)
    name = "fit_with_audit.json" if with_audit else "fit.json"
    (OUT / name).write_text(json.dumps(results, indent=1, default=float))
    # Cascade scores for the audit sampler.
    np.savez(CACHE / ("scores_with_audit.npz" if with_audit else "scores.npz"), m=sm, i=si, look=sl,
             cand=cand, cut_m=cut_m, cut_i=cut_i, medley=medley,
             cut_l=next(a["cut"] for a in agent if a["recall_target"] == AGENT_RECALL))
    summary(results)


def summary(r: dict) -> None:
    for t, d in r["tiers"].items():
        for m, rows in d["models"].items():
            x = next(row for row in rows if row["recall_target"] == 0.98)
            print(f"{t:3} {m:8} at 98%: keeps {x['pairs_kept']:>9,} pairs ({x['share_kept']:.4%}), "
                  f"{x['videos_kept']} videos; same-length {x['positives_kept']}/{x['positives']}, "
              f"medley {x['medley_kept']}/{x['medley']}")
    c = r["cascade"]
    print(json.dumps({k: c[k] for k in ("models", "m", "i", "agent", "top")}, indent=1, default=float))
    print(json.dumps(r["lookalike"], indent=1))


# --- audit ---------------------------------------------------------------------------------


AUDIT_SIZES = {"below_cut_metadata": 150, "below_cut_images": 150, "below_cut_lookalike": 150,
               "high_single_signal": 150, "random": 100}


def audit_sample() -> None:
    rng = np.random.default_rng(SEED + 1)
    ids, f = load_features()
    n = len(ids)
    index = {v: i for i, v in enumerate(ids)}
    z = np.load(CACHE / "scores.npz")
    sm, si, sl, cand = z["m"], z["i"], z["look"], z["cand"]
    cut_m, cut_i, cut_l = float(z["cut_m"]), float(z["cut_i"]), float(z["cut_l"])
    con = sqlite3.connect(DB, timeout=60)
    labelled = set(class_labels(con, index, n)["cls"])
    taken = np.zeros(len(sm), bool)
    taken[list(labelled)] = True
    strata = {}

    def take(name: str, cands: np.ndarray, k: int) -> None:
        cands = cands[~taken[cands]][:k]
        taken[cands] = True
        strata[name] = {"pairs": [int(p) for p in cands], "population": None}

    out_m = np.nonzero(sm < cut_m)[0]
    take("below_cut_metadata", out_m[np.argsort(-sm[out_m])], AUDIT_SIZES["below_cut_metadata"])
    strata["below_cut_metadata"]["population"] = int(len(out_m))
    out_i = np.nonzero((sm >= cut_m) & (si < cut_i))[0]
    take("below_cut_images", out_i[np.argsort(-si[out_i])], AUDIT_SIZES["below_cut_images"])
    strata["below_cut_images"]["population"] = int(len(out_i))
    out_l = np.nonzero((sm >= cut_m) & (si >= cut_i) & (sl < cut_l))[0]
    take("below_cut_lookalike", out_l[np.argsort(-sl[out_l])], AUDIT_SIZES["below_cut_lookalike"])
    strata["below_cut_lookalike"]["population"] = int(len(out_l))
    # Non-candidates of part 2 with the highest single-signal rank.
    nc = np.nonzero(~cand)[0]
    best_rank = np.zeros(len(nc))
    for s in ("title_sim", "thumb_emb", "thumb_outline", "hq2_emb", "hq2_outline", "cross_emb"):
        v = np.nan_to_num(f[s][nc], nan=-9)
        best_rank = np.maximum(best_rank, np.argsort(np.argsort(v)) / len(v))
    take("high_single_signal", nc[np.argsort(-best_rank)], AUDIT_SIZES["high_single_signal"])
    strata["high_single_signal"]["population"] = int(len(nc))
    take("random", rng.permutation(nc), AUDIT_SIZES["random"])
    strata["random"]["population"] = int(len(nc))
    iu, ju = np.triu_indices(n, 1)
    for s in strata.values():
        s["ab"] = [[ids[iu[p]], ids[ju[p]]] for p in s["pairs"]]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit").mkdir(exist_ok=True)
    (OUT / "audit" / "sample.json").write_text(json.dumps({"at": now(), "strata": strata}, indent=1))
    print({k: len(v["pairs"]) for k, v in strata.items()})


def audit_next(nmax: int) -> None:
    import review

    sample = json.loads((OUT / "audit" / "sample.json").read_text())["strata"]
    done = set()
    for p in AUDIT_LABELS.glob("*.json"):
        done |= {(it["a"], it["b"]) for it in json.loads(p.read_text())}
    sent = set()
    for p in AUDIT_SHEETS.glob("batch-*.json"):
        sent |= {(x["a"], x["b"]) for x in json.loads(p.read_text())["pairs"]}
    todo = [(st, a, b) for st, s in sample.items() for a, b in s["ab"] if (a, b) not in done | sent]
    # Mix strata on each sheet, so the reviewer can't tell which stratum a pair is from.
    rng = np.random.default_rng(len(sent))
    rng.shuffle(todo)
    rows = todo[:nmax]
    if not rows:
        print("nothing to review")
        return
    AUDIT_SHEETS.mkdir(parents=True, exist_ok=True)
    k = 1 + max([int(p.stem.split("-")[1]) for p in AUDIT_SHEETS.glob("batch-*.json")], default=0)
    while True:
        try:
            (AUDIT_SHEETS / f"batch-{k:03d}.json").open("x").close()
            break
        except FileExistsError:
            k += 1
    name = f"batch-{k:03d}"
    con = sqlite3.connect(DB, timeout=60)
    vids = {}
    for v in {x for r in rows for x in r[1:]}:
        t, pub, dur, views, side = con.execute(
            "SELECT title, published, duration, views, side FROM videos WHERE id = ?", (v,)).fetchone()
        vids[v] = {"title": t, "published": pub, "duration_s": dur, "views": views,
                   "channel": "Kids TV" if side == "A" else "Kids Channel"}
    data = {"batch": name, "labels": review.LABELS, "pairs": [
        {"n": i, "a": a, "b": b, "video_a": vids[a], "video_b": vids[b], "stratum": st}
        for i, (st, a, b) in enumerate(rows, 1)]}
    review.sheet([(a, b) for _, a, b in rows], AUDIT_SHEETS / f"{name}.jpg")
    # The stratum stays out of the reviewer's file (kept in sample.json).
    public = {**data, "pairs": [{k: v for k, v in p.items() if k != "stratum"} for p in data["pairs"]]}
    (AUDIT_SHEETS / f"{name}.json").write_text(json.dumps(public, indent=1, ensure_ascii=False))
    print(AUDIT_SHEETS / f"{name}.jpg")
    print(AUDIT_SHEETS / f"{name}.json")


def audit_results() -> dict:
    sample = json.loads((OUT / "audit" / "sample.json").read_text())["strata"]
    labels = {}
    for p in sorted(AUDIT_LABELS.glob("*.json")):
        for it in json.loads(p.read_text()):
            labels[(it["a"], it["b"])] = it
    out = {}
    for st, s in sample.items():
        got = [labels[tuple(ab)] for ab in s["ab"] if tuple(ab) in labels]
        k = sum(1 for it in got if it["label"] == "re-skin" and float(it["confidence"]) >= CONFIDENT)
        lo, hi = clopper_pearson(k, len(got)) if got else (0.0, 1.0)
        out[st] = {"sampled": len(s["ab"]), "labelled": len(got), "re_skins": k,
                   "labels": dict(Counter(it["label"] for it in got)), "rate_ci": [lo, hi],
                   "population": s["population"],
                   "found": [it for it in got
                             if it["label"] == "re-skin" and float(it["confidence"]) >= CONFIDENT]}
    return out


# --- report --------------------------------------------------------------------------------


IMAGE_S = 1.0          # mean gap between image requests (README budget)
DOWNLOADS_PER_DAY = 50


def group_cost(n_videos: int, c: dict, agent: dict) -> dict:
    """What a group of n_videos costs through the cascade, scaled from the seed channels: images by
    the share of videos that need them; agent pairs per video (low) or per pair (high, if look-alike
    pairs grow with the square of the videos)."""
    n0 = c["videos_total"]
    thumbs = n_videos * c["m"]["videos_needing_images"] / n0
    mids = 3 * n_videos * c["i"]["videos_needing_gate_frames"] / n0  # middle, 1/4 and 3/4 frames
    per_video = agent["pairs_reviewed"] / n0
    per_pair = agent["pairs_reviewed"] / (n0 * (n0 - 1) / 2)
    low = per_video * n_videos
    high = per_pair * n_videos * (n_videos - 1) / 2
    dl = n_videos * agent["download_videos"] / n0
    return {"videos": n_videos, "api_units": 2 * math.ceil(n_videos / 50),
            "images": round(thumbs + mids), "image_hours": (thumbs + mids) * IMAGE_S / 3600,
            "agent_pairs": [round(low), round(high)], "sheets": [math.ceil(low / 10), math.ceil(high / 10)],
            "download_videos": round(dl), "download_days": dl / DOWNLOADS_PER_DAY}


def thumb_uri(v: str, kind: str = "thumb", width: int = 160) -> str:
    import base64

    import cv2
    import review
    from search import crop_bars

    import visual as vis

    p = review.image_path(v, kind)
    if p is None:
        return ""
    img = crop_bars(vis.load_image(p))
    h = round(img.shape[0] * width / img.shape[1])
    img = cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def build_report() -> Path:
    from html import escape

    r = json.loads((OUT / "fit.json").read_text())
    def load(p: Path) -> dict | None:
        return json.loads(p.read_text()) if p.exists() else None

    ra = load(OUT / "fit_with_audit.json")
    au = load(OUT / "audit" / "results.json")
    c = r["cascade"]
    a95 = next(x for x in c["agent"] if x["recall_target"] == 0.95)
    p2 = r["part2"]
    fmt = "{:,}".format

    def pct(x: float, d: int = 1) -> str:
        return f"{100 * x:.{d}f}%"

    stages = [("All pairs", r["pairs"], "every two videos of the seed channels"),
              ("Metadata screen", c["m"]["pairs_kept"], "titles, descriptions, tags, durations, dates"),
              ("Thumbnail screen", c["i"]["pairs_kept"], "plus one image per video"),
              ("To the agent", a95["pairs_reviewed"], "ordered by the look-alike model, 95% cut-off"),
              ("Downloads", a95["download_videos"], "videos of agent-confirmed re-skins")]
    lmax = math.log10(r["pairs"])
    funnel = "".join(
        f'<div class="frow"><div class="flabel"><b>{escape(n)}</b><span>{escape(d)}</span></div>'
        f'<div class="ftrack"><div class="fbar" '
        f'style="width:{max(1.5, 100 * math.log10(max(v, 1)) / lmax):.1f}%">'
        f'</div></div><div class="fnum">{fmt(v)}{" videos" if n == "Downloads" else ""}</div></div>'
        for n, v, d in stages)

    def tier_rows(t: str) -> str:
        out = []
        for m in ("logreg", "boosted"):
            for x in r["tiers"][t]["models"][m]:
                if x["recall_target"] not in (1.0, 0.98, 0.95, 0.90):
                    continue
                out.append(f"<tr><td>{'Logistic regression' if m == 'logreg' else 'Boosted trees'}</td>"
                           f"<td>{pct(x['recall_target'], 0)}</td><td>{fmt(x['pairs_kept'])}</td>"
                           f"<td>{pct(x['share_kept'], 2)}</td><td>{fmt(x['videos_kept'])}</td>"
                           f"<td>{x['medley_kept']} of {x['medley']}</td></tr>")
        return "".join(out)

    tiers_html = "".join(
        f'<details{" open" if t == "M" else ""}><summary>{escape(TIER_NAMES[t])}</summary>'
        f'<div class="tw"><table><thead><tr><th>Model</th><th>Re-skins kept</th><th>Pairs kept</th>'
        f'<th>Share</th><th>Videos with a pair</th><th>Medleys kept</th></tr></thead>'
        f'<tbody>{tier_rows(t)}</tbody></table></div></details>' for t in TIERS)

    agent_rows = "".join(
        f"<tr><td>{pct(x['recall_target'], 0)}</td><td>{fmt(x['pairs_reviewed'])}</td>"
        f"<td>{fmt(x['sheets'])}</td>"
        f"<td>{x['same_length_found']} of {c['positives']}</td><td>{x['medley_found']} of {c['medley']}</td>"
        f"<td>{fmt(x['lookalikes_reviewed'])}</td><td>{fmt(x['reuploads_reviewed'])}</td>"
        f"<td>{fmt(x['unlabelled_reviewed'])}</td><td>{x['download_videos']}</td></tr>" for x in c["agent"])

    look_rows = "".join(
        f"<tr><td>{escape(TIER_NAMES[t])}</td>"
        f"<td>{'Logistic regression' if m == 'logreg' else 'Boosted trees'}</td>"
        + "".join(f"<td>{fmt(v[k])}</td>" for k in ("0.9", "0.95", "0.98")) + f"<td>{fmt(v['of'])}</td></tr>"
        for t, d in r["lookalike"].items() for m, v in d.items())

    lost = c["lost_by_screens"]
    lost_cards = "".join(
        f'<figure class="pair"><div class="imgs">'
        f'<img src="{thumb_uri(x["a"])}" alt="Thumbnail of {escape(x["a"])}">'
        f'<img src="{thumb_uri(x["b"])}" alt="Thumbnail of {escape(x["b"])}"></div>'
        f'<figcaption><span class="chip {"med" if x["medley"] else "same"}">'
        f'{"Medley" if x["medley"] else "Same length"}</span> lost at the {x["where"]} screen<br>'
        f'<span class="t">{escape(x["title_a"][:70])}</span>'
        f'<span class="t">{escape(x["title_b"][:70])}</span>'
        f'<code>{x["a"]} · {x["b"]}</code></figcaption></figure>' for x in lost)

    nar = r["narrowing"]
    sig_names = {"title_sim": "Title, character n-grams", "title_words": "Title, shared words",
                 "thumb_emb": "Thumbnail embedding", "thumb_outline": "Thumbnail outline",
                 "hq2_emb": "Middle frame embedding", "hq2_outline": "Middle frame outline",
                 "cross_emb": "Thumbnail against middle frame", "frames_emb": "Best of 3 × 3 frames",
                 "dur_logratio": "Duration ratio"}
    nar_rows = "".join(
        f"<tr><td>{sig_names[x['signal']]}</td><td>{pct(x['recall_target'], 0)}</td>"
        f"<td>{fmt(x['pairs_within'])}</td><td>{x['neighbours_per_video']:,.0f}</td></tr>"
        for x in nar["signals"] if x["recall_target"] in (1.0, 0.98))

    cost_rows = "".join(
        f"<tr><td>{fmt(g['videos'])}</td><td>{fmt(g['api_units'])}</td><td>{fmt(g['images'])} "
        f"({g['image_hours']:.1f} h)</td><td>{fmt(g['agent_pairs'][0])}–{fmt(g['agent_pairs'][1])}</td>"
        f"<td>{fmt(g['sheets'][0])}–{fmt(g['sheets'][1])}</td><td>{fmt(g['download_videos'])} "
        f"({g['download_days']:.1f} days)</td></tr>"
        for g in (group_cost(nv, c, a95) for nv in (1000, 4066, 10000, 30000)))

    audit_html = "<p>The audit hasn't been labelled yet.</p>"
    if au:
        names = {"below_cut_metadata": "Just below the metadata cut-off",
                 "below_cut_images": "Just below the thumbnail cut-off",
                 "below_cut_lookalike": "Survived both screens, below the agent cut-off",
                 "high_single_signal": "Not part 2 candidates, strongest single signal",
                 "random": "Random pairs that weren't part 2 candidates"}
        rows = "".join(
            f"<tr><td>{names[k]}</td><td>{v['labelled']}</td><td>{v['re_skins']}</td>"
            f"<td>{', '.join(f'{lab} {n}' for lab, n in Counter(v['labels']).most_common())}</td>"
            f"<td>{fmt(v['population'])}</td></tr>" for k, v in au.items())
        found = [it | {"stratum": names[k]} for k, v in au.items() for it in v["found"]]
        cards = "".join(
            f'<figure class="pair"><div class="imgs">'
            f'<img src="{thumb_uri(it["a"])}" alt="Thumbnail of {it["a"]}">'
            f'<img src="{thumb_uri(it["b"])}" alt="Thumbnail of {it["b"]}"></div><figcaption>'
            f'<span class="chip same">{escape(it["stratum"])}</span><br>'
            f'<span class="t">{escape(it["note"])}</span>'
            f'<code>{it["a"]} · {it["b"]} · confidence {it["confidence"]}</code></figcaption></figure>'
            for it in found)
        audit_html = ('<div class="tw"><table><thead><tr><th>Sample</th><th>Labelled</th><th>Re-skins</th>'
                      '<th>Labels</th><th>Pairs it stands for</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></div>')
        if cards:
            audit_html += f'<h3>Re-skins the audit found</h3><div class="pairs">{cards}</div>'
    rerun = ""
    if ra:
        ca = ra["cascade"]
        b = next(x for x in ca["agent"] if x["recall_target"] == 0.95)
        rerun = ("<p>The audit's re-skins are harder than the seed search's: none of them was found "
                 "by part 2. Retrained with them added as positives "
                 f"({ca['positives']} same-length, {ca['medley']} medleys): the metadata screen keeps "
                 f"{fmt(ca['m']['pairs_kept'])} pairs, the thumbnail screen {fmt(ca['i']['pairs_kept'])}, "
                 f"and the agent reviews {fmt(b['pairs_reviewed'])} pairs ({fmt(b['sheets'])} sheets) "
                 "for 95%. The highest cut-offs are set by a handful of unusual re-skins, so each one "
                 "found moves them a lot.</p>")

    tree = escape(r["tree_M"])
    imp = "".join(f"<li><code>{escape(x['feature'])}</code> {x['coef']:+.2f}</li>"
                  for x in r["importance"]["M"][:6])
    tr = next(x for x in nar["signals"] if x["signal"] == "title_words" and x["recall_target"] == 1.0)
    html = string.Template(TEMPLATE).substitute(
        funnel=funnel, tiers=tiers_html, agent_rows=agent_rows, look_rows=look_rows, lost=lost_cards,
        nar_rows=nar_rows, cost_rows=cost_rows, audit=audit_html, rerun=rerun, tree=tree, imp=imp,
        pairs=fmt(r["pairs"]), videos=fmt(r["videos"]), pos=c["positives"], med=c["medley"],
        m_kept=fmt(c["m"]["pairs_kept"]), m_share=pct(c["m"]["pairs_kept"] / r["pairs"], 2),
        m_videos=fmt(c["m"]["videos_needing_images"]), m_pos=c["m"]["positives_kept"],
        i_kept=fmt(c["i"]["pairs_kept"]), i_share=pct(c["i"]["pairs_kept"] / r["pairs"], 2),
        i_pos=c["i"]["positives_kept"], i_videos=fmt(c["i"]["videos_needing_gate_frames"]),
        a_pairs=fmt(a95["pairs_reviewed"]), a_sheets=fmt(a95["sheets"]), a_found=a95["same_length_found"],
        a_dl=a95["download_videos"], p2_cand=fmt(p2["candidates"]), p2_lab=fmt(p2["labelled"]),
        p2_sheets=fmt(p2["sheets"]), p2_dl=fmt(p2["download_videos"]),
        title_pairs=fmt(tr["pairs_within"]), title_nb=f"{tr['neighbours_per_video']:.0f}",
        at=r["at"][:10])
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / "report.html"
    out.write_text(html)
    return out


TEMPLATE_PATH = HERE / "learn_report.html"
TEMPLATE = TEMPLATE_PATH.read_text() if TEMPLATE_PATH.exists() else ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("features")
    fp = sub.add_parser("fit")
    fp.add_argument("--with-audit", action="store_true")
    au = sub.add_parser("audit")
    au.add_argument("what", choices=("sample", "next", "check", "results"))
    au.add_argument("file", nargs="?", type=Path)
    au.add_argument("--n", type=int, default=10)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "features":
        build_features()
    elif a.cmd == "fit":
        fit(a.with_audit)
    elif a.cmd == "report":
        print(build_report())
    elif a.what == "sample":
        audit_sample()
    elif a.what == "next":
        audit_next(a.n)
    elif a.what == "check":
        import review

        review.check(a.file)
    else:
        r = audit_results()
        (OUT / "audit" / "results.json").write_text(json.dumps(r, indent=1))
        print(json.dumps({k: {x: v[x] for x in ("labelled", "re_skins", "rate_ci", "population")}
                          for k, v in r.items()}, indent=1))


if __name__ == "__main__":
    main()
