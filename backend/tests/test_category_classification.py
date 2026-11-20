from runpy import run_path

import pytest

from hyperstim_api.analysis import PIPELINE_DIR

classifier = run_path(str(PIPELINE_DIR / "63_classify_categories.py"))


def test_channel_tagline_does_not_turn_story_into_music() -> None:
    row = {"title": "Police Car vs. Thief | Pinkfong – Kids Songs & Cartoons"}
    assert classifier["classify"](row)[0] == "music"
    assert classifier["classify_candidate"](row) == "narrative"


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"title": "Nursery Rhymes | Animated Cartoons"}, "music"),
        ({"title": "Phonics Song"}, "educational"),
        ({"title": "Minecraft Gameplay | Kids Songs & Cartoons"}, "gaming"),
        ({"title": "DIY Paper Craft Tutorial"}, "play"),
        ({"title": "Amazing Adventures", "desc": "A fairy tale retold"}, "narrative"),
        ({"title": "Song and Story"}, None),
        ({"title": "Our Favorite Game"}, None),
        ({}, None),
    ],
)
def test_weighted_classifier_candidate(row: dict[str, str], expected: str | None) -> None:
    assert classifier["classify_candidate"](row) == expected
