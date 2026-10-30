"""Settings → Providers and environment in a browser (openspec change provider-logins): an
agent of the fake provider "fake-login" (fake_provider.py) waits for its CLI's login; Needs
you leads there with "Log in…"; the login window runs the fake CLI's login command, which
prints a link and reads a code sent with "Text to send"; the window closes, the row says
"Logged in" and the agent starts by itself. On a computer and at a phone's width."""

import re
import uuid

import agent_helpers
import fake_provider
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in

from lado import loop, runtime, state

pytestmark = pytest.mark.ui

TITLE = "Fake agent"  # the fake providers' title


def waiting_session(repo, marker) -> str:
    """A session of "fake-login" resumed without its login: a new one would be refused, a
    resumed one waits (openspec change refuse-start-without-login)."""
    session = f"ui-{uuid.uuid4().hex[:6]}"
    marker.write_text("logged in")
    runtime.start_session(str(repo), session, None, "fake-login")
    runtime.stop_session(session)
    marker.unlink()
    runtime.start_session(str(repo), session, None)
    assert state.get_agent(session, "supervisor").status == state.WAITING
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    return session


def row(page: Page, title: str = TITLE):
    # The fake providers share their title: the row of "fake-login" has a login action.
    rows = page.get_by_role("listitem", name=title)
    return rows.filter(has=page.get_by_role("button", name="Log in…"))


def log_in_from_the_window(page: Page, marker, shot, full_page: bool = True) -> None:
    sheet = page.get_by_role("dialog", name=f"Log in: {TITLE}")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".xterm-rows")).to_contain_text("login.example.invalid", timeout=20000)
    expect(sheet.locator(".xterm-rows")).to_contain_text("Paste code here")
    shot(page, "window", full_page=full_page)
    sheet.get_by_label("Text to send").fill("code-42")
    sheet.get_by_role("button", name="Send ⏎").click()
    expect(sheet).to_have_count(0, timeout=20000)  # the command ended: the window closed
    assert marker.read_text() == "code-42"


def test_a_waiting_agent_leads_to_the_login_and_starts_by_itself(
    page: Page, logins, server, repo, shot
):
    page.set_viewport_size({"width": 1280, "height": 900})
    session = waiting_session(repo, logins)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    group = page.get_by_role("region", name=f"Session {session}")
    expect(group.get_by_text(re.compile("is not logged in: log in in Settings"))).to_be_visible()
    shot(page, "needs-you")
    group.get_by_role("button", name="Log in for supervisor").click()
    expect(page).to_have_url(re.compile("/settings#providers-and-environment$"))
    fake = row(page)
    expect(fake.get_by_text("Not logged in")).to_be_visible()
    expect(fake.get_by_role("link", name=f"supervisor of {session}")).to_be_visible()
    section = page.get_by_role("region", name="Providers and environment")
    expect(section.get_by_role("list", name="lado doctor about the providers")).to_be_visible()
    shot(page, "section")

    fake.get_by_role("button", name="Log in…").click()
    log_in_from_the_window(page, logins, shot)
    expect(row(page).get_by_text("Logged in · fake login")).to_be_visible()
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    shot(page, "logged-in")
    runtime.stop_session(session)


def test_the_login_window_at_a_phones_width(browser: Browser, logins, server, repo, shot):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        session = waiting_session(repo, logins)
        log_in(page, server)
        page.goto(f"{server['url']}/settings#providers-and-environment")
        fake = row(page)
        expect(fake.get_by_text("Not logged in")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390  # no sideways scroll
        shot(page, "section", full_page=False)
        fake.get_by_role("button", name="Log in…").click()
        sheet = page.get_by_role("dialog", name=f"Log in: {TITLE}")
        expect(sheet).to_be_visible()
        box = sheet.locator(".login-window").bounding_box()
        assert box and box["width"] == 390  # the whole screen
        for key in ("Up", "Down", "Enter", "Escape"):
            expect(sheet.get_by_role("button", name=key, exact=True)).to_be_visible()
        log_in_from_the_window(page, logins, shot, full_page=False)
        agent_helpers.wait_for(
            lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
        )
        runtime.stop_session(session)
    finally:
        context.close()


def test_a_token_saved_on_the_page_reaches_the_waiting_agent(
    page: Page, logins, server, repo, shot
):
    page.set_viewport_size({"width": 1280, "height": 900})
    session = waiting_session(repo, logins)
    log_in(page, server)
    page.goto(f"{server['url']}/settings#providers-and-environment")
    fake = row(page)
    field = fake.get_by_label(fake_provider.TOKEN)
    field.fill("canary-ui-token")
    fake.get_by_role("button", name="Save").click()
    expect(fake.get_by_text("set · LADO's secret")).to_be_visible()
    expect(field).to_have_value("")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    assert "canary-ui-token" not in page.content()
    shot(page, "token")
    runtime.stop_session(session)
