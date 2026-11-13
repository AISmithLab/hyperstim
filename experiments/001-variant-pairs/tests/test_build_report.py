import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_report  # noqa: E402


def test_build_report(tmp_path, monkeypatch):
    here = tmp_path / "001-variant-pairs"
    (here / "results").mkdir(parents=True)
    data = {"pair": {"a": "AAA", "b": "BBB"},
            "videos": {"AAA": {"title": "</script>x", "description": "long text"}, "BBB": {"title": "é"}}}
    (here / "results" / "demo.json").write_text(json.dumps(data))
    (here / "report.html").write_text('<script id="data" type="application/json">__DATA__</script>')
    video = tmp_path / "cache" / "video"
    video.mkdir(parents=True)
    (video / "AAA.mp4").write_bytes(b"a")
    (video / "BBB.mp4").write_bytes(b"b")
    out = tmp_path / "cache" / "report" / "demo"
    out.mkdir(parents=True)
    monkeypatch.setattr(build_report, "HERE", here)
    monkeypatch.setattr(sys, "argv", ["build_report.py", "demo"])
    build_report.main()
    page = (out / "index.html").read_text()
    assert "__DATA__" not in page and "</script>x" not in page and "é" in page
    blob = page.split(">", 1)[1].rsplit("</script>", 1)[0]
    shown = json.loads(blob.replace("<\\/", "</"))
    assert shown["videos"]["AAA"] == {"title": "</script>x"}  # descriptions left out
    assert (out / "a.mp4").read_bytes() == b"a" and (out / "b.mp4").read_bytes() == b"b"


def test_build_report_data_and_out(tmp_path, monkeypatch):
    here = tmp_path / "001-variant-pairs"
    here.mkdir()
    (here / "report.html").write_text('<script id="data" type="application/json">__DATA__</script>')
    data = tmp_path / "other.json"
    data.write_text(json.dumps({"pair": {"a": "AAA", "b": "BBB"}, "videos": {"AAA": {}, "BBB": {}}}))
    out = tmp_path / "out"
    monkeypatch.setattr(build_report, "HERE", here)
    monkeypatch.setattr(sys, "argv", ["build_report.py", "x", "--data", str(data), "--out", str(out)])
    build_report.main()  # no downloads in the cache: the page is still built
    assert '"AAA"' in (out / "index.html").read_text()
    assert not (out / "a.mp4").exists()


def test_player_starts_at_the_beginning():
    # The report's player opened mid-video (min(15 s, a quarter)); it starts at 0 (human decision).
    page = (Path(__file__).resolve().parents[1] / "report.html").read_text()
    assert "Math.min(15, DUR / 4)" not in page
    assert "va.currentTime = 0; });" in page and "showStill(0);" in page
