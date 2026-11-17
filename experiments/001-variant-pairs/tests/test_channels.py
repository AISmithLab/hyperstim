import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import channels as ch  # noqa: E402


def chan(cid, holders=(), emails=(), domains=(), featured=(), origin="reference", language="en", videos=100,
         title=None):
    ev = {"copyright": {h: 5 for h in holders}, "app": {}, "email": {e: 5 for e in emails},
          "domain": {d: 5 for d in domains}}
    return ch.Chan(id=cid, title=title or cid, origin=origin, evidence=ev, featured=list(featured),
                   language=language, videos=videos)


def by_id(*cs):
    return {c.id: c for c in cs}


def test_norm_holder_strips_suffixes_and_drops_boilerplate():
    assert ch.norm_holder("2024 USP Digital Private Limited") == "usp digital"
    assert ch.norm_holder("USP Digital Pvt. Ltd.") == "usp digital"
    assert ch.norm_holder("Acme Studios, LLC") == "acme studios"
    assert ch.norm_holder("Disclaimer under Section 107 of the Copyright Act 1976") == ""
    assert ch.norm_holder("the respective owners") == ""
    assert ch.norm_holder("All rights reserved") == ""
    assert ch.norm_holder("No copyright infringement intended") == ""
    assert ch.norm_holder("ab") == ""


def test_text_evidence_finds_holder_and_skips_common_hosts():
    ev = ch.text_evidence("Watch more! © 2024 USP Digital Private Limited\nhttps://linktr.ee/x "
                          "https://www.uspstudios.co/apps contact: hello@usp.example")
    assert ev["copyright"] == {"usp digital"}
    assert ev["domain"] == {"uspstudios.co"}
    assert ev["email"] == {"hello@usp.example"}


def test_channel_evidence_needs_channel_text_or_two_videos():
    ev = ch.channel_evidence("", ["© Song Licensor Ltd", "© Acme Toons", "© Acme Toons"])
    assert ev["copyright"] == {"acme toons": 2}  # the licensor is in one video only
    ev = ch.channel_evidence("© Acme Toons", [])
    assert ev["copyright"] == {"acme toons": 2}
    ev = ch.channel_evidence("", ["© Acme Toons"])  # a channel's only video is enough
    assert ev["copyright"] == {"acme toons": 1}


def test_shared_holder_is_a_strong_link():
    cs = by_id(chan("A", holders=["acme"]), chan("B", holders=["acme"]), chan("C", holders=["other"]))
    res = ch.group(cs, ch.build_links(cs))
    sets = [set(g["channels"]) for g in res["groups"]]
    assert {"A", "B"} in sets and {"C"} in sets


def test_value_shared_by_different_owners_is_a_network():
    # Three companies, each with its own holder, all using one distributor's email.
    cs = by_id(chan("A", holders=["acme"], emails=["x@dist.example"]),
               chan("B", holders=["bolt"], emails=["x@dist.example"]),
               chan("C", holders=["cove"], emails=["x@dist.example"]))
    links = ch.build_links(cs)
    assert {lk.strength for lk in links if lk.kind == "email"} == {"network"}
    assert all(len(g["channels"]) == 1 for g in ch.group(cs, links)["groups"])


def test_licensor_holder_in_others_descriptions_is_a_network():
    # "tunes" is A's own holder, but only a secondary credit in B and C: not their owner.
    a = chan("A", holders=["tunes"])
    b = chan("B", holders=["bolt", "tunes"])
    c = chan("C", holders=["cove", "tunes"])
    b.evidence["copyright"]["bolt"] = 9
    c.evidence["copyright"]["cove"] = 9
    links = ch.build_links(by_id(a, b, c))
    assert {lk.strength for lk in links if lk.value == "tunes"} == {"network"}


def test_featured_links_family_section_is_strong_mutual_generic_is_weak():
    cs = by_id(chan("A", featured=[("B", "Featured Channels"), ("C", "Our Family"), ("D", "Featured")]),
               chan("B", featured=[("A", "Friends")]), chan("C"), chan("D"))
    links = {(lk.a, lk.b): lk.strength for lk in ch.build_links(cs) if lk.kind == "featured"}
    assert links[("A", "B")] == "weak"  # mutual, but friends do that too
    assert links[("A", "C")] == "strong"  # family section
    assert links[("A", "D")] == "weak"


def test_family_channel_without_strong_link_is_featured_only():
    cs = by_id(chan("A", featured=[("F", "Featured channels")]), chan("F", origin="family"),
               chan("G", origin="family", holders=["acme"]), chan("H", holders=["acme"]))
    res = ch.group(cs, ch.build_links(cs))
    assert res["featured_only"] == ["F"]
    assert {"G", "H"} in [set(g["channels"]) for g in res["groups"]]


def test_name_containment_is_weak():
    cs = by_id(chan("A", title="Kids TV"), chan("B", title="Kids TV - Nursery Rhymes"),
               chan("C", title="Toons"), chan("D", title="Super Toons"))
    links = [lk for lk in ch.build_links(cs) if lk.kind == "name"]
    assert [(lk.a, lk.b, lk.strength) for lk in links] == [("A", "B", "weak")]  # "toons" is under 6 chars


def test_dubs_marked_by_language_and_single_links_flagged():
    cs = by_id(chan("A", holders=["acme"], videos=900), chan("B", holders=["acme"], videos=300),
               chan("C", emails=["a@acme.example"], language="es", videos=200))
    cs["B"].evidence["email"] = {"a@acme.example": 3}
    res = ch.group(cs, ch.build_links(cs))
    g = res["groups"][0]
    assert g["channels"] == ["A", "B", "C"]
    assert g["language"] == "en" and g["dubs"] == ["C"]
    assert len(g["single_links"]) == 2 and g["flags"]


def test_bridges():
    edges = {("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")}
    assert ch.bridges(["a", "b", "c", "d"], edges) == {("c", "d")}


def test_language_from_videos_then_channel():
    vids = [{"snippet": {"defaultAudioLanguage": "es-419"}}, {"snippet": {"defaultAudioLanguage": "es"}},
            {"snippet": {"defaultAudioLanguage": "en"}}]
    assert ch.language_of({}, vids) == "es"
    assert ch.language_of({"snippet": {"defaultLanguage": "pt-BR"}}, [{"snippet": {}}]) == "pt"
    assert ch.language_of({}, []) == "und"


def test_featured_of_reads_only_channel_sections():
    secs = {"items": [{"snippet": {"type": "multiplechannels", "title": "Our Family"},
                       "contentDetails": {"channels": ["X", "Y"]}},
                      {"snippet": {"type": "singlePlaylist"}, "contentDetails": {"playlists": ["P"]}}]}
    assert ch.featured_of(secs) == [("X", "Our Family"), ("Y", "Our Family")]
    assert ch.featured_of(None) == []


def test_next_pacific_day():
    t = ch.next_pacific_day(datetime(2026, 11, 12, 3, 0, tzinfo=UTC))  # 19:00 PST on the 11th
    assert t == datetime(2026, 11, 12, 8, 5, tzinfo=UTC)


def test_family_section_titles():
    for t in ["Our Family", "Visit Other Pinkfong Channels", "More PAW in More Languages!", "Our Channels",
              "Official Channels", "The Moonbug Family", "Mister Maker Worldwide!", "Simon around the world"]:
        assert ch.family_section(t), t
    for t in ["Featured Channels", "", "Our Friends", "Meet Our Friends!", "Recommended Channels",
              "Our Partners", "My favorite channels", "Our suggestions", "More similar content!",
              "Kids and Family Channels I Love!", "Other Great Kids' Channels", "Channels We Love!",
              "Related Channels", "Our Best Friends"]:
        assert not ch.family_section(t), t


def test_renamed_company_holder_is_an_owner():
    # Five channels name "studios" first and "digital" second; two name only "digital".
    cs = {}
    for i in range(5):
        c = chan(f"S{i}", holders=["studios", "digital"])
        c.evidence["copyright"]["studios"] = 9
        cs[c.id] = c
    for i in range(2):
        cs[f"D{i}"] = chan(f"D{i}", holders=["digital"])
    res = ch.group(cs, ch.build_links(cs))
    assert len(res["groups"]) == 1 and len(res["groups"][0]["channels"]) == 7


def test_moonbug_style_owner_over_acquired_studios():
    # The owner is named first by most channels, though some keep their own studio's line too.
    cs = by_id(*(chan(f"M{i}", holders=["owner"]) for i in range(4)),
               chan("T", holders=["owner", "treasure"]), chan("E", holders=["owner", "elbebe"]))
    links = ch.build_links(cs)
    assert {lk.strength for lk in links if lk.value == "owner"} == {"strong"}


def test_owner_app_shared_across_renamed_holders_is_strong():
    cs = by_id(chan("A", holders=["studios", "digital"]), chan("B", holders=["studios", "digital"]),
               chan("C", holders=["digital"]))
    for c in cs.values():
        c.evidence["app"] = {"android:com.acme.app": 3}
    cs["A"].evidence["copyright"]["studios"] = 9
    cs["B"].evidence["copyright"]["studios"] = 9
    links = ch.build_links(cs)
    assert {lk.strength for lk in links if lk.kind == "app"} == {"strong"}


def test_generic_hosts_include_subdomains():
    assert ch.generic_host("m.onelink.me") and ch.generic_host("blippi.lnk.to")
    assert ch.generic_host("music.youtube.com") and ch.generic_host("www.pinterest.com")
    assert not ch.generic_host("uspdigital.co") and not ch.generic_host("moonbug.com")
