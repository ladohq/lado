"""Playwright's Chromium in LADO's image (openspec capability container): the image carries
its system libraries, so on a new home volume the Playwright of uv.lock installs its headless
shell, `ldd` finds every library and Chromium renders a page; the browser itself is not in
the image (`make browser` puts it on the home volume). Each command runs in a login shell
started from a clean environment, as LADO starts an agent's (test_toolchains.login)."""

import tempfile
from pathlib import Path

import pytest
from container_helpers import ROOT, docker
from test_toolchains import login

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

pytestmark = pytest.mark.container

# The page's screenshot, beside the UI tests' (tests/ui/conftest.py); CI's job uploads it.
SHOTS = Path(tempfile.gettempdir()) / "lado-container-shots"
CACHE = "~/.cache/ms-playwright"
SHELL = f"{CACHE}/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"
TEXT = "Latin and Cyrillic: кириллица"
PAGE = f"""
import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.set_content('<p id="text">{TEXT}</p>')
    print(page.inner_text("#text"))
    page.screenshot(path=sys.argv[1])
    browser.close()
"""


def playwright_version() -> str:
    """The version of uv.lock's Playwright: the one `make browser` installs with."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    [version] = [p["version"] for p in lock["package"] if p["name"] == "playwright"]
    return version


def test_playwrights_chromium_finds_its_libraries_and_renders_a_page(container):
    playwright = f"uv tool run --from playwright=={playwright_version()}"
    login(container, f"{playwright} playwright install --only-shell chromium")
    [shell] = login(container, f"ls {SHELL}").stdout.split()
    linked = login(container, f"ldd {shell}").stdout
    missing = [line.split()[0] for line in linked.splitlines() if "not found" in line]
    assert missing == [], f"libraries missing for {shell}: {missing}"
    container.write("/tmp/page.py", PAGE)
    rendered = login(container, f"{playwright} python /tmp/page.py /tmp/page.png")
    assert rendered.stdout.strip() == TEXT
    SHOTS.mkdir(parents=True, exist_ok=True)
    docker("cp", f"{container.name}:/tmp/page.png", str(SHOTS / "chromium-page.png"))
    assert (SHOTS / "chromium-page.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_image_carries_no_browser(container):
    login(container, f"test ! -e {CACHE}")
    for name in ("chromium", "chromium-browser", "google-chrome"):
        assert login(container, f"command -v {name}", check=False).stdout == "", name
