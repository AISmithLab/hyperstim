import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_pair as sp  # noqa: E402


def test_r_rounds_nested_results():
    x = {"a": 1.234567, "b": [np.float32(0.5), np.int64(3), float("nan")], "c": np.array([1.23456, 2.0]),
         "d": ("x", None, True)}
    assert sp.r(x) == {"a": 1.2346, "b": [0.5, 3, None], "c": [1.2346, 2.0], "d": ["x", None, True]}
    json.dumps(sp.r(x))


def test_sprite(tmp_path):
    frames = [np.full((4, 6, 3), 40 * k, np.uint8) for k in range(5)]
    out = tmp_path / "s" / "a.jpg"
    meta = sp.sprite(frames, 2, out)
    assert meta == {"file": "a.jpg", "cols": 2, "rows": 3, "w": 6, "h": 4, "n": 5}
    sheet = cv2.imread(str(out))
    assert sheet.shape == (12, 12, 3)
    assert abs(int(sheet[5, 8, 0]) - 120) <= 3 and int(sheet[10, 8].max()) <= 3  # tile 3; empty slot


def test_edge_overlay():
    ga = np.zeros((40, 40), np.uint8)
    ga[:, 20:] = 255
    gb = ga.T.copy()
    out = sp.edge_overlay(ga, gb)
    assert out.shape == (40, 40, 3)
    assert tuple(out[5, 20]) == (255, 80, 200) and tuple(out[20, 5]) == (60, 220, 120)
    assert tuple(out[20, 20]) == (255, 255, 255) and tuple(out[5, 5]) == (18, 18, 18)


def test_features(tmp_path):
    p = tmp_path / "f.tsv"
    cols = sp.bl.FEATURES
    values = ["1.5"] + [""] * (len(cols) - 1)
    p.write_text("video_id\t" + "\t".join(cols) + "\nabc\t" + "\t".join(values) + "\n")
    f = sp.features(p)
    assert f["abc"][cols[0]] == 1.5 and math.isnan(f["abc"][cols[1]])


def test_loudness():
    y = np.concatenate([np.full(2205, 0.5), np.full(2205, 1.0), np.zeros(100)]).astype(np.float32)
    assert sp.loudness(y).tolist() == [-6.0, 0.0]


def test_video_info():
    item = {"snippet": {"title": "T", "channelTitle": "C", "channelId": "UC1", "publishedAt": "2014",
                        "description": "D"}}
    channel = {"snippet": {"publishedAt": "2010"}, "statistics": {"subscriberCount": "12", "viewCount": "5"}}
    v = sp.video_info(item, channel, 61.5, {"viewCount": 1})
    assert v == {"title": "T", "channel": "C", "channel_id": "UC1", "published": "2014", "duration_s": 61.5,
                 "tags": [], "description": "D", "stats": {"viewCount": 1}, "channel_created": "2010",
                 "channel_subscribers": 12, "channel_videos": 0, "channel_views": 5, "channel_country": None}


def test_channel_info_reuses_saved_responses(tmp_path, monkeypatch):
    api = tmp_path / "cache" / "api"
    api.mkdir(parents=True)
    (api / "channels-UCa_UCb.json").write_text(json.dumps({"items": [{"id": "UCa"}, {"id": "UCb"}]}))
    (api / "channelSections-UCa.json").write_text(json.dumps(
        {"items": [{"contentDetails": {"channels": ["UCb", "UCx"]}}, {"snippet": {}}]}))
    monkeypatch.setattr(sp, "ROOT", tmp_path)
    calls = []

    def fake_api(endpoint, params, experiment, note):
        calls.append((endpoint, params))
        return {"items": []}

    monkeypatch.setattr(sp.yt, "api", fake_api)
    by_id, featured = sp.channel_info("UCb", "UCa")
    assert set(by_id) == {"UCa", "UCb"}
    assert featured == {"UCa": {"UCb", "UCx"}, "UCb": set()}
    assert calls == [("channelSections", {"channelId": "UCb", "part": "snippet,contentDetails"})]
    assert sp.legacy("missing.json") is None


def test_results_hold_no_local_paths_or_frames():
    """Results are committed to a public repo: numbers, IDs and public metadata only."""
    for p in (sp.HERE / "results").glob("*.json"):
        text = p.read_text()
        assert "/home/" not in text and "cache/" not in text and "data:image" not in text, p.name
