"""A session's name from a typed text: the core's runtime.slug against the table the New
session window's slug is tested on (web/src/sessionSlug.cases.json, web/src/sessionName.ts),
so the name the window shows is the one the core gives the session."""

import json
from pathlib import Path

import pytest

from lado import runtime

TABLE = Path(__file__).parent.parent / "web" / "src" / "sessionSlug.cases.json"
CASES = json.loads(TABLE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["text"] for case in CASES])
def test_the_core_slugs_as_the_window_does(case):
    assert runtime.slug(case["text"]) == (case["slug"] or "lado")
