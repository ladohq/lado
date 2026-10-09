"""The system panel in the browser (docs/design/ui.md, System panel): `live` opens it, the
system info is copied for an issue, and a newer LADO (here a local index) marks `live` and
gives the panel its Update block."""

import re

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import __version__, state

pytestmark = pytest.mark.ui


def test_live_opens_the_system_panel_and_copies_the_system_info(page: Page, server, shot):
    log_in(page, server)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    live = page.get_by_role("button", name="System")
    expect(live).to_have_text("live")
    live.click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.get_by_text(f"LADO {__version__}")).to_be_visible()
    expect(panel.get_by_text("Running")).to_be_visible()
    expect(panel.get_by_role("region", name="Providers")).to_contain_text("Claude Code")
    expect(panel.locator(".system-check")).to_contain_text("No update check")
    panel.get_by_role("button", name="Copy system info").click()
    expect(panel.get_by_text("System info copied")).to_be_visible()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("### LADO system info\n")
    assert re.search(r"^- Browser: Chrome \d+ on \w+$", copied, re.MULTILINE)
    for secret in (str(state.home()), server["token"], server["url"].split("//")[1]):
        assert secret not in copied
    shot(page)


def test_a_newer_lado_marks_live_and_the_panel_offers_the_update(
    page: Page, published, server, shot
):
    published(**{"99.0.0": "2026-10-04"})  # before the server's first look
    log_in(page, server)
    live = page.get_by_role("button", name="System: LADO 99.0.0 is available")
    expect(live).to_have_text("live↑ 99.0.0")
    expect(page.get_by_text("is available")).to_have_count(0)  # no line under the top bar
    expect(page.get_by_role("alert")).to_have_count(0)  # no version banner: same version
    live.click()
    update = page.get_by_role("dialog", name="System").get_by_role("region", name="Update")
    expect(update).to_contain_text("99.0.0 is out")
    # A working copy is no uv tool or pipx install: the commands by hand, no button.
    expect(update).to_contain_text("not a uv tool or pipx install")
    expect(update.get_by_role("button", name="Update…")).to_have_count(0)
    expect(update.locator("pre")).to_contain_text("install lado==99.0.0")
    expect(page.get_by_role("dialog", name="System").get_by_text("Running")).to_be_visible()
    shot(page)
