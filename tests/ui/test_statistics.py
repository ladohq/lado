"""Statistics in the browser (docs/design/ui.md, Statistics): the banner that asks once, its
What is sent, Settings → Statistics, and the page switched off by the server's environment."""

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import state, telemetry

pytestmark = pytest.mark.ui


@pytest.fixture
def not_chosen(telemetry_on):
    """Sending possible (a local endpoint), the choice not made: the UI asks."""
    (state.home() / "telemetry" / "consent.json").unlink()


def test_the_banner_asks_once_and_settings_shows_the_choice(page: Page, not_chosen, server, shot):
    log_in(page, server)
    banner = page.get_by_role("region", name="Usage statistics")
    expect(banner).to_contain_text("Help improve LADO?")
    expect(banner).to_contain_text("Nothing is sent until you choose.")
    shot(page, "banner")
    banner.get_by_text("What is sent").click()
    expect(banner.locator("pre")).to_contain_text('"lado_daily"', timeout=30_000)
    shot(page, "what-is-sent")
    banner.get_by_role("button", name="Send statistics").click()
    expect(banner).to_have_count(0)
    assert telemetry.state().on
    page.get_by_role("link", name="Settings").click()
    page.get_by_role("navigation", name="Settings sections").get_by_role(
        "link", name="Statistics"
    ).click()
    section = page.get_by_role("region", name="Statistics")
    expect(section.get_by_role("radio", name="Send", exact=True)).to_be_checked()
    expect(section).to_contain_text("Not sent yet. What LADO collects ↗")
    shot(page, "settings")
    page.reload()
    expect(page.get_by_role("heading", name="Statistics")).to_be_visible()
    expect(page.locator(".stats-banner")).to_have_count(0)  # asked once


@pytest.fixture
def do_not_track(telemetry_on, monkeypatch):
    monkeypatch.setenv("DO_NOT_TRACK", "1")  # in the server's environment


def test_settings_is_disabled_when_the_environment_switches_it_off(
    page: Page, do_not_track, server, shot
):
    log_in(page, server)
    expect(page.get_by_role("button", name="System")).to_be_visible()
    expect(page.locator(".stats-banner")).to_have_count(0)
    page.goto(f"{server['url']}/settings/statistics")
    section = page.get_by_role("region", name="Statistics")
    expect(section).to_contain_text("Off: DO_NOT_TRACK=1 is set in the server's environment.")
    expect(section.get_by_role("radio", name="Don't send")).to_be_checked()
    expect(section.get_by_role("radio", name="Don't send")).to_be_disabled()
    shot(page, "settings-off")
    page.get_by_role("button", name="System").click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.get_by_role("link", name="off: DO_NOT_TRACK=1")).to_be_visible()
    shot(page, "panel")
