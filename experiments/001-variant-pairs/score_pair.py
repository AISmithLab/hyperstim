"""Score one pair of videos on every signal of the framework (PLAN.md, Signal framework).

    uv run python 001-variant-pairs/score_pair.py pRPe05YfXxg AJ1vEJXC0-M --name seed-pair

Writes 001-variant-pairs/results/<name>.json (numbers, IDs and public metadata only) and the
report's frame sprites to cache/report/<name>/ (stills from the downloads: never committed).
Needs both videos downloaded (tools/yt.py download) and their pipeline features in
cache/features/ (PLAN.md, Results: Framework built).
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import overlap  # noqa: E402

import align  # noqa: E402
import audio  # noqa: E402
import baselines as bl  # noqa: E402
import changes as chg  # noqa: E402
import media  # noqa: E402
import metadata as md  # noqa: E402
import visual as vis  # noqa: E402
import yt  # noqa: E402

EXP = "001"
SMALL = (160, 90)     # motion, cuts
MID = (320, 180)      # structure, change maps
SPRITE = (384, 216)   # report stills
SAMPLE_RATE = 2.0     # aligned frame pairs a second


def legacy(name: str) -> dict | None:
    """API responses saved before tools/yt.py existed (owner probe): reuse, never re-fetch."""
    p = ROOT / "cache" / "api" / name
    return json.loads(p.read_text()) if p.exists() else None


def channel_info(ch_a: str, ch_b: str) -> tuple[dict, dict]:
    ids = ",".join(sorted({ch_a, ch_b}))
    chans = legacy(f"channels-{'_'.join(sorted({ch_a, ch_b}))}.json") or yt.api(
        "channels", {"id": ids, "part": "snippet,statistics,brandingSettings"}, EXP, "owner signal")
    by_id = {c["id"]: c for c in chans["items"]}
    featured = {}
    for c in (ch_a, ch_b):
        sec = legacy(f"channelSections-{c}.json") or yt.api(
            "channelSections", {"channelId": c, "part": "snippet,contentDetails"}, EXP, "owner signal")
        featured[c] = {x for s in sec["items"] for x in s.get("contentDetails", {}).get("channels", [])}
    return by_id, featured


def features(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="") as f:
        return {r["video_id"]: {k: float(r[k]) if r[k] not in ("", None) else float("nan")
                                for k in bl.FEATURES} for r in csv.DictReader(f, delimiter="\t")}


def sprite(frames: list[np.ndarray], cols: int, out: Path) -> dict:
    h, w = frames[0].shape[:2]
    rows = -(-len(frames) // cols)
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, fr in enumerate(frames):
        r, c = divmod(k, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = fr
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 78])
    return {"file": out.name, "cols": cols, "rows": rows, "w": w, "h": h, "n": len(frames)}


def edge_overlay(ga: np.ndarray, gb: np.ndarray) -> np.ndarray:
    """A's edges in one channel, B's in another: shared edges show white."""
    ea = cv2.dilate(cv2.Canny(ga, 60, 140), np.ones((2, 2), np.uint8)) > 0
    eb = cv2.dilate(cv2.Canny(gb, 60, 140), np.ones((2, 2), np.uint8)) > 0
    out = np.full(ga.shape + (3,), 18, np.uint8)
    out[ea] = (255, 80, 200)
    out[eb] = (60, 220, 120)
    out[ea & eb] = (255, 255, 255)
    return out


def r(x, n=4):
    """Round floats in nested results for a compact JSON."""
    if isinstance(x, float):
        return None if np.isnan(x) else round(x, n)
    if isinstance(x, (np.floating, np.integer)):
        return r(x.item(), n)
    if isinstance(x, np.ndarray):
        return r(x.tolist(), n)
    if isinstance(x, dict):
        return {k: r(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r(v, n) for v in x]
    return x


def loudness(y: np.ndarray) -> np.ndarray:
    """Loudness per 0.1 s (dBFS, RMS) of samples at align.SR."""
    return (20 * np.log10(np.sqrt(np.mean(y[: len(y) // 2205 * 2205].reshape(-1, 2205) ** 2, axis=1))
                          + 1e-6)).round(1)


def video_info(item: dict, channel: dict, duration_s: float, stats: dict) -> dict:
    """A video's public metadata and its channel's, for the results JSON."""
    sn, ch_stats = item["snippet"], channel["statistics"]
    return {"title": sn["title"], "channel": sn["channelTitle"], "channel_id": sn["channelId"],
            "published": sn["publishedAt"], "duration_s": duration_s, "tags": sn.get("tags", []),
            "description": sn["description"], "stats": stats,
            "channel_created": channel["snippet"]["publishedAt"],
            "channel_subscribers": int(ch_stats.get("subscriberCount", 0)),
            "channel_videos": int(ch_stats.get("videoCount", 0)),
            "channel_views": int(ch_stats.get("viewCount", 0)),
            "channel_country": channel["snippet"].get("country")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--name", required=True)
    ap.add_argument("--all-signals", action="store_true",
                    help="run every signal, also those the signal order would skip (checks the order)")
    ap.add_argument("--features", type=Path, default=ROOT / "cache/features",
                    help="folder with features.tsv and features-shared.tsv (prepare_pair.py)")
    args = ap.parse_args()
    va, vb = args.a, args.b
    out_dir = ROOT / "cache" / "report" / args.name
    derived = ROOT / "cache" / "derived"

    # --- Metadata ----------------------------------------------------------------------
    rows = bl.load_dataset()
    snip_pair = bl.snippets([va, vb], EXP, f"{args.name}: pair")
    sa, sb = snip_pair[va], snip_pair[vb]
    ch_a, ch_b = sa["snippet"]["channelId"], sb["snippet"]["channelId"]
    chans, featured = channel_info(ch_a, ch_b)
    title = md.title_signal(sa["snippet"]["title"], sb["snippet"]["title"])
    song = title["song"].split()
    print("song:", title["song"])

    exclude = {ch_a, ch_b}
    pair_titles = [sa["snippet"]["title"], sb["snippet"]["title"]]
    subject, subject_how = bl.subject_videos(rows, song, exclude, pair_titles)
    print(f"same subject: {len(subject)} videos ({subject_how})")
    sets = bl.sample_sets(rows, song, exclude, subject=subject)
    sample_ids = sorted({v for s in sets.values() for v in s})
    snips = bl.snippets(sample_ids, EXP, f"{args.name}: baseline sample")
    pair_ev = md.owner_evidence(sa["snippet"]["description"] + "\n" + sb["snippet"]["description"])
    same_owner = set()
    for v, s in snips.items():
        ev = md.owner_evidence(s["snippet"].get("description", ""))
        if (ev["copyright"] & pair_ev["copyright"]) or (ev["app"] & pair_ev["app"]):
            same_owner.add(v)
    same_owner_channels = {snips[v]["snippet"]["channelId"] for v in same_owner}
    print(f"baseline sample: {len(snips)} videos; {len(same_owner)} share the pair's owner")

    owner = md.owner_signal(
        [sa["snippet"]["description"], chans[ch_a]["snippet"].get("description", "")],
        [sb["snippet"]["description"], chans[ch_b]["snippet"].get("description", "")],
        featured[ch_a], featured[ch_b], ch_a, ch_b)

    timing = md.timing_signal(sa["snippet"]["publishedAt"], sb["snippet"]["publishedAt"])
    dur_a_api = md.iso_duration(sa["contentDetails"]["duration"])
    dur_b_api = md.iso_duration(sb["contentDetails"]["duration"])
    duration = md.duration_signal(dur_a_api, dur_b_api)
    text = md.text_signal(sa["snippet"]["description"], sb["snippet"]["description"],
                          sa["snippet"].get("tags", []), sb["snippet"].get("tags", []))

    big = bl.dataset_pairs(rows, song, exclude, same_owner_channels, subject=subject)
    small = bl.pairs_for(sets, rows, (va, vb), same_owner)
    meta_of = lambda v: rows.get(v) or {  # noqa: E731
        "title": snip_pair[v]["snippet"]["title"], "published_at": snip_pair[v]["snippet"]["publishedAt"],
        "duration_s": md.iso_duration(snip_pair[v]["contentDetails"]["duration"])}
    for v in (va, vb):
        rows.setdefault(v, {**meta_of(v), "channel_id": snip_pair[v]["snippet"]["channelId"]})
    # The dataset has publish dates only: time of day comes from the sample's snippets.
    base_title, base_days, base_dur = ({k: [] for k in big} for _ in range(3))
    for k, ps in big.items():
        for x, y in ps:
            t = md.title_signal(rows[x]["title"], rows[y]["title"])
            base_title[k].append(t["jaccard"])
            base_days[k].append(md.timing_signal(rows[x]["published_at"], rows[y]["published_at"])["days"])
            base_dur[k].append(abs(float(rows[x]["duration_s"]) - float(rows[y]["duration_s"])))
    snips_all = {**snips, **snip_pair}
    base_desc, base_lines, base_tags, base_tod = ({k: [] for k in small} for _ in range(4))
    for k, ps in small.items():
        for x, y in ps:
            if x not in snips_all or y not in snips_all:
                continue
            a_, b_ = snips_all[x]["snippet"], snips_all[y]["snippet"]
            t = md.text_signal(a_.get("description", ""), b_.get("description", ""),
                               a_.get("tags", []), b_.get("tags", []))
            base_desc[k].append(t["description_words"])
            base_lines[k].append(t["description_lines"])
            base_tags[k].append(t["tags"])
            base_tod[k].append(md.timing_signal(a_["publishedAt"], b_["publishedAt"])["time_of_day_h"])

    # --- Thumbnails --------------------------------------------------------------------
    thumbs = {}
    for v in [va, vb] + sample_ids:
        p = bl.thumbnail(v, EXP, f"{args.name}: thumbnail")
        if p:
            thumbs[v] = vis.load_image(p)
    tid = list(thumbs)
    temb = dict(zip(tid, vis.embed([thumbs[v] for v in tid], size=(224, 224)), strict=True))
    thumb = vis.thumbnail_similarity(thumbs[va], thumbs[vb], temb[va], temb[vb])
    base_th_emb, base_th_hash = {k: [] for k in small}, {k: [] for k in small}
    for k, ps in small.items():
        for x, y in ps:
            if x in thumbs and y in thumbs:
                s = vis.thumbnail_similarity(thumbs[x], thumbs[y], temb[x], temb[y])
                base_th_emb[k].append(s["embedding"])
                base_th_hash[k].append(s["hash"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for v, name in ((va, "thumb-a.jpg"), (vb, "thumb-b.jpg")):
        cv2.imwrite(str(out_dir / name), cv2.cvtColor(thumbs[v], cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])

    # --- Downloads: alignment ----------------------------------------------------------
    pa, pb = yt.download(va, EXP), yt.download(vb, EXP)
    ya, yb = media.audio(pa), media.audio(pb)
    dur_a, dur_b = len(ya) / align.SR, len(yb) / align.SR
    # By the audio, or by the frames when the audio covers under half (e.g. new audio).
    al = overlap.align_pair(pa, pb, ya, yb)
    segs, acurves, align_source = al["segs"], al["curves"], al["source"]
    assert segs, "no alignment from audio or frames"
    speed = align.speed_ratio(ya, yb, segs[0])
    parts = chg.only_parts(segs, dur_a, dur_b)
    print("segments:", segs)

    # --- Storyboards -------------------------------------------------------------------
    sbs = {}
    for v, p in ((va, pa), (vb, pb)):
        fmt = vis.storyboard_format(yt.info(v))
        sprites = [vis.load_image(yt.image(f["url"], EXP, "storyboard", v, f"{args.name}: storyboard"))
                   for f in fmt["fragments"]]
        sbs[v] = vis.storyboard_frames(fmt, sprites, media.probe(p)["duration"])
    story = vis.storyboard_signal(*sbs[va], *sbs[vb], audio_lag=segs[0].lag)

    # --- Audio -------------------------------------------------------------------------
    # Signal order: stem separation (the costliest step) decides only "same backing, different
    # overlay", so it runs only when the waveforms don't already settle a closer level.
    au = audio.analyze(ya, yb, segs, None, None, speed)
    if au["level"] in ("exact", "adjusted") and not args.all_signals:
        au["stems_skipped"] = True
        au["settled_by"] = f"waveform match, r {au['waveform_corr']:.3f}"
    else:
        level_without = au["level"]
        stems_a, stems_b = audio.stems(pa, derived), audio.stems(pb, derived)
        au = audio.analyze(ya, yb, segs, stems_a, stems_b, speed)
        au["stems_skipped"] = False
        # The order check (every 10th pair runs every signal): would skipping have changed the level?
        if level_without in ("exact", "adjusted"):
            au["order_check"] = {"level_without_stems": level_without, "same": level_without == au["level"]}
    print("audio level:", au["level"], "(stems skipped)" if au["stems_skipped"] else "")

    # --- Frames ------------------------------------------------------------------------
    fps = media.probe(pa)["fps"]
    # Different frame rates: B is decoded at A's, so frame indices share one clock.
    fps_b = None if abs(media.probe(pb)["fps"] - fps) < 1e-6 else fps
    gsa, gsb = media.frames(pa, SMALL, gray=True), media.frames(pb, SMALL, fps=fps_b, gray=True)
    # The larger frames are read only where they're sampled below (aligned pairs, their time-shift
    # baselines, one a second for the sprites): all of them would be gigabytes for a long video.
    # Decoding can give a frame or two less than the audio's length, so sample A's frames only.
    dur_frames = min(dur_a, (len(gsa) - 0.5) / fps)
    pairs = vis.sample_pairs(segs, dur_frames, fps, len(gsb), SAMPLE_RATE)
    null_pairs = [vis.sample_pairs(segs, dur_frames, fps, len(gsb), SAMPLE_RATE / 2, shift=s)
                  for s in vis.shifts(8)]
    sec = np.arange(0, int(dur_a))
    sec_i = [min(round(t * fps), len(gsa) - 1) for t in sec]
    sec_tb = [align.map_time(segs, float(t)) for t in sec]
    sec_j = [None if tb is None or round(tb * fps) >= len(gsb) else round(tb * fps) for tb in sec_tb]
    keep_a = {i for ps in [pairs, *null_pairs] for _, i, _ in ps} | set(sec_i)
    keep_b = {j for ps in [pairs, *null_pairs] for _, _, j in ps} | {j for j in sec_j if j is not None}
    gma = media.frames_at(pa, MID, keep_a, gray=True)
    gmb = media.frames_at(pb, MID, keep_b, fps=fps_b, gray=True)
    cma, cmb = media.frames_at(pa, MID, keep_a), media.frames_at(pb, MID, keep_b, fps=fps_b)

    da, db = vis.frame_diff(gsa), vis.frame_diff(gsb)
    cuts_a, cuts_b = vis.cuts(da, fps), vis.cuts(db, fps)
    cut_share, n_cuts = vis.cut_match(cuts_a, cuts_b, segs, fps)
    segs_b = [align.Segment(s.a0 + s.lag, s.a1 + s.lag, -s.lag, s.score) for s in segs]
    cut_share_b, _ = vis.cut_match(cuts_b, cuts_a, segs_b, fps)
    cut_null = [vis.cut_match(cuts_a, cuts_b, segs, fps, s)[0] for s in vis.shifts(40)]

    flow_a, flow_b = vis.flow_curves(gsa), vis.flow_curves(gsb)
    motion = {k: vis.curve_corr(flow_a[k], flow_b[k], segs, fps) for k in flow_a}
    motion_null = {k: [vis.curve_corr(flow_a[k], flow_b[k], segs, fps, s) for s in vis.shifts(30)]
                   for k in flow_a}

    st = vis.structure(gma, gmb, pairs)
    st_null = {"gray_ssim": [], "edge_ssim": []}
    for sp in null_pairs:
        x = vis.structure(gma, gmb, sp)
        for k in st_null:
            st_null[k] += [v for v in x[k] if not np.isnan(v)]

    ia = [i for _, i, _ in pairs]
    ib = [j for _, _, j in pairs]
    ea, eb = vis.embed(cma[ia]), vis.embed(cmb[ib])
    content = np.sum(ea * eb, axis=1)
    content_null = []
    for sp in null_pairs:
        x, y = vis.embed(cma[[i for _, i, _ in sp]]), vis.embed(cmb[[j for _, _, j in sp]])
        content_null += np.sum(x * y, axis=1).tolist()

    # --- What changed ------------------------------------------------------------------
    chs = [chg.pair_change(cma[i], cmb[j], chg.moving_mask(gsa, i, MID)) for _, i, j in pairs]
    area = chg.area_summary(chs)
    color = chg.color_summary([cma[i] for i in ia], [cmb[j] for j in ib])

    # A clip the pipeline couldn't measure (e.g. a shared part under its minimum length, when the
    # versions barely align) has no row: its features are NaN.
    missing = dict.fromkeys(bl.FEATURES, float("nan"))
    fa = {v: features(args.features / "features.tsv").get(v, missing) for v in (va, vb)}
    shared_path = args.features / "features-shared.tsv"
    fs = {v: (features(shared_path) if shared_path.exists() else {}).get(v, missing) for v in (va, vb)}
    feat = {"dataset_clip": {"a": fa[va], "b": fa[vb]}, "shared_part": {"a": fs[va], "b": fs[vb]}}
    base_feat = {}
    for f in bl.FEATURES:
        vals = {k: [] for k in big}
        for k, ps in big.items():
            for x, y in ps:
                with contextlib.suppress(ValueError, KeyError):
                    vals[k].append(abs(float(rows[x][f]) - float(rows[y][f])))
        base_feat[f] = vals
    # Dataset spread per feature, so the report can show where each version sits.
    feat_dist = {}
    for f in bl.FEATURES:
        v = np.array([float(x[f]) for x in rows.values() if x.get(f) not in ("", None)])
        feat_dist[f] = {"p5": float(np.percentile(v, 5)), "p50": float(np.median(v)),
                        "p95": float(np.percentile(v, 95)),
                        "a_pct": float(np.mean(v < fs[va][f])), "b_pct": float(np.mean(v < fs[vb][f]))}

    stats = {v: {k: int(snip_pair[v]["statistics"].get(k, 0))
                 for k in ("viewCount", "likeCount", "commentCount")}
             for v in (va, vb)}

    # --- Sprites for the report (A's timeline, 1 still a second) ------------------------
    sa_f, sb_f, mask_f, edge_f, has_b = [], [], [], [], []
    blank = np.full((SPRITE[1], SPRITE[0], 3), 30, np.uint8)
    for i, j in zip(sec_i, sec_j, strict=True):
        sa_f.append(cv2.resize(cma[i], SPRITE, interpolation=cv2.INTER_AREA))
        if j is None:
            has_b.append(False)
            sb_f.append(blank)
            mask_f.append(blank)
            edge_f.append(blank)
            continue
        has_b.append(True)
        sb_f.append(cv2.resize(cmb[j], SPRITE, interpolation=cv2.INTER_AREA))
        ch = chg.pair_change(cma[i], cmb[j], chg.moving_mask(gsa, i, MID))
        mask_f.append(cv2.resize(chg.mask_image(cma[i], ch), SPRITE, interpolation=cv2.INTER_AREA))
        edge_f.append(cv2.resize(edge_overlay(gma[i], gmb[j]), SPRITE, interpolation=cv2.INTER_NEAREST))
    sprites = {name: sprite(fr, 12, out_dir / f"{name}.jpg")
               for name, fr in (("a", sa_f), ("b", sb_f), ("mask", mask_f), ("edges", edge_f))}
    # Storyboard strips, for the cheap-signal section.
    for v, name in ((va, "sb-a"), (vb, "sb-b")):
        sprites[name] = sprite([cv2.resize(f, (160, 90), interpolation=cv2.INTER_AREA) for f in sbs[v][1]],
                               25, out_dir / f"{name}.jpg")
        sprites[name]["times"] = sbs[v][0].tolist()

    # --- Signals with baselines --------------------------------------------------------
    T = bl.threshold
    # Storyboard offsets ≥ 3 s from its best one: the storyboard's time-shift baseline.
    story_null = [s for s, lag in zip(story["offsets"]["scores"], story["offsets"]["lags"], strict=True)
                  if abs(lag - story["lag"]) >= 3 and s is not None and not np.isnan(s)]
    sig = {
        "metadata": {
            "owner": {"value": owner["strongest"], "fires": owner["same_owner"], "detail": owner},
            "timing_days": {**T(base_days, False, timing["days"]), "detail": timing},
            "timing_time_of_day": T(base_tod, False, timing["time_of_day_h"]),
            "title": {**T(base_title, True, title["jaccard"]), "detail": title},
            "description": {**T(base_desc, True, text["description_words"]), "detail": text},
            "description_lines": T(base_lines, True, text["description_lines"]),
            "tags": T(base_tags, True, text["tags"]),
            "duration": {**T(base_dur, False, duration["diff_s"]),
                         "detail": {**duration, "a": dur_a_api, "b": dur_b_api}},
        },
        "visual": {
            "thumbnail_embedding": T(base_th_emb, True, thumb["embedding"]),
            "thumbnail_hash": T(base_th_hash, True, thumb["hash"]),
            "storyboard": {**T({"time_shift": story_null}, True, story["embedding"]),
                           "detail": {k: v for k, v in story.items() if k != "sequence"}},
            "aligned_cuts": {**T({"time_shift": cut_null}, True, cut_share),
                             "detail": {"n_cuts_a": len(cuts_a), "n_cuts_b": len(cuts_b),
                                        "n_in_matched": n_cuts, "share_b": cut_share_b,
                                        "cuts_a": (cuts_a / fps).tolist(),
                                        "cuts_b": (cuts_b / fps).tolist()}},
            "motion_camera_x": T({"time_shift": motion_null["dx"]}, True, motion["dx"]),
            "motion_camera_y": T({"time_shift": motion_null["dy"]}, True, motion["dy"]),
            "motion_magnitude": T({"time_shift": motion_null["magnitude"]}, True, motion["magnitude"]),
            "motion_objects": T({"time_shift": motion_null["object"]}, True, motion["object"]),
            "structure_gray": T({"time_shift": st_null["gray_ssim"]}, True,
                                float(np.nanmedian(st["gray_ssim"]))),
            "structure_edges": T({"time_shift": st_null["edge_ssim"]}, True,
                                 float(np.nanmedian(st["edge_ssim"]))),
            "frame_content": T({"time_shift": content_null}, True, float(np.median(content))),
        },
        "audio": au | {"curves": None},
        "changes": {
            "color": color | {"delta_e_curve": None},
            "area": {k: v for k, v in area.items() if not k.endswith("_curve")},
            "parts": parts,
            "features": feat,
            "features_baseline": {f: T(base_feat[f], False, abs(fs[va][f] - fs[vb][f])) for f in bl.FEATURES},
            "features_dataset": feat_dist,
            "audience": stats,
        },
    }
    for v in sig["changes"]["features_baseline"].values():
        v["per_set"] = {s: {kk: vv for kk, vv in p.items() if kk != "hist"} for s, p in v["per_set"].items()}

    curves = {
        "audio": {k: v for k, v in au["curves"].items()},
        "align": {"times": acurves["times"], "score": acurves["score"], "threshold": acurves["threshold"]},
        "frames": {"times": [t for t, _, _ in pairs], "gray_ssim": st["gray_ssim"],
                   "edge_ssim": st["edge_ssim"],
                   "content": content, "delta_e": color["delta_e_curve"], "changed": area["changed_curve"],
                   "recolored": area["recolored_curve"], "reshaped": area["reshaped_curve"]},
        "motion": {"fps": 5, "a": {k: v[::int(fps / 5)] for k, v in flow_a.items()},
                   "b": {k: v[::int(fps / 5)] for k, v in flow_b.items()}},
        "storyboard": story["sequence"],
        # Loudness per 0.1 s (dBFS, RMS), each on its own clock; the report shifts B onto A's.
        "loudness": {"rate": 10, **{k: loudness(y) for k, y in (("a", ya), ("b", yb))}},
    }
    result = {
        "name": args.name, "pair": {"a": va, "b": vb},
        "videos": {v: video_info(snip_pair[v], chans[snip_pair[v]["snippet"]["channelId"]], len(y) / align.SR,
                                 stats[v])
                   for v, y in ((va, ya), (vb, yb))},
        "alignment": {"segments": [s.__dict__ for s in segs], "speed": speed, "lag": segs[0].lag,
                      "source": align_source, "audio_share": al["audio_share"],
                      "frame_share": al["frame_share"], "share": al["share"]},
        "signals": sig, "curves": curves, "sprites": sprites, "has_b": has_b,
        "baseline_sizes": {"sample_videos": len(snips), "subject_how": subject_how,
                           "subject_videos": len(subject), "same_owner_left_out": sorted(same_owner),
                           "dataset_pairs": {k: len(v) for k, v in big.items()},
                           "sample_pairs": {k: len(v) for k, v in small.items()}},
    }
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{args.name}.json").write_text(json.dumps(r(result), ensure_ascii=False, indent=1))
    print("wrote", HERE / "results" / f"{args.name}.json")


if __name__ == "__main__":
    main()
