"""Statistics in the browser (docs/design/ui.md, Statistics): the banner that asks once, its
What is sent, Settings → Statistics, and the page switched off by the server's environment."""

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import state, telemetry

pytestmark = pytest.mark.ui

NAME = "Send anonymous statistics and errors to LADO's maintainers"


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
    expect(section.get_by_role("switch", name=NAME)).to_be_checked()
    expect(section.get_by_role("radio")).to_have_count(0)
    expect(section).to_contain_text("Not sent yet. What LADO collects ↗")
    shot(page, "settings")
    page.reload()
    expect(page.get_by_role("heading", name="Statistics")).to_be_visible()
    expect(page.locator(".stats-banner")).to_have_count(0)  # asked once


def test_settings_not_chosen_is_off_and_turning_it_on_answers_the_banner(
    page: Page, not_chosen, server, shot
):
    log_in(page, server)
    banner = page.get_by_role("region", name="Usage statistics")
    expect(banner).to_be_visible()
    page.goto(f"{server['url']}/settings/statistics")
    section = page.get_by_role("region", name="Statistics", exact=True)
    switch = section.get_by_role("switch", name=NAME)
    expect(switch).not_to_be_checked()
    expect(switch).to_be_enabled()
    expect(section).to_contain_text("Nothing is sent until you choose. What LADO collects ↗")
    expect(banner).to_be_visible()  # off is not a choice: the banner still asks
    page.set_viewport_size({"width": 1440, "height": 900})
    shot(page, "not-chosen-1440", full_page=False)
    page.set_viewport_size({"width": 390, "height": 844})
    switch.scroll_into_view_if_needed()
    # Beside its name, not under it: the switch's middle within the row's text.
    beside = switch.evaluate(
        """(sw) => {
            const text = sw.closest('.srow').querySelector('.srow-text').getBoundingClientRect();
            const box = sw.getBoundingClientRect();
            const middle = box.top + box.height / 2;
            return box.left >= text.right && middle > text.top && middle < text.bottom;
        }"""
    )
    assert beside
    shot(page, "not-chosen-390", full_page=False)
    page.set_viewport_size({"width": 1440, "height": 900})
    switch.click()
    expect(switch).to_be_checked()
    assert telemetry.state().on
    page.reload()
    expect(page.get_by_role("heading", name="Statistics")).to_be_visible()
    expect(page.locator(".stats-banner")).to_have_count(0)
    section.get_by_role("switch", name=NAME).click()
    expect(section.get_by_role("switch", name=NAME)).not_to_be_checked()
    expect(section).to_contain_text("Nothing is sent. What LADO collects ↗")
    assert not telemetry.state().on


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
    expect(section.get_by_role("switch", name=NAME)).not_to_be_checked()
    expect(section.get_by_role("switch", name=NAME)).to_be_disabled()
    shot(page, "settings-off")
    page.get_by_role("button", name="System").click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.get_by_role("link", name="off: DO_NOT_TRACK=1")).to_be_visible()
    shot(page, "panel")
