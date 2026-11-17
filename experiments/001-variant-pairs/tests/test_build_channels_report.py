import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_channels_report as rep  # noqa: E402


def test_link_summary_counts_strong_links_inside_a_group():
    links = [{"strength": "strong", "group_a": "G1", "group_b": "G1", "kind": "copyright", "value": "acme"},
             {"strength": "strong", "group_a": "G1", "group_b": "G1", "kind": "copyright", "value": "acme"},
             {"strength": "weak", "group_a": "G1", "group_b": "G1", "kind": "domain", "value": "a.example"},
             {"strength": "strong", "group_a": "G1", "group_b": "G2", "kind": "email", "value": "a@b.c"}]
    assert rep.link_summary(links) == {"G1": [["copyright", "acme", 2]]}


def test_fetch_status_keeps_the_latest_line_of_each_stage(tmp_path, monkeypatch):
    (tmp_path / "events.log").write_text(
        "t1 fetch: family stage 2 (video descriptions): 50 of 100\n"
        "t2 group: 5 channels\n"
        "t3 fetch: family stage 2 (video descriptions): 100 of 100\n")
    monkeypatch.setattr(rep, "RES", tmp_path)
    assert rep.fetch_status() == ["t3 fetch: family stage 2 (video descriptions): 100 of 100"]
