"""A UI test that hangs inside Playwright, past its time limit (tests/time_limit.py,
LAD-271): it fails and the run goes on. Here, not with the unit tests of the limit
(tests/test_ui_time_limit.py), as it needs the browser."""

import os
import sys
from pathlib import Path

import pytest
from test_ui_time_limit import run_past_the_limit

pytestmark = pytest.mark.ui
pytest_plugins = "pytester"

HANG = """
def test_hangs(page):
    page.set_content("<p>here</p>")
    page.wait_for_selector("#never", timeout=0)


def test_next(page):
    page.set_content("<p>here</p>")
"""


@pytest.fixture
def browsers() -> str:
    """Where Playwright keeps its browsers, taken before pytester moves HOME."""
    cache = "Library/Caches" if sys.platform == "darwin" else ".cache"
    return os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / cache / "ms-playwright")


def test_a_test_hung_in_playwright_fails_and_the_run_goes_on(browsers, pytester, monkeypatch):
    """Playwright's own event loop waits in another greenlet: the stacks show that loop, not
    the test's line, and a failure raised into it would hang the page's teardown."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", browsers)
    result = run_past_the_limit(pytester, monkeypatch, HANG, limit=10, stacks_before=2)
    result.stderr.fnmatch_lines(["*playwright*"])
