"""Settings → Providers and environment in a browser (openspec changes provider-logins,
provider-login-layers): an agent of the fake provider "fake-login" (fake_provider.py), which
logs in like Claude Code by a pasted token or key, waits for its CLI's login; Needs you leads
there with "Log in…"; the row's one button opens the sheet that asks how to log in, the
token pasted there reaches the waiting agent, and Log out asks first, naming it. "fake-window"
logs in by its own command, like OpenCode: its sheet is the login window, which runs the
fake CLI's login command, prints a link and reads a code sent with "Text to send". On a
computer and at a phone's width."""

import re
import time
import uuid

import agent_helpers
import fake_provider
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in

from lado import loop, project_secrets, runtime, state

pytestmark = pytest.mark.ui

TITLE = "Fake agent"  # the fake providers' title; "fake-login" alone has a login button
QUESTION = fake_provider.FakeLoginProvider.login_question


def waiting_session(repo, marker) -> str:
    """A session of "fake-login" resumed by LADO without its login (as lado update does): a
    new one or a resume by hand would be refused, LADO's own resume waits (openspec changes
    refuse-start-without-login, providers-section-and-start-screens)."""
    session = f"ui-{uuid.uuid4().hex[:6]}"
    marker.write_text("logged in")
    runtime.start_session(str(repo), session, None, "fake-login")
    runtime.stop_session(session)
    marker.unlink()
    runtime.start_session(str(repo), session, None, wait_for_login=True)
    assert state.get_agent(session, "supervisor").status == state.WAITING
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    return session


def row(page: Page):
    rows = page.get_by_role("listitem", name=TITLE)
    return rows.filter(has=page.get_by_role("button", name=re.compile("Log in…|Change login…")))


def idle(session: str) -> None:
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )


def test_a_waiting_agent_leads_to_the_sheet_and_starts_with_the_pasted_token(
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
    expect(fake.get_by_role("button")).to_have_count(1)  # one button, no field
    expect(fake.get_by_role("textbox")).to_have_count(0)
    section = page.get_by_role("region", name="Providers and environment")
    expect(
        section.get_by_text("Sign-ins your agents use. Changes apply to agents started afterwards.")
    ).to_be_visible()
    expect(section.get_by_role("button", name="Check the CLIs again")).to_be_visible()
    for gone in ("lado doctor", "Check again", "[ok]", "[warn]"):
        expect(section).not_to_contain_text(gone)
    shot(page, "section")

    fake.get_by_role("button", name="Log in…").click()
    sheet = page.get_by_role("dialog", name=QUESTION)
    expect(sheet.get_by_role("radio", name="A token")).to_be_checked()
    field = sheet.get_by_label(fake_provider.TOKEN)
    field.fill("canary-ui-token")
    # Shown as dots, as a project's secret is (the font LadoSecretDots).
    font = field.evaluate("e => getComputedStyle(e).fontFamily")
    assert "LadoSecretDots" in font, font
    shot(page, "sheet")
    sheet.get_by_role("button", name="Save").click()
    expect(sheet).to_have_count(0)
    expect(row(page).get_by_text("Logged in · token · LADO's secret")).to_be_visible()
    # Logged in, the row never says that an agent waits for this login (LAD-160's glitch),
    # also while the agent's window has not looked yet and the check after Save runs.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        text = row(page).inner_text()
        assert "Logged in" in text and "waits for this login" not in text, text
        time.sleep(0.1)
    idle(session)
    assert "canary-ui-token" not in page.content()
    row(page).scroll_into_view_if_needed()
    shot(page, "logged-in")

    # Log out asks first, naming the running agent, and removes the token.
    row(page).get_by_role("button", name="Change login…").click()
    sheet = page.get_by_role("dialog", name=QUESTION)
    expect(sheet.get_by_role("radio", name=re.compile("A token"))).to_be_checked()
    expect(sheet.get_by_text("current")).to_be_visible()
    sheet.get_by_role("button", name="Log out…").click()
    ask = sheet.get_by_role("group", name="Remove this login from LADO's secrets?")
    expect(ask).to_contain_text(f"supervisor of {session} keeps it until it starts again")
    shot(page, "log-out")
    ask.get_by_role("button", name="Log out", exact=True).click()
    expect(sheet).to_have_count(0)
    expect(row(page).get_by_text("Not logged in")).to_be_visible()
    assert project_secrets.lado_names() == []
    runtime.stop_session(session)


@pytest.fixture
def held(tmp_path, monkeypatch):
    """While this file exists, "fake-login"'s status command does not answer
    (fake_provider.py); set before `server`."""
    hold = tmp_path / "hold-login"
    monkeypatch.setenv("FAKE_AGENT_LOGIN_HOLD", str(hold))
    return hold


def test_the_section_shows_the_last_rows_at_once(page: Page, logins, held, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    held.write_text("")
    log_in(page, server)
    page.goto(f"{server['url']}/settings#providers-and-environment")
    section = page.get_by_role("region", name="Providers and environment")
    refresh = section.get_by_role("button", name="Check the CLIs again")
    # The first visit: each row as soon as its CLI answered; the held one says checking….
    fake = section.get_by_role("listitem", name=TITLE)
    expect(fake.filter(has_text="checking…")).to_have_count(1)
    expect(window_row(page).get_by_text("No login")).to_be_visible()
    expect(refresh).to_have_class(re.compile("spinning"))
    expect(refresh).to_have_attribute("title", "Checking the CLIs…")
    shot(page, "first-visit")
    held.unlink()
    expect(row(page).get_by_text("Not logged in")).to_be_visible()
    expect(refresh).not_to_have_class(re.compile("spinning"))
    # The next visit shows the last rows at once, while a fresh check runs.
    page.goto(f"{server['url']}/sessions")
    held.write_text("")
    page.goto(f"{server['url']}/settings#providers-and-environment")
    expect(refresh).to_have_class(re.compile("spinning"))
    expect(row(page).get_by_text("Not logged in")).to_be_visible()
    expect(fake.filter(has_text="checking…")).to_have_count(0)
    shot(page, "next-visit")
    held.unlink()
    expect(refresh).not_to_have_class(re.compile("spinning"))


def test_the_sheet_at_a_phones_width(browser: Browser, logins, server, repo, shot):
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
        sheet = page.get_by_role("dialog", name=QUESTION)
        box = sheet.locator(".login-window").bounding_box()
        assert box and box["width"] == 390  # the whole screen
        sheet.get_by_text("A key").click()
        sheet.get_by_label(fake_provider.KEY).fill("canary-ui-key")
        shot(page, "sheet", full_page=False)
        sheet.get_by_role("button", name="Save").click()
        expect(row(page).get_by_text("Logged in · key · LADO's secret")).to_be_visible()
        idle(session)
        assert project_secrets.lado_names() == [fake_provider.KEY]
        runtime.stop_session(session)
    finally:
        context.close()


def window_row(page: Page):
    return page.get_by_role("listitem", name="Fake window agent")


def log_in_from_the_window(page: Page, marker, shot, full_page: bool = True) -> None:
    sheet = page.get_by_role("dialog", name="Log in: Fake window agent")
    expect(sheet.get_by_label("Text to send")).to_be_visible()
    expect(sheet.locator(".xterm-rows")).to_contain_text("login.example.invalid", timeout=20000)
    expect(sheet.locator(".xterm-rows")).to_contain_text("Paste code here")
    shot(page, "window", full_page=full_page)
    sheet.get_by_label("Text to send").fill("code-42")
    sheet.get_by_role("button", name="Send ⏎").click()
    expect(sheet).to_have_count(0, timeout=20000)  # the command ended: the window closed
    assert marker.read_text() == "code-42"


def test_a_cli_with_its_own_login_command_opens_its_window(page: Page, logins, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/settings#providers-and-environment")
    expect(window_row(page).get_by_text("No login")).to_be_visible()
    window_row(page).get_by_role("button", name="Log in…").click()
    log_in_from_the_window(page, logins, shot)
    expect(
        window_row(page).get_by_text("Logged in · fake login · the fake CLI's login file")
    ).to_be_visible()
    expect(window_row(page).get_by_role("button", name="Change login…")).to_be_visible()
    window_row(page).scroll_into_view_if_needed()
    shot(page, "logged-in")


def test_the_login_window_at_a_phones_width(browser: Browser, logins, server, shot):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        log_in(page, server)
        page.goto(f"{server['url']}/settings#providers-and-environment")
        window_row(page).get_by_role("button", name="Log in…").click()
        sheet = page.get_by_role("dialog", name="Log in: Fake window agent")
        expect(sheet.get_by_label("Text to send")).to_be_visible()
        box = sheet.locator(".login-window").bounding_box()
        assert box and box["width"] == 390  # the whole screen
        for key in ("Up", "Down", "Enter", "Escape"):
            expect(sheet.get_by_role("button", name=key, exact=True)).to_be_visible()
        log_in_from_the_window(page, logins, shot, full_page=False)
    finally:
        context.close()
