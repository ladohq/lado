"""The session list's groups in a browser (docs/design/ui.md, Structure: Sessions): each
heading folds its group by a click, Enter or Space, remembered over a reload; the open
session is seen in its folded group; a row shows the session's card under the pointer, and
not when the focus comes back to it with the tab."""

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui


ERRORS = [
    "problem",
    "update-bad",
    "field-problem",
    "started-problems",
    "kit-problem",
    "market-error",
    "term-notice",
    "artifact-missing",
]
WARNINGS = ["problem share-warning", "kit-warning"]
SETTING_WARNINGS = ["pv-warn", "pv-none"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_a_notice_is_a_ground_and_an_icon_and_the_selected_session_keeps_its_stripe(
    page: Page, server, repo, shot, theme
):
    session = running_session(repo)
    log_in(page, server)
    page.emulate_media(color_scheme=theme)
    page.goto(f"{server['url']}/sessions/{session}")
    selected = page.get_by_role("navigation", name="Sessions").locator(
        ".session-link[aria-current='page']"
    )
    expect(selected).to_be_visible()
    assert selected.evaluate("row => getComputedStyle(row).boxShadow") != "none"
    # Each notice as the stylesheet draws it, beside the token it must wear.
    looks = page.evaluate(
        """([errors, warnings, inSetting]) => {
          const box = document.body.appendChild(document.createElement("div"));
          const setting = box.appendChild(document.createElement("div"));
          setting.className = "setting";
          const colour = (token) => {
            const probe = box.appendChild(document.createElement("i"));
            probe.style.background = `var(${token})`;
            return getComputedStyle(probe).backgroundColor;
          };
          const look = (classes, parent, ground, ink) => {
            const notice = parent.appendChild(document.createElement("p"));
            notice.className = classes;
            notice.textContent = "A notice";
            const style = getComputedStyle(notice);
            const icon = getComputedStyle(notice, "::before");
            return {
              classes,
              ground: style.backgroundColor === colour(ground),
              ink: style.color === colour(ink),
              stripe: style.borderLeftWidth,
              icon: icon.content !== "none" && icon.maskImage !== "none",
            };
          };
          return [
            ...errors.map((one) => look(one, box, "--danger-ground", "--danger")),
            ...warnings.map((one) => look(one, box, "--warn-ground", "--warn")),
            ...inSetting.map((one) => look(one, setting, "--warn-ground", "--warn")),
          ];
        }""",
        [ERRORS, WARNINGS, SETTING_WARNINGS],
    )
    assert len(looks) == len(ERRORS) + len(WARNINGS) + len(SETTING_WARNINGS)
    for look in looks:
        wanted = {"ground": True, "ink": True, "stripe": "0px", "icon": True}
        assert {key: look[key] for key in wanted} == wanted, look
    shot(page, f"notices-{theme}")


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
    expect(sessions.get_by_role("button", name="Needs you 1")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(sessions.get_by_role("button", name="Stopped 1")).to_have_attribute(
        "aria-expanded", "false"
    )
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
    expect(
        sessions.get_by_role("region", name="Stopped").get_by_role("link", name=old)
    ).to_be_visible()
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
    expect(card).to_contain_text(f"{calm} · running · idle · 1 agent")
    expect(card).to_contain_text("ran <1 min")
    expect(card).to_contain_text(str(repo))
    expect(card).to_contain_text("default · fake")
    shot(page, "running")

    sessions.get_by_role("button", name="Stopped 1").click()
    stopped = sessions.get_by_role("link", name=old)
    expect(stopped.locator(".session-about")).to_have_text("stopped <1 min ago · ran <1 min")
    stopped.hover()
    expect(card).to_contain_text(f"{old} · stopped")
    expect(card).to_contain_text("stopped <1 min ago · ran <1 min")
    expect(card).to_contain_text("Stopped: open it and press Resume")
    shot(page, "stopped")


@pytest.fixture
def tabs(browser_type, server, repo):
    """A session's row and a second tab, for real tab switches. In full Chromium with the
    focus emulation off: the default headless shell sends no blur or focus on a switch, and
    a test there passes with the defect in place (openspec tooltip-focus)."""
    browser = browser_type.launch(channel="chromium")
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    other = context.new_page()
    session = running_session(repo)
    page.bring_to_front()
    log_in(page, server)
    page.goto(f"{server['url']}/sessions")
    row = page.get_by_role("navigation", name="Sessions").get_by_role("link", name=session)
    expect(row).to_be_visible()
    for tab in (page, other):  # after the navigation, which brings the emulation back
        context.new_cdp_session(tab).send("Emulation.setFocusEmulationEnabled", {"enabled": False})
    yield page, other, row
    browser.close()


def wait_for_focus(page: Page, wanted: bool) -> None:
    # By asking, as a page in the background runs no wait_for_function's polling.
    for _ in range(200):
        if page.evaluate("document.hasFocus()") == wanted:
            return
        page.wait_for_timeout(50)
    pytest.fail(f"the page's document.hasFocus() never became {wanted}")


def away_and_back(page: Page, other: Page) -> None:
    other.bring_to_front()
    wait_for_focus(page, False)
    page.bring_to_front()
    wait_for_focus(page, True)
    page.wait_for_timeout(500)  # past the tooltip's delay: one that would show has shown


def test_a_clicked_row_shows_no_tooltip_when_the_focus_returns_with_the_tab(tabs, shot):
    page, other, row = tabs
    row.click()
    page.mouse.move(800, 600)
    card = page.get_by_role("tooltip")
    expect(card).to_have_count(0)
    away_and_back(page, other)
    expect(row).to_be_focused()
    expect(card).to_have_count(0)
    shot(page, "returned")


def test_a_clicked_row_and_a_key_show_no_tooltip_when_the_focus_returns_with_the_tab(tabs):
    page, other, row = tabs
    row.click()
    page.mouse.move(800, 600)
    page.keyboard.press("Shift")
    card = page.get_by_role("tooltip")
    expect(card).to_have_count(0)
    away_and_back(page, other)
    expect(row).to_be_focused()
    expect(card).to_have_count(0)


def test_a_keyboards_tooltip_goes_and_stays_away_when_the_focus_returns_with_the_tab(tabs):
    page, other, row = tabs
    row.focus()
    card = page.get_by_role("tooltip")
    expect(card).to_be_visible()
    away_and_back(page, other)
    expect(row).to_be_focused()
    expect(card).to_have_count(0)


def test_after_the_focus_returns_tab_and_back_shows_the_rows_tooltip(tabs):
    page, other, row = tabs
    row.focus()
    away_and_back(page, other)
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.keyboard.press("Tab")
    expect(row).not_to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(row).to_be_focused()
    expect(page.get_by_role("tooltip")).to_be_visible()


def test_after_the_focus_returns_the_pointer_shows_the_rows_tooltip(tabs):
    page, other, row = tabs
    row.focus()
    away_and_back(page, other)
    card = page.get_by_role("tooltip")
    expect(card).to_have_count(0)
    row.hover()
    expect(card).to_be_visible()


def test_a_running_row_says_whether_its_agents_work_and_follows_their_hooks(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.emulate_media(color_scheme="light", reduced_motion="no-preference")
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions")
    row = (
        page.get_by_role("navigation", name="Sessions")
        .get_by_role("region", name="Running")
        .get_by_role("link", name=session)
    )
    about = row.locator(".session-about")
    expect(row.get_by_role("img", name="idle")).to_be_visible()
    expect(about).to_have_text("1 agent · <1 min")

    runtime.write_as_human(session, "pause")  # the fake supervisor's turn goes on till released
    agent_helpers.wait_for(
        lambda: agent_helpers.paused(session, "supervisor", 1), "paused", session
    )
    working = row.get_by_role("img", name="working")
    expect(working).to_be_visible()
    expect(about).to_have_text("1 agent · <1 min")
    pulse = "e => getComputedStyle(e).animationName"
    assert working.evaluate(pulse) == "activity-pulse"
    page.emulate_media(reduced_motion="reduce")
    assert working.evaluate(pulse) == "none"
    shot(page, "working")

    agent_helpers.release(session, "supervisor", 1)
    expect(row.get_by_role("img", name="idle")).to_be_visible()
    expect(about).to_have_text("1 agent · <1 min")
    shot(page, "idle")

    page.get_by_role("button", name="Collapse sessions").click()
    icon = page.locator("nav.sessions-strip").get_by_role("link", name=f"{session}, idle")
    expect(icon.locator(".dot")).to_be_visible()
    shot(page, "strip")


def test_rename_from_the_row_menu_and_esc(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    titled = running_session(repo)
    plain = running_session(repo)
    runtime.set_title(titled, "Ревью kit-sdlc")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{plain}")
    sessions = page.get_by_role("navigation", name="Sessions")
    row = sessions.locator(".session-row").filter(has_text="Ревью kit-sdlc")
    expect(row.locator(".session-about")).to_contain_text(f"{titled} · ")
    expect(
        sessions.locator(".session-row").filter(has_text=plain).locator(".session-name")
    ).to_have_text(plain)
    page.get_by_role("searchbox", name="Find a session").fill("ревью")
    expect(sessions.locator(".session-row")).to_have_count(1)
    page.get_by_role("searchbox", name="Find a session").fill(titled)
    expect(sessions.locator(".session-row")).to_have_count(1)
    shot(page, "found-by-name")
    page.get_by_role("searchbox", name="Find a session").fill("")

    more = row.get_by_role("button", name=f"Actions for {titled}")
    row.hover()
    more.click()
    menu = page.get_by_role("menu", name=titled)
    expect(menu.get_by_role("menuitem")).to_have_text(["Rename…", "Copy link", "Open in new tab"])
    shot(page, "menu")
    menu.get_by_role("menuitem", name="Rename…").click()
    field = sessions.get_by_role("textbox", name="Session title")
    expect(field).to_be_focused()
    expect(field).to_have_value("Ревью kit-sdlc")
    field.fill("x")
    shot(page, "editing")
    field.press("Escape")
    expect(row.locator(".session-name")).to_have_text("Ревью kit-sdlc")
    expect(more).to_be_focused()
    assert state.get_session(titled).title == "Ревью kit-sdlc"

    more.click()
    page.get_by_role("menu", name=titled).get_by_role("menuitem", name="Rename…").click()
    field.fill("")
    field.press("Enter")
    cleared = sessions.locator(".session-row").filter(has_text=titled).first
    expect(cleared.locator(".session-name")).to_have_text(titled)
    expect(cleared.locator(".session-about")).not_to_contain_text(f"{titled} · ")
    assert state.get_session(titled).title is None
    shot(page, "cleared")


def test_tab_takes_the_rest_of_the_name_in_a_row(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    sessions = page.get_by_role("navigation", name="Sessions")
    row = sessions.locator(".session-row").filter(has_text=session)
    row.hover()
    row.get_by_role("button", name=f"Actions for {session}").click()
    page.get_by_role("menu", name=session).get_by_role("menuitem", name="Rename…").click()
    field = sessions.get_by_role("textbox", name="Session title")
    field.press_sequentially(session[:2])
    rest = sessions.locator(".title-edit-rest")
    expect(rest).to_have_text(session)
    expect(rest.locator(".title-edit-typed")).to_have_text(session[:2])
    expect(sessions.locator(".title-edit-hint")).to_have_text(
        f"{session} · Tab takes the name · Enter to save · Esc to cancel"
    )
    shot(page, "rest-of-the-name")
    field.press("Tab")
    expect(field).to_have_value(session)
    expect(field).to_be_focused()
    expect(rest).to_have_count(0)
    field.press_sequentially(" 2")
    field.press("Enter")
    expect(row.locator(".session-name")).to_have_text(f"{session} 2")
    assert state.get_session(session).title == f"{session} 2"
