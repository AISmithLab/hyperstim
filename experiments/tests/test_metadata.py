import math

import pytest

import metadata as md


def test_tokens_lowercase_and_spell_numbers():
    assert md.tokens("5 Little Ducks, 10 FROGS!") == ["five", "little", "ducks", "ten", "frogs"]
    assert md.tokens("Five little ducks") == md.tokens("5 little ducks")


def test_song_name_is_longest_shared_run():
    assert md.song_name("Five Little Ducks | 3D Nursery Rhymes", "5 little ducks (cartoon)") == [
        "five", "little", "ducks"]
    assert md.song_name("Baby Shark", "Wheels on the Bus") == []
    assert md.song_name("Bus song", "Wheels bus") == []  # one shared word is not a song


def test_without_removes_first_run_only():
    assert md.without(["a", "b", "c", "a", "b"], ["a", "b"]) == ["c", "a", "b"]
    assert md.without(["a", "b"], []) == ["a", "b"]
    assert md.without(["a", "b"], ["x"]) == ["a", "b"]


def test_jaccard():
    assert md.jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert math.isnan(md.jaccard([], []))


def test_title_signal_compares_titles_without_the_song():
    t = md.title_signal("Five Little Ducks | Nursery Rhymes", "5 Little Ducks | Kids Songs")
    assert t["song"] == "five little ducks"
    assert t["rest_a"] == "nursery rhymes" and t["rest_b"] == "kids songs"
    assert t["jaccard"] == 0.0
    assert t["only_a"] == ["nursery", "rhymes"] and t["only_b"] == ["kids", "songs"]
    same = md.title_signal("Five Little Ducks | Kids Songs", "Kids Songs: 5 little ducks")
    assert same["jaccard"] == 1.0 and same["ratio"] == 1.0 and same["shared"] == ["kids", "songs"]
    whole = md.title_signal("Five Little Ducks", "5 little ducks")
    assert whole["song"] == "five little ducks" and math.isnan(whole["jaccard"])


def test_text_signal():
    da = "Subscribe for more songs!\nhttps://example.com/a\nLyrics:\nfive little ducks went out"
    db = "Subscribe for more songs!\nhttps://other.org\nfive little ducks went out"
    t = md.text_signal(da, db, ["Nursery Rhymes", "Ducks", "3D"], ["nursery  rhymes", "kids"])
    assert t["shared_lines"] == ["subscribe for more songs!", "five little ducks went out"]
    assert t["description_lines"] == pytest.approx(2 / 5)  # "lyrics:" and the two URLs differ
    assert t["shared_tags"] == ["nursery rhymes"]
    assert t["only_a_tags"] == ["3d", "ducks"] and t["only_b_tags"] == ["kids"]
    assert t["tags"] == pytest.approx(1 / 4) and t["n_tags"] == [3, 2]
    assert 0 < t["description_words"] < 1
    assert math.isnan(md.text_signal("x", "y", [], [])["tags"])


def test_timing_signal():
    t = md.timing_signal("2014-10-18T08:14:11Z", "2014-11-05T09:41:12Z")
    assert t["days"] == pytest.approx(18 + (1 * 3600 + 27 * 60 + 1) / 86400)
    assert t["time_of_day_h"] == pytest.approx(1 + 27 / 60 + 1 / 3600)
    assert t["first"] == "a"
    wrap = md.timing_signal("2020-01-02T23:30:00Z", "2020-01-01T00:30:00Z")
    assert wrap["time_of_day_h"] == pytest.approx(1.0)  # across midnight
    assert wrap["first"] == "b"


def test_duration_signal():
    assert md.duration_signal(120, 90) == {"diff_s": 30, "ratio": 0.75}


@pytest.mark.parametrize("iso, seconds", [
    ("PT2M35S", 155), ("PT1H", 3600), ("PT45S", 45), ("P1DT2H3M4S", 93784), ("PT10M", 600)])
def test_iso_duration(iso, seconds):
    assert md.iso_duration(iso) == seconds


DESC_A = """Five little ducks went out one day!
© 2014 Acme Kids Media Ltd. All rights reserved.
Website: https://www.acmekids.com/songs.
Watch more: https://www.youtube.com/watch?v=abc https://bit.ly/xyz
Get our app: https://play.google.com/store/apps/details?id=com.acme.kids&hl=en
iPhone: https://apps.apple.com/us/app/acme-kids/id123456789
Contact: Hello@AcmeKids.com"""

DESC_B = """Copyright 2015-2016 ACME Kids Media Ltd™
Shop: https://shop.acmekids.com
App: https://apps.apple.com/app/id123456789"""


def test_owner_evidence_finds_patterns():
    ev = md.owner_evidence(DESC_A)
    assert ev["copyright"] == {"acme kids media ltd"}
    assert ev["domain"] == {"acmekids.com"}  # YouTube and short links say nothing about the owner
    assert ev["app"] == {"android:com.acme.kids", "ios:123456789"}
    assert ev["email"] == {"hello@acmekids.com"}
    eb = md.owner_evidence(DESC_B)
    assert eb["copyright"] == {"acme kids media ltd"}
    assert eb["domain"] == {"shop.acmekids.com"}
    assert md.owner_evidence("(c) https://foo.com")["copyright"] == set()


def test_owner_signal_strongest_evidence():
    s = md.owner_signal([DESC_A], [DESC_B], set(), set(), "UCa", "UCb")
    assert s["same_owner"] and s["strongest"] == "copyright line"
    assert s["shared"]["app"] == ["ios:123456789"]
    assert s["evidence_a"]["email"] == ["hello@acmekids.com"]
    assert md.owner_signal(["x"], ["y"], {"UCb"}, set(), "UCa", "UCb")["strongest"] == "featured channels"
    assert md.owner_signal(["x"], ["y"], set(), set(), "UCa", "UCa")["strongest"] == "same channel"
    none = md.owner_signal(["hi"], ["there"], set(), set(), "UCa", "UCb")
    assert not none["same_owner"] and none["strongest"] is None
    email = md.owner_signal(["a@b.com"], ["A@B.com"], set(), set(), "UCa", "UCb")
    assert email["strongest"] == "email"
