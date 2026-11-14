import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_report  # noqa: E402
import build_search_site as site  # noqa: E402


def data(song="five little ducks", title_a="Five Little Ducks | Kids TV", same_channel=False):
    return {"pair": {"a": "AAA", "b": "BBB"},
            "videos": {"AAA": {"title": title_a, "channel_id": "C1", "description": "x"},
                       "BBB": {"title": "b", "channel_id": "C1" if same_channel else "C2"}},
            "signals": {"metadata": {"title": {"detail": {"song": song}}}},
            "sprites": {"mask": {"file": "mask.jpg"}, "a": {"file": "a.jpg"}}}


def test_ok_reports_takes_each_names_latest_state(tmp_path):
    log = tmp_path / "reports.tsv"
    log.write_text("at\tname\tstate\n1\tx\tstart\n2\ty\tstart\n3\tx\tok\n4\ty\tfailed\n5\tz\tok\n6\tz\tstart\n")
    assert site.ok_reports(log) == ["x"]
    assert site.ok_reports(tmp_path / "missing.tsv") == []


def test_token_keeps_safe_names_and_replaces_the_rest():
    assert site.token("AxB-pRPe05YfXxg-AJ1vEJXC0-M") == "AxB-pRPe05YfXxg-AJ1vEJXC0-M"
    assert site.token("a b/c") == "a~b~c"


def test_short_title_prefers_the_song_then_a_title():
    assert site.short_title(data()) == "Five Little Ducks"
    assert site.short_title(data(song="")) == "Five Little Ducks"
    long = data(song="", title_a="A very long title that keeps going and going | Kids TV")
    assert site.short_title(long).endswith("…") and len(site.short_title(long)) <= 26


def test_pair_type_from_name_or_channels():
    assert site.pair_type("BxB-x-y", data()) == "BxB"
    assert site.pair_type("other", data(same_channel=True)) == "AxA"
    assert site.pair_type("other", data()) == "AxB"


def test_write_pair_site_mode_packs_stills(tmp_path):
    import cv2

    src = tmp_path / "src"
    src.mkdir()
    cv2.imwrite(str(src / "mask.jpg"), np.full((180, 320, 3), 128, np.uint8))   # 2 x 2 tiles of 160 x 90
    cv2.imwrite(str(src / "a.jpg"), np.full((90, 160, 3), 128, np.uint8))
    cv2.imwrite(str(src / "thumb-a.jpg"), np.full((90, 160, 3), 128, np.uint8))
    out = tmp_path / "out"
    out.mkdir()
    (out / "old.jpg").write_text("x")   # an earlier layout's file goes
    (out / "a.mp4").write_text("v")     # a copied video stays
    d = data()
    d["sprites"] = {"mask": {"file": "mask.jpg", "cols": 2, "rows": 2, "w": 160, "h": 90},
                    "a": {"file": "a.jpg", "cols": 1, "rows": 1, "w": 160, "h": 90},
                    "edges": {"file": "edges.jpg", "cols": 1, "rows": 1, "w": 1, "h": 1}}  # missing file
    files = build_report.write_pair("AxB-x-y", d, out, site=True, quality=60, scale=0.5, stills_from=src,
                                    frames=False)
    assert files == ["index.html", "data.json", "stills.jpg"]
    assert sorted(f.name for f in out.iterdir()) == ["a.mp4", "data.json", "index.html", "stills.jpg"]
    page = (out / "index.html").read_text()
    assert page.startswith("<!doctype html>") and 'data-src="data.json"' in page
    assert 'data-videos="../../videos.json"' in page and 'data-name="AxB-x-y"' in page
    assert ">null</script>" in page
    shown = json.loads((out / "data.json").read_text())
    assert shown["thumbs"]["a"].startswith("data:image/jpeg;base64,") and "b" not in shown["thumbs"]
    assert set(shown["sprites"]) == {"mask"}  # A/B stills only without a video; missing files dropped
    m = shown["sprites"]["mask"]
    assert (m["sheet"], m["x"], m["y"], m["W"], m["H"]) == ("stills.jpg", 0, 0, 160, 90)
    assert (m["w"], m["h"]) == (80, 45)
    assert d["sprites"]["mask"].get("sheet") is None    # the caller's data is left alone

    build_report.write_pair("AxB-x-y", d, out, site=True, quality=60, scale=1, stills_from=src, frames=True)
    shown = json.loads((out / "data.json").read_text())
    assert shown["sprites"]["a"]["sheet"] == "frames.jpg" and (out / "frames.jpg").exists()


def test_strips_keep_their_slots(tmp_path, monkeypatch):
    import build_search_report as bsr

    monkeypatch.setattr(bsr, "strip_image", lambda a, b: np.zeros((90, 1286, 3), np.uint8))
    st = bsr.Strips(tmp_path)
    css = [st.css(f"v{i:010d}", "w_-") for i in range(27)]
    assert "sheet-00.jpg" in css[0] and "0 0.0000%" in css[0] and "100.0000%" in css[24]
    assert "sheet-01.jpg" in css[25]
    (tmp_path / "strips").mkdir()
    (tmp_path / "strips" / "old_strip.jpg").write_text("x")
    st.save()
    assert sorted(f.name for f in (tmp_path / "strips").iterdir()) == ["sheet-00.jpg", "sheet-01.jpg"]
    t0 = (tmp_path / "strips" / "sheet-00.jpg").stat().st_mtime_ns
    st2 = bsr.Strips(tmp_path)
    assert st2.css("v0000000003", "w_-") == css[3]       # same slot after a reload
    st2.css("new", "pair")                               # lands in sheet 1: sheet 0 isn't rewritten
    st2.save()
    assert (tmp_path / "strips" / "sheet-00.jpg").stat().st_mtime_ns == t0


def test_standalone_shell_inlines_data():
    page = build_report.shell({"pair": {"a": "</script>"}})
    assert not page.startswith("<!doctype") and "<\\/script>" in page and "__DATA__" not in page


def test_strips_take_a_drawing_function(tmp_path):
    import build_search_report as bsr

    st = bsr.Strips(tmp_path, make=lambda v: np.zeros((90, 640, 3), np.uint8))
    assert "sheet-00.jpg" in st.css("vid")
    st.save()
    import cv2

    assert cv2.imread(str(tmp_path / "strips" / "sheet-00.jpg")).shape == (90 * 25, 640, 3)


def test_asset_videos_need_both_videos():
    out = site.asset_videos(["AxA-aaaaaaaaaaa-bbbbbbbbbbb", "AxA-aaaaaaaaaaa-ccccccccccc"],
                            {"aaaaaaaaaaa": "/_blob/1", "bbbbbbbbbbb": "/_blob/2"})
    assert out["AxA-aaaaaaaaaaa-bbbbbbbbbbb"] == {"a": "/_blob/1", "b": "/_blob/2"}
    assert out["AxA-aaaaaaaaaaa-ccccccccccc"] == {"a": None, "b": None}


def test_group_reports_keep_built_selected_pairs_of_each_group():
    groups = [{"videos": ["v1", "v2", "v3"]}, {"videos": ["w1", "w2"]}]
    sel = [{"a": "v1", "b": "v2", "type": "AxA"}, {"a": "v1", "b": "v3", "type": "AxB"},
           {"a": "w1", "b": "w2", "type": "BxB"}]
    assert site.group_reports(groups, sel, {"AxA-v1-v2", "BxB-w1-w2"}) == [["AxA-v1-v2"], ["BxB-w1-w2"]]


class FakeStrips:
    def css(self, *ids):
        return "background:x"


VIDS = {v: {"side": s, "title": f"Wheels on the Bus {v}", "published": f"2015-0{i}-01", "duration": 60,
            "views": 1000} for i, (v, s) in enumerate([("aaaaaaaaaaa", "A"), ("bbbbbbbbbbb", "B"),
                                                        ("ccccccccccc", "A")], 1)}


NO_INTENSITY = site.no_levels()


def test_group_section_shows_versions_pairs_and_lazy_reports():
    g = {"videos": ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"],
         "pairs": [{"a": "aaaaaaaaaaa", "b": "bbbbbbbbbbb", "type": "AxB", "confidence": 0.9, "share": 0.98,
                    "source": "audio"},
                   {"a": "ccccccccccc", "b": "aaaaaaaaaaa", "type": "AxA", "confidence": 0.8, "share": 0.7,
                    "source": "frames"}]}
    out = site.group_section(1, g, "re-skin", VIDS, FakeStrips(), {}, ["AxB-aaaaaaaaaaa-bbbbbbbbbbb"],
                             {"AxB-aaaaaaaaaaa-bbbbbbbbbbb": "Wheels"}, NO_INTENSITY)
    assert out.count("<td class='img'") == 3 and "both channels" in out and "3 versions" in out
    assert ">Published<" in out and ">Like rate<" in out and "Visual intensity" in out
    assert ">Visual brightness<" in out
    assert out.count("class='sort'") == 9 and "aria-sort='none'" in out
    assert "#1 ↔ #2" in out and "#1 ↔ #3" in out and "98%" in out and "frames" in out
    assert "data-src='pairs/AxB-aaaaaaaaaaa-bbbbbbbbbbb/index.html'" in out and "#1 → #2" in out
    assert "<iframe" not in out and "1 of 2" in out
    # The group's number leads its name, and its all-versions report comes before the pair reports.
    assert "<span class='gnum'>1.</span>" in out and "Group 1" not in out
    assert out.index("data-src='group.html#g=1'") < out.index("data-src='pairs/")
    assert "data-key='aaaaaaaaaaa'" in out and "class='star'" in out
    plain = site.group_section(2, g, "same-song", VIDS, FakeStrips(), {}, [], {}, NO_INTENSITY)
    assert "Overlap" not in plain and "Reports" not in plain and "group.html" not in plain


def test_big_groups_fold_their_versions():
    vids = [f"v{i:010d}" for i in range(20)]
    pairs = [{"a": vids[0], "b": v, "type": "AxA", "confidence": 0.8} for v in vids[1:]]
    g = {"videos": vids, "pairs": pairs}
    out = site.group_section(1, g, "same-template", {}, FakeStrips(), {}, [], {}, NO_INTENSITY)
    # One table, so sorting covers every version; past SHOWN they fold until "Show all".
    assert "Show all 20 versions" in out and out.count("<td class='img'") == 20
    assert out.count("<table class='vtable sortable' data-shown='12'>") == 1
    assert "<details class='pairs'>" in out   # 19 pairs: the table starts closed


def test_little_shared_lists_pairs_and_the_waiting_count():
    little = [{"a": "aaaaaaaaaaa", "b": "bbbbbbbbbbb", "type": "AxB", "confidence": 0.9, "share": 0.04,
               "source": "audio"}]
    out = site.little_section(little, 3, VIDS, FakeStrips(), NO_INTENSITY)
    assert "4% shared, by audio" in out and "3 more pairs wait" in out
    assert out.count("<td class='img'") == 2
    assert site.little_section([], 0, VIDS, FakeStrips(), NO_INTENSITY) == ""
    held = [{"a": "aaaaaaaaaaa", "b": "ccccccccccc", "type": "AxA", "confidence": 0.9, "share": 1.0,
             "long_share": 0.25, "source": "audio"}]
    out = site.little_section([], 0, VIDS, FakeStrips(), NO_INTENSITY, held)
    assert "One inside a longer video" in out and "100% of the shorter, 25% of the longer" in out
    assert "little shared" not in out


def test_label_page_fills_the_template():
    out = site.label_page("re-upload", "<section>G</section>", "<div>F</div>", {"base": ""}, "2026-11-11 UTC")
    assert out.startswith('<meta charset="utf-8">') and out.count("<title>Re-upload Groups</title>") == 1
    assert "<section>G</section>" in out and "not published yet" in out and "__" not in out
    linked = site.label_page("re-upload", "", "", {"base": "https://claude.ai/x"}, "")
    assert "href='https://claude.ai/x'" in linked


LEVELS_A = {"mean_saturation": ({"aaaaaaaaaaa": 120.0}, [100.0, 110.0, 120.0, 130.0, 140.0]),
            "mean_lstar": ({"aaaaaaaaaaa": 70.0}, [40.0, 50.0, 60.0, 70.0, 80.0])}


def test_version_rows_show_date_views_likes_and_intensity():
    vids = {"aaaaaaaaaaa": {"side": "A", "title": "Wheels <b>", "published": "2015-01-02T03:04:05Z",
                            "duration": 60, "views": 1234567, "likes": 890},
            "bbbbbbbbbbb": {"side": "B", "title": "x", "published": "2016-01-01", "duration": 60,
                            "views": None, "likes": None}}
    rows = site.version_rows(["aaaaaaaaaaa", "bbbbbbbbbbb"], {"aaaaaaaaaaa": 1, "bbbbbbbbbbb": 2}, vids,
                             FakeStrips(), LEVELS_A)
    a, b = rows
    assert "Wheels &lt;b&gt;" in a and "2015-01-02<" in a and "1,234,567" in a and ">890<" in a
    assert "<b>50</b>" in a and "saturation 120" in a and "Kids TV" in a
    assert "<b>75</b>" in a and "lightness 70" in a and "data-label='Visual brightness'" in a
    assert b.count("not measured") == 2 and b.count(">–<") == 3 and "Kids Channel" in b
    assert ">0.07%<" in a and "data-v='0.000720" in a          # like rate: likes / views
    assert "data-v='1234567'" in a and "data-v='50.0'" in a      # sort keys: raw numbers
    assert b.count("data-v=''") == 5                             # unknowns sort last


def test_like_rate():
    assert site.like_rate(1000, 25) == 0.025 and site.rate_text(0.025) == "2.50%"
    assert site.like_rate(None, 3) is None and site.like_rate(0, 3) is None
    assert site.like_rate(10, None) is None
    assert site.rate_text(None) == "–"


def test_offsets_follow_the_links_from_the_root():
    # B time = A time + lag: b is 2 s later than r; c is 1 s earlier than b, so 1 s later than r.
    off = site.offsets("r", [("r", "b", 2.0), ("c", "b", 1.0), ("x", "y", 5.0)])
    assert off == {"r": 0.0, "b": 2.0, "c": 1.0}


def test_group_data_has_each_version_and_its_link(tmp_path, monkeypatch):
    res = tmp_path / "results"
    res.mkdir()
    (res / "AxB-aaaaaaaaaaa-bbbbbbbbbbb.json").write_text(json.dumps({
        "alignment": {"lag": 1.5, "share": 0.9},
        "signals": {"changes": {"area": {"changed": 0.4}}, "audio": {"level": "identical"},
                    "visual": {"aligned_cuts": {"detail": {"cuts_a": [1.0, 2.5], "cuts_b": [2.5]}}}}}))
    monkeypatch.setattr(site, "HERE", tmp_path)
    g = {"videos": ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"],
         "pairs": [{"a": "aaaaaaaaaaa", "b": "bbbbbbbbbbb"}, {"a": "ccccccccccc", "b": "aaaaaaaaaaa"}]}
    d = site.group_data(3, g, "Wheels", ["AxB-aaaaaaaaaaa-bbbbbbbbbbb"], VIDS, {"aaaaaaaaaaa": "/_blob/1"},
                        {"bbbbbbbbbbb": {"cuts_per_min": 9.0}}, NO_INTENSITY,
                        {("ccccccccccc", "aaaaaaaaaaa"): -3.0})
    a, b, c = d["versions"]
    assert d["k"] == 3 and d["name"] == "Wheels" and [v["n"] for v in d["versions"]] == [1, 2, 3]
    assert a["url"] == "/_blob/1" and b["url"] is None and a["offset"] == 0.0
    assert b["offset"] == 1.5 and c["offset"] == 3.0
    assert b["link"] == {"report": "AxB-aaaaaaaaaaa-bbbbbbbbbbb", "changed": 0.4, "audio": "identical",
                         "share": 0.9}
    assert a["link"] is None and b["measures"] == {"cuts_per_min": 9.0}
    assert a["cuts"] == [1.0, 2.5] and b["cuts"] == [2.5] and c["cuts"] == []


def test_percentile_rank_matches_the_site():
    pool = [1.0, 2.0, 2.0, 3.0, 4.0]
    assert site.percentile_rank(1.0, pool) == 0.0 and site.percentile_rank(4.0, pool) == 100.0
    assert site.percentile_rank(2.0, pool) == 50.0   # at or below: the tie counts in full
    assert site.percentile_rank(0.5, pool) == 0.0 and site.percentile_rank(9.0, pool) == 100.0
    assert site.percentile_rank(3.0, [5.0]) == 50.0 and site.percentile_rank(3.0, []) is None


def test_saturation_lookup_first_found_wins(tmp_path):
    def tsv(path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("video_id\tmean_saturation\n" + "".join(f"{v}\t{x}\n" for v, x in rows))

    dataset = tmp_path / "videos.tsv"
    tsv(dataset, [("a", "10"), ("blank", "")])
    feats = tmp_path / "features"
    tsv(feats / "pairs" / "AxA-a-b" / "features.tsv", [("a", "99"), ("b", "20")])
    sources = site.saturation_sources(feats, [dataset])
    assert sources == [dataset, feats / "pairs" / "AxA-a-b" / "features.tsv"]  # no videos/ file yet
    tsv(feats / "videos" / "features.tsv", [("b", "77"), ("c", "30")])
    sat = site.saturation_by_video(site.saturation_sources(feats, [dataset]))
    assert sat == {"a": 10.0, "b": 20.0, "c": 30.0}


def test_saturation_lookup_skips_reports_on_slowed_copies(tmp_path):
    feats = tmp_path / "features"
    path = feats / "pairs" / f"{site.SLOWED_TYPE}-a-f" / "features.tsv"
    path.parent.mkdir(parents=True)
    path.write_text("video_id\tmean_saturation\nf\t50\n")
    assert site.saturation_sources(feats, []) == []


def test_check_reports_finds_missing_files_and_videos(tmp_path):
    ok_n, bad_n = "AxB-aaaaaaaaaaa-bbbbbbbbbbb", "AxA-ccccccccccc-ddddddddddd"
    for n in (ok_n, bad_n):
        (tmp_path / "pairs" / n).mkdir(parents=True)
        for f in ("index.html", "data.json", "stills.jpg"):
            (tmp_path / "pairs" / n / f).write_text("x")
    (tmp_path / "pairs" / bad_n / "index.html").unlink()
    assets = {"aaaaaaaaaaa": "/_blob/1", "bbbbbbbbbbb": "/_blob/2", "ccccccccccc": "/_blob/3"}
    (tmp_path / "videos.json").write_text(json.dumps({
        ok_n: {"a": "/_blob/1", "b": "/_blob/2"}, bad_n: {"a": "/_blob/3", "b": None}}))
    problems = site.check_reports(tmp_path, [ok_n, bad_n, "AxA-not-ok"], {ok_n, bad_n}, assets)
    assert problems == [f"{bad_n}: missing index.html", f"{bad_n}: no video for b (ddddddddddd)"]
    assert json.loads(site.manifest(tmp_path).read_text())[0] == {"path": f"pairs/{bad_n}/data.json"}


def test_link_frames_points_sprites_at_the_reports_sheet():
    data = {"pair": {"a": "aaaaaaaaaaa", "b": "bbbbbbbbbbb"}, "alignment": {"lag": 1.25},
            "curves": {"frames": {"times": [0.0, 0.5], "edge_ssim": [0.41234, None], "recolored": [0.1, 0.2],
                                  "reshaped": [0.3, 0.4]}},
            "sprites": {"mask": {"file": "mask.jpg", "sheet": "stills.jpg", "n": 3, "cols": 12},
                        "edges": {"file": "edges.jpg", "sheet": "stills.jpg", "n": 3, "cols": 12},
                        "a": {"file": "a.jpg"}}}
    f = site.link_frames("AxB-aaaaaaaaaaa-bbbbbbbbbbb", data)
    assert f["a"] == "aaaaaaaaaaa" and f["b"] == "bbbbbbbbbbb" and f["lag"] == 1.25
    assert f["edge"] == [0.412, None] and f["times"] == [0.0, 0.5]
    assert f["sprites"]["mask"]["sheet"] == "pairs/AxB-aaaaaaaaaaa-bbbbbbbbbbb/stills.jpg"
    assert "file" not in f["sprites"]["mask"] and set(f["sprites"]) == {"mask", "edges"}


def test_overview_links_pairs_to_reports_or_groups_and_families_to_groups():
    groups = [{"videos": ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"],
               "pairs": [{"a": "aaaaaaaaaaa", "b": "bbbbbbbbbbb", "type": "AxB"},
                         {"a": "ccccccccccc", "b": "aaaaaaaaaaa", "type": "AxA"}]}]
    vids = {v: {**r, "likes": 1} for v, r in VIDS.items()}
    out = site.overview_section(groups, vids, vids, [["AxB-aaaaaaaaaaa-bbbbbbbbbbb"]],
                                {("aaaaaaaaaaa", "bbbbbbbbbbb"): "same shots"})
    assert 'href="#AxB-aaaaaaaaaaa-bbbbbbbbbbb"' in out     # a pair with a full report opens it
    assert 'href="#g1"' in out                              # one without jumps to its group
    assert "<a href='#g1'>1. " in out and "same shots" in out and "Channel story" in out


def test_closing_the_panel_returns_focus_to_its_opener_without_scrolling():
    # Opened from the channel story's link, closing used to focus the report's button far down in its
    # group, scrolling the page there. (Checked in a browser too; the experiments have no browser tests.)
    js = (Path(__file__).resolve().parents[1] / "search_groups.html").read_text()
    assert "returnTo?.focus({ preventScroll: true })" in js
    assert "open(b, true, a)" in js
    assert "current.focus()" not in js


def test_each_group_has_a_labelled_note_box_hidden_until_the_script_runs():
    html = site.note_box(3, "Wheels <Bus>")
    assert "<div class='gnote' hidden>" in html
    assert "<label for='g3nt'>Note on group 3, Wheels &lt;Bus&gt;</label><textarea id='g3nt'" in html
    assert f"maxlength='{site.NOTE_MAX}'" in html and "aria-controls='g3n'" in html
    js = (Path(__file__).resolve().parents[1] / "search_groups.html").read_text()
    assert "collection('notes')" in js and "if (text) notes[key] = text; else delete notes[key];" in js
    # display: grid on the box and form would otherwise override `hidden` (the form showed, empty)
    assert ".gnote[hidden], .note-form[hidden], .note-edit[hidden] { display: none; }" in js
