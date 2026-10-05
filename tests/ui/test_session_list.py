"""The session list's groups in a browser (docs/design/ui.md, Structure: Sessions): each
heading folds its group by a click, Enter or Space, remembered over a reload; the open
session is seen in its folded group; a row shows the session's card under the pointer."""

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime

pytestmark = pytest.mark.ui


def test_each_group_folds_by_its_heading_remembered_and_the_open_session_stays_in_sight(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.emulate_media(color_scheme="light")
    calm = running_session(repo)
    other = running_session(repo)
    asking = running_session(repo)
    old = running_session(repo)
    runtime.ask_human(asking, "supervisor", "Merge w1 now?", "Tests pass.", ["yes", "later"])
    runtime.stop_session(old)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{calm}")
    sessions = page.get_by_role("navigation", name="Sessions")
    running = sessions.get_by_role("region", name="Running")
    head = sessions.get_by_role("button", name="Running 2")
    expect(running.get_by_role("link", name=other)).to_be_visible()
    expect(sessions.get_by_role("button", name="Needs you 1")).to_have_attribute("aria-expanded", "true")
    expect(sessions.get_by_role("button", name="Stopped 1")).to_have_attribute("aria-expanded", "false")
    expect(sessions.get_by_role("region", name="Stopped").get_by_role("link")).to_have_count(0)
    shot(page, "light")

    head.click()
    expect(head).to_have_attribute("aria-expanded", "false")
    expect(running.get_by_role("link", name=other)).to_have_count(0)
    expect(running.get_by_role("link", name=calm)).to_be_visible()  # the open session
    shot(page, "running-folded")
    page.reload()
    expect(head).to_have_attribute("aria-expanded", "false")  # remembered
    expect(running.get_by_role("link", name=calm)).to_be_visible()
    expect(running.get_by_role("link", name=other)).to_have_count(0)

    head.focus()
    page.keyboard.press("Enter")
    expect(head).to_have_attribute("aria-expanded", "true")
    expect(running.get_by_role("link", name=other)).to_be_visible()
    page.keyboard.press("Space")
    expect(head).to_have_attribute("aria-expanded", "false")
    page.keyboard.press("Space")
    expect(head).to_have_attribute("aria-expanded", "true")

    page.emulate_media(color_scheme="dark")
    sessions.get_by_role("button", name="Stopped 1").click()
    expect(sessions.get_by_role("region", name="Stopped").get_by_role("link", name=old)).to_be_visible()
    shot(page, "dark")


def test_a_row_shows_its_sessions_card_under_the_pointer(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    calm = running_session(repo)
    old = running_session(repo)
    runtime.stop_session(old)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions")
    sessions = page.get_by_role("navigation", name="Sessions")
    sessions.get_by_role("link", name=calm).hover()
    card = page.get_by_role("tooltip")
    expect(card).to_contain_text(f"{calm} · running · 1 agent")
    expect(card).to_contain_text(str(repo))
    expect(card).to_contain_text("default · fake")
    shot(page, "running")

    sessions.get_by_role("button", name="Stopped 1").click()
    sessions.get_by_role("link", name=old).hover()
    expect(card).to_contain_text(f"{old} · stopped")
    expect(card).to_contain_text("Stopped: open it and press Resume")
    shot(page, "stopped")
