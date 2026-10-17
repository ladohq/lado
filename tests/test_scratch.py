"""lado.scratch: a session from scratch in a new or empty folder (openspec change
start-from-scratch)."""

import pytest

from lado import scratch

# The spec's table: each Cyrillic letter and its Latin letters.
TABLE = (
    "а a, б b, в v, г g, ґ g, д d, е e, ё e, є ie, ж zh, з z, и i, і i, ї i, й i, к k, л l, "
    "м m, н n, о o, п p, р r, с s, т t, у u, ф f, х kh, ц ts, ч ch, ш sh, щ shch, ъ , ы y, "
    "ь , э e, ю iu, я ia"
)
LETTERS = [tuple((pair + " ").split(" ")[:2]) for pair in TABLE.split(", ")]


def test_a_cyrillic_name():
    assert scratch.names("Сайт кофейни") == scratch.Names("sait-kofeini", "Сайт кофейни")


def test_a_name_that_is_already_a_name():
    assert scratch.names("coffee-site") == scratch.Names("coffee-site", None)


def test_a_name_with_accents():
    assert scratch.names("Café Noël") == scratch.Names("cafe-noel", "Café Noël")


def test_another_script():
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.names("東京")
    assert str(refused.value) == "the name needs a Latin letter or digit for its folder: type one"


def test_the_table_is_the_specs():
    assert scratch.CYRILLIC == dict(LETTERS)


@pytest.mark.parametrize("letter,latin", LETTERS)
def test_each_letter_of_the_table(letter, latin):
    for text in (letter, letter.upper()):
        assert scratch.names(f"x{text}x").name == f"x{latin}x"


def test_the_text_is_trimmed():
    assert scratch.names("  Сайт  ") == scratch.Names("sait", "Сайт")


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_name_is_refused(text):
    with pytest.raises(scratch.ScratchError, match="^type a name$"):
        scratch.names(text)


def test_a_name_is_at_most_80_characters():
    assert scratch.names("a" * 80).name == "a" * 80
    with pytest.raises(scratch.ScratchError, match="^a name is at most 80 characters$"):
        scratch.names("a" * 81)


def test_a_hidden_character_is_refused_by_its_name():
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.names("shop‮")
    assert str(refused.value) == (
        "a name is one line of visible text: U+202E RIGHT-TO-LEFT OVERRIDE is not allowed"
    )
