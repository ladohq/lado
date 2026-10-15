import pytest

from lado import text

HIDDEN = ["\t", "\n", "\x00", "\x1b", "\x7f", " ", " ", "‮", "⁦", "​", "﻿"]
FAMILY = "\U0001f468‍\U0001f469‍\U0001f467"


@pytest.mark.parametrize("char", HIDDEN)
def test_each_category_is_hidden(char):
    assert text.hidden(char)
    assert text.first_hidden(f"a{char}b") == char


@pytest.mark.parametrize("visible", ["Ревью", "代码", FAMILY, " ", "a-b (LAD-68)"])
def test_visible_text_has_nothing_hidden(visible):
    assert text.first_hidden(visible) is None


def test_the_zero_width_joiner_is_not_hidden():
    assert not text.hidden("‍")


def test_the_first_hidden_character_is_found():
    assert text.first_hidden("a​b‮c") == "​"


def test_a_character_is_named_by_its_code_point_and_name():
    assert text.named("‮") == "U+202E RIGHT-TO-LEFT OVERRIDE"
    assert text.named(" ") == "U+2028 LINE SEPARATOR"
    assert text.named("\t") == "U+0009"
    assert text.named("\U000e0001") == "U+E0001 LANGUAGE TAG"


@pytest.mark.parametrize(
    ("given", "line"),
    [
        ("a\tb", "a b"),
        ("a\nb", "a b"),
        ("a\x1b[31mb", "a [31mb"),
        ("a b", "a b"),
        ("a b", "a b"),
        ("ab‮cd", "abcd"),
        ("ab⁦cd⁩", "abcd"),
        ("a​b", "ab"),
        ("﻿ab", "ab"),
        (f"Семья {FAMILY}", f"Семья {FAMILY}"),
        ("  a  b  ", "a  b"),
        ("​\t", ""),
    ],
)
def test_one_line_cleans_hidden_characters(given, line):
    assert text.one_line(given) == line
    assert text.first_hidden(text.one_line(given)) is None
