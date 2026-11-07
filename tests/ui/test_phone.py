"""The phone layout in a browser (docs/design/ui.md, Phone layout; LAD-95): Chromium with a
touch screen (`is_mobile`, `has_touch`) upright at 390x844 and 360x780 and sideways at
844x390, and with a mouse at the same sizes, which must keep the computer's layout."""

import re

import agent_helpers
import pytest
from playwright.sync_api import Browser, Locator, Page, expect
from test_gates import LONG_NOTE, MEASURE_SCROLLERS, gated_session, recommended, waiting_card
from test_launch import stopped_session
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui

UPRIGHT = (390, 844)
NARROWEST = (360, 780)
SIDEWAYS = (844, 390)
MENU = re.compile(r"^Menu(, \d+ waiting)?$")  # not the rail's Collapse menu


@pytest.fixture
def device(browser: Browser):
    """A page of its own browser context: a touch screen (a phone, a tablet) or a mouse, at
    `width` x `height`."""
    contexts = []

    def make(size: tuple[int, int], touch: bool = True) -> Page:
        width, height = size
        context = browser.new_context(
            viewport={"width": width, "height": height}, is_mobile=touch, has_touch=touch
        )
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


def opened(page: Page, server, path: str) -> Page:
    log_in(page, server)
    page.goto(f"{server['url']}{path}")
    return page


def waiting_session(repo) -> str:
    """gated_session's gate #1 of ship/x, and a question of the supervisor's: two things wait."""
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Merge w1 now?", None, ["yes", "no"])
    return session


def top_bar(page: Page):
    return page.get_by_role("banner")


def menu(page: Page):
    return top_bar(page).get_by_role("button", name=MENU)


def rail(page: Page):
    return page.get_by_role("navigation", name="Sections", exact=True)


def box(locator) -> dict:
    found = locator.bounding_box()
    assert found is not None, locator
    return found


def no_sideways_scroll(page: Page) -> None:
    sizes = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert sizes[0] <= sizes[1], (page.url, sizes)


def wheel_to_the_end(page: Page, target: Locator) -> None:
    """Scroll as a finger does: the wheel over the page, which Chromium gives only to a box
    that scrolls (script scrolling moves a clipped box too, LAD-159), until `target` is
    within the window, the window itself not scrolled."""
    width, height = page.viewport_size["width"], page.viewport_size["height"]
    page.mouse.move(width / 2, height / 2)
    page.mouse.wheel(0, 5000)
    page.wait_for_function(
        "e => e.getBoundingClientRect().bottom <= window.innerHeight", arg=target.element_handle()
    )
    assert page.evaluate("window.scrollY") == 0


def keeps_the_computers_frame(page: Page) -> None:
    """None of the phone's frame (LAD-109): no variable of usePhoneViewport on <html>, and
    the app in the page's flow."""
    root = "getComputedStyle(document.documentElement).getPropertyValue('--phone-height')"
    assert page.evaluate(root) == ""
    assert page.locator(".app").evaluate("a => getComputedStyle(a).position") == "static"


# A computer and a tablet keep their layout


@pytest.mark.parametrize(
    "size", [(1280, 800), (800, 900), (1280, 400)], ids=lambda s: f"{s[0]}x{s[1]}"
)
def test_a_computer_keeps_its_layout(device, server, repo, shot, size):
    session = running_session(repo)
    page = opened(device(size, touch=False), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.phone") is None
    expect(rail(page)).to_be_visible()
    expect(page.get_by_role("button", name=MENU)).to_have_count(0)
    expect(top_bar(page).locator("h1 .session-chevron")).to_be_visible()  # the computer's line
    expect(
        page.get_by_role("navigation", name="Sessions", exact=True)
    ).to_be_visible()  # list or strip
    expect(page.get_by_role("complementary", name="Terminals")).to_be_visible()
    keeps_the_computers_frame(page)
    shot(page)


def test_the_phones_title_and_link_are_easy_to_tap(device, server, repo, shot):
    """Spec §9 and LAD-193: the title's target is the bar's height, the link's 44×33 by the
    gaps at its sides."""
    session = running_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    title = top_bar(page).locator("h1 button")
    expect(title).to_be_visible()
    assert box(title)["height"] == 44
    link = top_bar(page).locator(".system-button")
    target = box(link)
    assert (target["width"], target["height"]) == (33, 44)
    page.touchscreen.tap(target["x"] + target["width"] - 1, target["y"] + target["height"] / 2)
    expect(page.get_by_role("dialog", name="System")).to_be_visible()
    page.reload()
    expect(title).to_be_visible()
    page.touchscreen.tap(box(title)["x"] + 8, box(title)["y"] + 1)
    expect(page.get_by_role("dialog", name=session)).to_be_visible()


def test_the_phones_targets_have_their_sizes(device, server, repo, shot):
    """Spec §9's table, row by row."""
    session = gated_session(repo, LONG_NOTE)
    runtime.ask_human(session, "supervisor", "Which one?", None, ["yes", "no"])
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    panel = card.get_by_role("tabpanel")

    def high(locator) -> int:
        return round(box(locator)["height"])

    expect(panel.get_by_role("button", name="Approve", exact=True)).to_be_visible()
    gate = {
        "Approve": panel.get_by_role("button", name="Approve", exact=True),
        "Reject": panel.get_by_role("button", name="Reject", exact=True),
        "Stop": top_bar(page).get_by_role("button", name=re.compile("^Stop")),
        "Menu": menu(page),
        "Minimize": card.get_by_role("button", name="Minimize the card"),
        "Expand": card.get_by_role("button", name="Expand the card"),
        "tab": card.get_by_role("tab").first,
        "comment": panel.locator(".answer-box").first,
    }
    assert {name: high(one) for name, one in gate.items()} == dict.fromkeys(gate, 44)
    for name in ("Stop", "Menu", "Minimize", "Expand"):
        assert round(box(gate[name])["width"]) == 44, name
    toggle = box(page.get_by_role("button", name="Messages between agents"))
    assert (toggle["width"], toggle["height"]) == (36, 36)
    # As they are: not the main action, past WCAG's 24 px.
    assert high(page.get_by_role("group", name="Team").get_by_role("button").first) >= 24
    tabs = page.get_by_role("navigation", name="Session sections")
    assert high(tabs.get_by_role("link").first) >= 24
    assert high(card.locator(".waiting-more")) == 24
    shot(page, "gate", full_page=False)

    card.get_by_role("tab", name="supervisor 1").click()
    question = {
        "Send answer": panel.get_by_role("button", name="Send answer to supervisor"),
        "Skip question": panel.get_by_role("button", name="Skip question"),
        "choice": panel.get_by_role("button", name="yes", exact=True),
    }
    expect(question["Skip question"]).to_be_visible()
    assert {name: high(one) for name, one in question.items()} == dict.fromkeys(question, 44)

    card.get_by_role("button", name="Minimize the card").tap()
    send = page.get_by_role("button", name="Send", exact=True)
    expect(send).to_be_visible()
    assert high(send) == 44


def test_a_narrow_window_with_a_mouse_is_a_phone(device, server, repo, shot):
    session = running_session(repo)
    page = opened(device(UPRIGHT, touch=False), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.phone") == "tall"
    expect(page.get_by_role("button", name=MENU)).to_be_visible()
    expect(top_bar(page).locator("h1")).to_contain_text(session)
    shot(page, full_page=False)


@pytest.mark.parametrize("size", [(768, 1024), (820, 1180), (1024, 768), (1440, 900)], ids=str)
def test_a_tablet_and_a_touch_laptop_keep_their_layout(device, server, repo, shot, size):
    session = running_session(repo)
    page = opened(device(size), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.phone") is None
    expect(rail(page)).to_be_visible()
    expect(page.get_by_role("button", name=MENU)).to_have_count(0)
    shot(page, full_page=False)


def test_a_tablets_page_is_as_high_as_the_part_of_the_window_it_sees(device, server, repo):
    """The page stands still, so its height is what brings the composer above the keyboard."""
    session = running_session(repo)
    page = opened(device((768, 1024)), server, f"/sessions/{session}")
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    assert page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--phone-height')"
    ) == ("1024px")
    page.evaluate(
        "document.documentElement.style.setProperty('--phone-height', '600px')"
    )  # the keyboard opens
    assert page.locator(".app").bounding_box()["height"] == 600
    composer = page.get_by_role("textbox", name="Write to the supervisor…").bounding_box()
    assert composer["y"] + composer["height"] <= 600


@pytest.mark.parametrize("size", [(1180, 734), (1032, 1366)], ids=str)
def test_a_wide_touch_screens_app_is_as_high_as_the_part_it_sees(device, server, repo, shot, size):
    """iPad check of PR #224: wider than 900 px the app was 100dvh, taller than the visible part
    on iPadOS Safari, so the card's buttons and the composer lay under its bars."""
    width, height = size
    session = gated_session(repo)
    page = opened(device(size), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    approve = card.get_by_role("button", name="Approve", exact=True)
    expect(approve).to_be_visible()
    variable = "getComputedStyle(document.documentElement).getPropertyValue('--phone-height')"
    assert page.evaluate(variable) == f"{height}px"
    seen = height - 46  # Safari's bar
    page.evaluate(f"document.documentElement.style.setProperty('--phone-height', '{seen}px')")
    assert box(page.locator(".app"))["height"] == seen
    field = box(page.get_by_role("textbox", name=re.compile("^Write to")))
    assert field["y"] + field["height"] <= seen
    assert box(approve)["y"] + box(approve)["height"] <= seen
    shot(page, full_page=False)


def test_with_the_keyboard_open_on_a_wide_touch_screen_the_card_stays_in_sight(
    device, server, repo, shot
):
    """iPad landscape, keyboard open: 312 px of the window are left."""
    session = gated_session(repo)
    page = opened(device((1180, 734)), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    expect(comment).to_be_visible()
    comment.tap()
    page.evaluate("document.documentElement.style.setProperty('--phone-height', '312px')")
    for part in (comment, card.get_by_role("button", name="Approve", exact=True)):
        expect(part).to_be_visible()
        assert box(part)["y"] + box(part)["height"] <= 312, part
    shot(page, full_page=False)


def test_a_wide_touch_screens_other_pages_scroll_inside_the_app(device, server, repo):
    gated_session(repo, LONG_NOTE)
    page = opened(device((1180, 734)), server, "/needs-you")
    expect(top_bar(page).locator("h1")).to_have_text("Needs you")
    page.evaluate("document.documentElement.style.setProperty('--phone-height', '500px')")
    assert box(page.locator(".app"))["height"] == 500
    content = page.locator(".content")
    expect(content.get_by_role("region").first).to_be_visible()
    assert content.evaluate("c => c.scrollHeight > c.clientHeight")
    content.evaluate("c => { c.scrollTop = 100; }")
    assert content.evaluate("c => c.scrollTop") == 100


def test_a_wide_touch_screens_rail_ends_with_the_part_it_sees(device, server, repo, shot):
    """iPad held sideways (LAD-226): the rail stayed 100vh, taller than the visible part, and
    Report a bug and Settings lay under the screen's bottom edge, on every page."""
    session = running_session(repo)
    page = opened(device((1180, 688)), server, f"/sessions/{session}")
    for path in (f"/sessions/{session}", "/needs-you"):
        page.goto(f"{server['url']}{path}")
        settings = rail(page).get_by_role("link", name="Settings")
        expect(settings).to_be_visible()
        page.evaluate("document.documentElement.style.setProperty('--phone-height', '560px')")
        assert box(rail(page))["height"] == 560, path
        assert box(settings)["y"] + box(settings)["height"] <= 560, path
    shot(page, full_page=False)


def test_a_computers_rail_is_as_high_as_the_window(device, server):
    page = opened(device((1280, 800), touch=False), server, "/needs-you")
    expect(rail(page)).to_be_visible()
    assert box(rail(page))["height"] == 800


def test_an_upright_tablets_rail_is_as_high_as_the_part_it_sees(device, server, repo):
    session = running_session(repo)
    page = opened(device((820, 1180)), server, f"/sessions/{session}")
    expect(rail(page)).to_be_visible()
    page.evaluate("document.documentElement.style.setProperty('--phone-height', '600px')")
    assert box(rail(page))["height"] == 600


def test_a_computer_of_a_tablets_width_keeps_the_windows_height(device, server, repo):
    session = running_session(repo)
    page = opened(device((1180, 734), touch=False), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    keeps_the_computers_frame(page)


def test_a_tablet_elsewhere_keeps_the_computers_frame(device, server):
    page = opened(device((768, 1024)), server, "/needs-you")
    expect(page.get_by_role("banner").locator("h1")).to_have_text("Needs you")
    assert page.locator(".app").evaluate("a => getComputedStyle(a).position") == "static"


# The Resume window


@pytest.mark.parametrize(
    "folder",
    ["clients/acme-corporation/services/platform/backend-monolith-2026", "x" * 80],
    ids=["deep", "no-break"],
)
def test_the_resume_window_shows_a_long_folder_whole(device, server, tmp_path, shot, folder):
    """On an iPhone Where cut a long path at the field's edge (LAD-226): nothing may be cut."""
    repo = agent_helpers.init_repo(tmp_path / folder)
    session = stopped_session(repo)
    page = opened(device((402, 874)), server, f"/sessions/{session}")
    page.locator(".stopped-bar").get_by_role("button", name="Resume session").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    where = dialog.get_by_role("group", name="Where")
    expect(where).to_have_text(str(repo))
    assert box(where)["height"] > 38
    assert box(where)["x"] + box(where)["width"] <= 402
    assert where.evaluate("w => w.scrollWidth === w.clientWidth")
    no_sideways_scroll(page)
    shot(page, folder[:4], full_page=False)


# The menu


def test_the_menu_opens_the_rail_and_closes(device, server, repo, shot):
    session = waiting_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    assert page.evaluate("document.documentElement.dataset.phone") == "tall"
    expect(rail(page)).to_be_hidden()
    button = menu(page)
    expect(button).to_have_accessible_name("Menu, 2 waiting")
    expect(button).to_contain_text("2")
    shot(page, "closed", full_page=False)

    button.tap()
    expect(rail(page)).to_be_visible()
    expect(rail(page).get_by_role("link", name="Kits")).to_contain_text("Kits")  # with its name
    assert box(rail(page))["x"] == 0
    shot(page, "open", full_page=False)
    rail(page).get_by_role("link", name="Kits").tap()
    expect(page).to_have_url(f"{server['url']}/kits")
    expect(rail(page)).to_be_hidden()

    button.tap()
    expect(rail(page)).to_be_visible()
    page.keyboard.press("Escape")
    expect(rail(page)).to_be_hidden()
    expect(button).to_be_focused()

    button.tap()
    expect(rail(page)).to_be_visible()
    page.touchscreen.tap(UPRIGHT[0] - 20, UPRIGHT[1] // 2)  # the dimmed page beside it
    expect(rail(page)).to_be_hidden()
    expect(page).to_have_url(f"{server['url']}/kits")


# The top bar and the session's details


def test_the_top_bar_is_one_line_and_the_name_opens_the_details(device, server, repo, shot):
    session = gated_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    bar = top_bar(page)
    name = bar.get_by_role("button", name=session)
    expect(name).to_be_visible()
    # The session waits at a gate: the bar's dot is the list's mark, not "running".
    dot = bar.get_by_role("img", name="needs you · 1 gate")
    expect(dot).to_be_visible()
    expect(dot).to_have_class(re.compile(r"\bdot-waiting\b"))
    expect(bar.get_by_role("button", name="Stop session…")).to_be_visible()
    expect(bar.get_by_role("button", name="System")).to_be_visible()
    expect(bar.get_by_role("button", name="Copy path")).to_have_count(0)
    assert box(bar)["height"] <= 52
    for button in (menu(page), bar.get_by_role("button", name="Stop session…")):
        assert (box(button)["width"], box(button)["height"]) == (44, 44)
    expect(bar.locator(".session-action-word")).to_be_hidden()
    tops = [
        box(one)["y"] for one in (menu(page), name, bar.get_by_role("button", name="Stop session…"))
    ]
    assert max(tops) - min(tops) < 12, tops  # one line
    mark, line = box(dot), box(bar)
    assert line["y"] <= mark["y"] and mark["y"] + mark["height"] <= line["y"] + line["height"]
    shot(page, "bar", full_page=False)
    dot.tap()  # the mark's words, which the bar has no room for
    expect(page.get_by_role("tooltip")).to_have_text("needs you · 1 gate")
    shot(page, "mark", full_page=False)

    expect(name.locator(".session-chevron svg")).to_be_visible()  # it says the title opens
    name.tap()
    sheet = page.get_by_role("dialog", name=session)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".session-details-state")).to_contain_text(
        re.compile(r"^needs you · 1 gate · ")
    )
    expect(sheet).to_contain_text(str(repo))  # the whole folder
    expect(sheet).to_contain_text("uiflow 1.0.0")
    expect(sheet).to_contain_text("fake")
    for button in ("Rename", "Copy path", "Copy link"):
        expect(sheet.get_by_role("button", name=button)).to_be_visible()
    assert box(sheet.get_by_role("button", name="Copy path"))["height"] == 44
    # The whole folder wraps inside its cell, under no button.
    folder, copy = box(sheet.locator("dd code")), box(sheet.locator(".session-details-copy").first)
    assert folder["x"] + folder["width"] <= copy["x"] + 1, (folder, copy)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    sheet.get_by_role("button", name="Copy path").tap()
    expect(sheet.get_by_role("status").filter(has_text="Path copied")).to_be_in_viewport(ratio=1)
    expect(bar.locator("h1")).to_have_css("font-size", "17px")  # the phone's head as it was
    expect(sheet.get_by_role("link", name="All sessions")).to_be_visible()
    sheet_box = box(sheet)
    assert sheet_box["y"] + sheet_box["height"] >= UPRIGHT[1] - 1  # at the bottom
    shot(page, "details", full_page=False)

    sheet.get_by_role("button", name="Rename").tap()
    field = page.get_by_role("textbox", name="Session title")
    field.fill("Phone layout")
    field.press("Enter")
    expect(top_bar(page).get_by_role("button", name="Phone layout")).to_be_visible()
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    shot(page, "renamed", full_page=False)


# Sessions


def test_the_sessions_page_is_the_list(device, server, repo, shot):
    session = running_session(repo)
    page = opened(device(UPRIGHT), server, "/sessions")
    sessions = page.get_by_role("navigation", name="Sessions", exact=True)
    row = sessions.get_by_role("link", name=session)
    expect(row).to_be_visible()
    assert box(page.locator(".session-list"))["width"] >= UPRIGHT[0] - 1
    shot(page, "list", full_page=False)
    row.tap()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    expect(page.get_by_role("navigation", name="Sessions", exact=True)).to_have_count(0)  # no strip
    assert page.evaluate("localStorage.getItem('lado.sessionsList')") is None
    shot(page, "session", full_page=False)


def test_phone_forget_stopped(device, server, repo, shot):
    session = running_session(repo)
    runtime.stop_session(session)
    page = opened(device(UPRIGHT), server, "/sessions")
    band = (
        page.get_by_role("navigation", name="Sessions", exact=True)
        .get_by_role("region", name="Stopped")
        .locator("h3")
    )
    action = band.get_by_role("button", name="Forget stopped sessions…")
    expect(action).to_be_visible()
    shot(page, "band", full_page=False)
    action.tap()
    asked = page.get_by_role("dialog", name="Forget stopped sessions?")
    expect(asked.get_by_role("button", name="Forget 1 session")).to_be_enabled()
    no_sideways_scroll(page)
    shot(page, "window", full_page=False)
    asked.get_by_role("button", name="Cancel").tap()
    expect(asked).to_have_count(0)


# Tabs


def test_four_tabs_fit_360(device, server, repo, shot):
    session = gated_session(repo)
    page = opened(device(NARROWEST), server, f"/sessions/{session}")
    tabs = page.get_by_role("navigation", name="Session sections").get_by_role("link")
    expect(tabs).to_have_count(4)
    expect(tabs.last).to_contain_text("Artifacts")
    for at in range(4):
        found = box(tabs.nth(at))
        assert found["x"] >= 0 and found["x"] + found["width"] <= NARROWEST[0], (at, found)
    shot(page, full_page=False)


@pytest.mark.parametrize("size", [SIDEWAYS, (568, 320)], ids=["844x390", "568x320"])
def test_sideways_the_toggle_ends_the_tab_row_and_shows_the_agents_messages(
    device, server, repo, shot, size
):
    session = running_session(repo)
    runtime.spawn_worker(session, "Build it", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    runtime.send_message(session, "supervisor", "w1", "please review the branch")
    page = opened(device(size), server, f"/sessions/{session}")
    row = page.get_by_role("navigation", name="Session sections")
    tabs = row.get_by_role("link")
    toggle = row.get_by_role("button", name="Messages between agents")
    expect(toggle).to_be_visible()
    expect(page.get_by_role("button", name="Messages between agents")).to_have_count(1)
    found, last = box(toggle), box(tabs.last)
    assert found["height"] >= 36
    assert found["x"] >= last["x"] + last["width"]
    assert found["x"] + found["width"] <= size[0]
    for at in range(4):
        tab = box(tabs.nth(at))
        assert tab["x"] >= 0 and tab["x"] + tab["width"] <= found["x"], (at, tab)
    shot(page, "yours", full_page=False)
    feed = page.get_by_role("log", name="Chat with the session")
    between = feed.get_by_role("article", name="Message from supervisor to w1")
    expect(between).to_have_count(0)
    toggle.tap()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(between).to_be_visible()
    shot(page, "all", full_page=False)
    tabs.nth(1).tap()
    expect(tabs.nth(1)).to_have_attribute("aria-current", "page")
    expect(toggle).to_have_count(0)


def test_the_kits_tabs_fit_360(device, server, shot):
    page = opened(device(NARROWEST), server, "/kits")
    tabs = page.get_by_role("navigation", name="Kits").get_by_role("link")
    expect(tabs).to_have_count(3)
    for at in range(3):
        found = box(tabs.nth(at))
        assert found["x"] >= 0 and found["x"] + found["width"] <= NARROWEST[0], (at, found)
    shot(page, full_page=False)


# The chat


def test_the_composer_stays_at_the_bottom_with_a_gate_waiting(device, server, repo, shot):
    session = waiting_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    expect(card.get_by_role("tab")).to_have_count(2)
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_be_visible()
    assert page.evaluate("document.scrollingElement.scrollHeight <= window.innerHeight")
    composer = box(page.locator(".chat > .composer"))
    assert composer["y"] + composer["height"] <= UPRIGHT[1]
    assert composer["y"] + composer["height"] >= UPRIGHT[1] - 40, composer  # at the bottom
    chat = box(page.get_by_role("region", name="Chat"))
    assert box(card.locator(".waiting-top"))["height"] <= chat["height"] * 0.4 + 1
    within(card.locator(".waiting-foot"), 0, UPRIGHT[1])
    assert page.locator(".chat-feed").evaluate("f => getComputedStyle(f).overflowY") == "auto"
    expect(page.locator(".composer-keys")).to_be_hidden()
    expect(page.locator(".composer-to")).to_have_count(0)
    expect(page.locator(".composer-meta")).to_be_hidden()  # no empty line
    assert field.evaluate("f => getComputedStyle(f).fontSize") == "16px"
    shot(page, full_page=False)


# The visible part of the window (LAD-109): what the browser's bars and the keyboard leave.

# window.visualViewport replaced by one the test moves, as the keyboard or a browser's bar
# would: `moveViewport(height, top)` sets it and dispatches resize and scroll.
FAKE_VIEWPORT = """(() => {
  const fake = new EventTarget();
  let height = null;
  let top = 0;
  Object.defineProperties(fake, {
    height: { get: () => height ?? window.innerHeight },
    width: { get: () => window.innerWidth },
    offsetTop: { get: () => top },
    offsetLeft: { value: 0 },
    scale: { value: 1 },
  });
  Object.defineProperty(window, "visualViewport", { configurable: true, get: () => fake });
  window.moveViewport = (newHeight, newTop) => {
    height = newHeight;
    top = newTop;
    fake.dispatchEvent(new Event("resize"));
    fake.dispatchEvent(new Event("scroll"));
  };
})()"""


def question_session(repo) -> str:
    """gated_session's gate, and a long question of the supervisor's, its list scrolling."""
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Merge w1 now?", "Long details.\n" * 30, ["yes", "no"])
    return session


def question_tab(page: Page, session: str):
    """The waiting card on the supervisor's question, and its Send button."""
    card = waiting_card(page, session)
    card.get_by_role("tab", name="supervisor 1").tap()
    send = card.get_by_role("tabpanel").get_by_role("button", name="Send answer to supervisor")
    expect(send).to_be_visible()
    return card, send


def within(locator, top: float, bottom: float) -> None:
    found = box(locator)
    assert found["y"] >= top - 1 and found["y"] + found["height"] <= bottom + 1, (
        locator,
        found,
        top,
        bottom,
    )


def test_the_composer_and_the_send_button_are_in_sight(device, server, repo, shot):
    """AC-1: the composer and the card's Send button lie within the visible part of the
    window without scrolling, also with the card expanded."""
    session = question_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    visible = page.evaluate("window.visualViewport.height")
    composer = page.locator(".chat > .composer")
    within(composer, 0, visible)
    within(send, 0, visible)
    shot(page, "question", full_page=False)
    card.get_by_role("button", name="Expand the card").tap()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    within(send, 0, visible)
    shot(page, "expanded", full_page=False)


def test_the_app_shrinks_to_the_visible_part_and_grows_back(device, server, repo, shot):
    """AC-2: with the visible part 300 px lower than the window (the keyboard), the app ends
    at its bottom, the top bar stays at its top, the composer and Send within it, the card's
    title and context at most 40 % of the chat; when it grows back, the app does too."""
    session = question_session(repo)
    phone = device(UPRIGHT)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    app = page.locator(".app")
    assert abs(box(app)["height"] - UPRIGHT[1]) <= 1

    shrunk = UPRIGHT[1] - 300
    page.evaluate(f"window.moveViewport({shrunk}, 0)")
    expect(app).to_have_css("height", f"{shrunk}px")
    found = box(app)
    assert abs(found["y"] + found["height"] - shrunk) <= 1, found
    assert abs(box(top_bar(page))["y"]) <= 1
    within(page.locator(".chat > .composer"), 0, shrunk)
    within(send, 0, shrunk)
    chat = box(page.get_by_role("region", name="Chat"))["height"]
    assert box(card.locator(".waiting-top"))["height"] <= chat * 0.4 + 1
    assert page.evaluate("document.documentElement.style.getPropertyValue('--phone-height')") == (
        f"{shrunk}px"
    )
    shot(page, "shrunk", full_page=False)

    page.evaluate(f"window.moveViewport({UPRIGHT[1]}, 0)")
    expect(app).to_have_css("height", f"{UPRIGHT[1]}px")
    within(page.locator(".chat > .composer"), 0, UPRIGHT[1])


def test_the_app_follows_safaris_pan(device, server, repo, shot):
    """AC-2: Safari pans the page 120 px up under its keyboard; the app moves down with the
    visible part, so the top bar stays at its top."""
    session = question_session(repo)
    phone = device(UPRIGHT)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    _, send = question_tab(page, session)
    shrunk = UPRIGHT[1] - 300
    page.evaluate(f"window.moveViewport({shrunk}, 120)")
    expect(page.locator(".app")).to_have_css("top", "120px")
    assert abs(box(top_bar(page))["y"] - 120) <= 1
    within(page.locator(".chat > .composer"), 120, 120 + shrunk)
    within(send, 120, 120 + shrunk)
    shot(page, full_page=False)


# A field of the card above the keyboard: the keyboard leaves 440 px of 874 visible (frame
# g3-390-kbd); an imitation, a real keyboard stays to be checked on a device.

KEYBOARD = (402, 874)
ABOVE_KEYBOARD = 440


def session_around_card_hidden(page: Page, hidden: bool) -> None:
    """The session's tabs and the Team row, hidden while the card is expanded on a phone."""
    for part in (
        page.get_by_role("navigation", name="Session sections"),
        page.get_by_role("group", name="Team"),
    ):
        (expect(part).to_be_hidden if hidden else expect(part).to_be_visible)()


def uncut(card, part) -> None:
    """The panel clips what goes past it: a part within the window may still be cut."""
    panel = box(card.get_by_role("tabpanel"))
    within(part, panel["y"], panel["y"] + panel["height"])


def typing_around_card(page: Page, card, typing: bool) -> None:
    """A field in focus hides the session's tabs, the Team row and the context."""
    session_around_card_hidden(page, typing)
    context = card.get_by_role("region", name="Context of the card")
    (expect(context).to_be_hidden if typing else expect(context).to_be_visible)()


@pytest.mark.parametrize("visible", [ABOVE_KEYBOARD, 380, 350])
def test_a_gates_comment_stays_above_the_keyboard_and_folds_what_is_around(
    device, server, repo, shot, visible
):
    """A tap on the gate's comment does not expand the card: the session's tabs, the Team row
    and the context go, the composer folds into a line, and the field and Approve / Reject
    stay in sight, a recommendation of two lines over them; the keyboard closed, it all comes
    back, the comment kept."""
    session = gated_session(repo)
    recommended(session, "A reason to approve. " * 40, choice="approve")  # two lines
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    typing_around_card(page, card, False)
    comment.tap()
    expect(comment).to_be_focused()
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    page.evaluate(f"window.moveViewport({visible}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{visible}px")
    typing_around_card(page, card, True)
    line = page.locator(".composer-fold")
    expect(line).to_have_text("Commenting on gate #1 above")
    comment.fill("check the migration")
    for part in (
        comment,
        card.get_by_role("button", name="Approve", exact=True),
        card.get_by_role("button", name="Reject", exact=True),
        line,
    ):
        within(part, 0, visible)
    uncut(card, card.get_by_role("button", name="Approve", exact=True))
    uncut(card, comment)
    shot(page, "keyboard", full_page=False)

    page.evaluate(f"window.moveViewport({KEYBOARD[1]}, 0)")  # the keyboard closes
    expect(page.locator(".app")).to_have_css("height", f"{KEYBOARD[1]}px")
    comment.blur()
    typing_around_card(page, card, False)
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    expect(comment).to_have_value("check the migration")
    shot(page, "closed", full_page=False)


def test_an_own_answer_stays_above_the_keyboard(device, server, repo, shot):
    """A tap on Other… focuses its field; the field, Send and the composer's line are in sight
    with the keyboard's 440 px, the card not expanded."""
    session = question_session(repo)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    card.get_by_role("button", name="Other…").tap()
    own = card.get_by_role("textbox", name="Your own answer")
    expect(own).to_be_focused()
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    page.evaluate(f"window.moveViewport({ABOVE_KEYBOARD}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{ABOVE_KEYBOARD}px")
    typing_around_card(page, card, True)
    line = page.locator(".composer-fold")
    expect(line).to_contain_text("Answering question #")
    within(own, 0, ABOVE_KEYBOARD)
    within(send, 0, ABOVE_KEYBOARD)
    within(line, 0, ABOVE_KEYBOARD)
    shot(page, full_page=False)


def test_a_tap_on_approve_with_the_field_in_focus_answers_the_gate(device, server, repo):
    """The field losing the focus to the tap brings the context back: the tap still lands."""
    session = gated_session(repo)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("textbox", name="Comment for the next step (optional)").tap()
    page.evaluate(f"window.moveViewport({ABOVE_KEYBOARD}, 0)")
    expect(page.locator(".composer-fold")).to_be_visible()
    card.get_by_role("button", name="Approve").tap()
    expect(card).to_have_count(0)


def test_a_long_note_scrolls_in_the_context_and_the_footer_stays_on_a_phone(
    device, server, repo, shot
):
    """F14 at 390: the recommendation, the comment field and the buttons are in sight, the
    composer under them, and only the context scrolls."""
    session = gated_session(repo, LONG_NOTE)
    recommended(session, "Approve: the plan holds.", choice="approve")
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    panel = card.get_by_role("tabpanel")
    expect(panel.get_by_role("region", name="Supervisor's recommendation")).to_contain_text(
        "Supervisor recommends Approve:"
    )
    for part in (
        panel.get_by_role("region", name="Supervisor's recommendation"),
        panel.get_by_role("textbox", name="Comment for the next step (optional)"),
        panel.get_by_role("button", name="Approve", exact=True),
        panel.get_by_role("button", name="Reject", exact=True),
    ):
        within(part, 0, UPRIGHT[1])
    assert panel.evaluate(MEASURE_SCROLLERS) == {"context": True, "panel": 0, "foot": False}
    shot(page, full_page=False)


def test_a_long_recommendation_opens_to_three_lines_that_scroll(device, server, repo, shot):
    """Cut on 2 lines; a tap opens it to 3 lines, and the rest scrolls inside them."""
    session = gated_session(repo)
    recommended(session, "A reason to approve. " * 40, choice="approve")
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    block = waiting_card(page, session).get_by_role("region", name="Supervisor's recommendation")
    line = block.get_by_role("button")
    expect(line).to_be_visible()
    assert box(line)["height"] <= 2 * 21 + 1
    shot(page, "cut", full_page=False)
    line.tap()
    body = block.locator(".rec-bar-body")
    expect(body).to_be_visible()
    assert body.evaluate(
        "b => b.clientHeight <= 3 * parseFloat(getComputedStyle(b).lineHeight) + 1"
    )
    assert body.evaluate("b => b.scrollHeight > b.clientHeight")
    shot(page, "opened", full_page=False)


def test_an_opened_recommendation_fades_until_its_end(device, server, repo, shot):
    """Opened, a text longer than its 3 lines fades at the lower edge until it is scrolled to
    its end, and again when it scrolls back; one that fits does not fade."""
    session = gated_session(repo)
    recommended(session, "A reason to approve. " * 40, choice="approve")
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    block = waiting_card(page, session).get_by_role("region", name="Supervisor's recommendation")
    block.get_by_role("button").tap()
    frame = block.locator(".rec-bar-frame")
    cut = re.compile(r"\bcut\b")
    expect(frame).to_have_class(cut)
    assert frame.evaluate("f => getComputedStyle(f, '::after').content") != "none"
    shot(page, "fades", full_page=False)
    body = frame.locator(".rec-bar-body")
    body.evaluate("b => { b.scrollTop = b.scrollHeight; }")
    expect(frame).not_to_have_class(cut)
    assert frame.evaluate("f => getComputedStyle(f, '::after').content") == "none"
    shot(page, "at-its-end", full_page=False)
    body.evaluate("b => { b.scrollTop = 0; }")
    expect(frame).to_have_class(cut)


def test_a_short_opened_recommendation_does_not_fade(device, server, repo):
    session = gated_session(repo)
    recommended(session, "A short reason.", choice="approve")
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    block = waiting_card(page, session).get_by_role("region", name="Supervisor's recommendation")
    block.get_by_role("button").tap()
    expect(block.locator(".rec-bar-body")).to_be_visible()
    expect(block.locator(".rec-bar-frame")).not_to_have_class(re.compile(r"\bcut\b"))


@pytest.mark.parametrize("visible", [350, 340])
def test_six_choices_keep_the_buttons_above_the_keyboard(device, server, repo, shot, visible):
    """A question of six choices of two lines each with a long own answer, little left: the
    field, Send and Skip question whole."""
    session = gated_session(repo)
    choices = [f"Choice {n}: a rather long choice that takes the most of a row" for n in range(6)]
    runtime.ask_human(session, "supervisor", "Which one?", None, choices)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    card.get_by_role("button", name="Other…").evaluate("b => b.click()")
    own = card.get_by_role("textbox", name="Your own answer")
    expect(own).to_be_focused()
    own.fill("a first line\na second line\na third line")
    page.evaluate(f"window.moveViewport({visible}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{visible}px")
    within(send, 0, visible)
    within(card.get_by_role("button", name="Skip question"), 0, visible)
    within(own, 0, visible)
    for part in (send, card.get_by_role("button", name="Skip question"), own):
        uncut(card, part)
    shot(page, full_page=False)


@pytest.mark.parametrize("visible", [350, 340])
@pytest.mark.parametrize(
    ("button", "field"),
    [("Other…", "Your own answer"), ("Skip question", "Why you skip it (optional)")],
    ids=["other", "skip"],
)
def test_a_field_hides_the_choices_under_a_recommendation_above_the_keyboard(
    device, server, repo, shot, visible, button, field
):
    """A question of six choices under a recommendation of two lines, little left: the field
    in the footer hides the choices, so the field, Send and Skip question are whole; the
    field losing the focus brings them back (the human's decision of 2026-11-05, F16)."""
    session = gated_session(repo)
    choices = [f"Choice {n}: a rather long choice that takes the most of a row" for n in range(6)]
    runtime.ask_human(session, "supervisor", "Which one?", None, choices)
    [asked] = [m.id for m in state.list_messages(session) if m.kind == state.QUESTION]
    state.recommend(state.QUESTION, asked, "A reason to pick it. " * 40, choices[0], False)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    area = card.get_by_role("group", name="Choices")
    expect(area).to_be_visible()
    card.get_by_role("button", name=button).evaluate("b => b.click()")
    own = card.get_by_role("textbox", name=field)
    expect(own).to_be_focused()
    page.evaluate(f"window.moveViewport({visible}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{visible}px")
    expect(area).to_be_hidden()
    skip = card.get_by_role("button", name="Skip question")
    for part in (card.get_by_role("region", name="Supervisor's recommendation"), own, send, skip):
        within(part, 0, visible)
        uncut(card, part)
    shot(page, "keyboard", full_page=False)

    page.evaluate(f"window.moveViewport({KEYBOARD[1]}, 0)")  # the keyboard closes
    expect(page.locator(".app")).to_have_css("height", f"{KEYBOARD[1]}px")
    own.blur()
    expect(area).to_be_visible()
    shot(page, "closed", full_page=False)


def needs_you_with_a_gate_and_a_question(repo) -> str:
    """A long note's gate under a long recommendation, and the supervisor's question."""
    session = gated_session(repo, LONG_NOTE)
    recommended(session, "A reason to approve. " * 40, choice="approve")
    runtime.ask_human(session, "supervisor", "Which one?", "Long details.\n" * 30, ["yes", "no"])
    return session


@pytest.mark.parametrize("visible", [ABOVE_KEYBOARD, 380, 350])
@pytest.mark.parametrize("tab", ["gate", "question"])
def test_on_needs_you_a_field_in_focus_is_seen_and_the_page_scrolls_to_its_buttons(
    device, server, repo, shot, visible, tab
):
    """Needs you scrolls as a page and the browser leads the keyboard, which the imitation
    does not: the field brought into sight stands there, nothing folds around it, and the page
    scrolls on to the buttons under it."""
    session = needs_you_with_a_gate_and_a_question(repo)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, "/needs-you")
    card = waiting_card(page, session)
    expect(card.get_by_role("button", name="Expand the card")).to_have_count(0)
    if tab == "question":
        card.get_by_role("tab", name="supervisor 1").tap()
        card.get_by_role("button", name="Other…").evaluate("b => b.click()")
        field = card.get_by_role("textbox", name="Your own answer")
        button = card.get_by_role("button", name="Send answer to supervisor")
    else:
        field = card.get_by_role("textbox", name="Comment for the next step (optional)")
        field.tap()
        button = card.get_by_role("button", name="Approve", exact=True)
    expect(field).to_be_focused()
    page.evaluate(f"window.moveViewport({visible}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{visible}px")
    field.evaluate("f => f.scrollIntoView({ block: 'nearest' })")
    bar = box(top_bar(page))
    within(field, bar["y"] + bar["height"], visible)
    expect(field).to_be_focused()
    expect(card.get_by_role("region", name="Context of the card")).to_be_attached()
    assert not card.evaluate("c => c.classList.contains('typing')")
    page.mouse.move(100, visible / 2)
    page.mouse.wheel(0, 5000)
    page.wait_for_function(
        "([b, bottom]) => b.getBoundingClientRect().bottom <= bottom + 1",
        arg=[button.element_handle(), visible],
        timeout=3000,
    )
    within(button, bar["y"] + bar["height"], visible)
    shot(page, full_page=False)


@pytest.mark.parametrize("visible", [ABOVE_KEYBOARD, 350])
def test_the_expanded_cards_long_recommendation_gives_way_above_the_keyboard(
    device, server, repo, shot, visible
):
    """Expanded in the chat, the whole recommendation yields to the field and the buttons."""
    session = gated_session(repo)
    recommended(session, "A reason to approve. " * 80, choice="approve")
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").tap()
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    comment.tap()
    page.evaluate(f"window.moveViewport({visible}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{visible}px")
    approve = card.get_by_role("button", name="Approve", exact=True)
    page.wait_for_function(
        "([b, bottom]) => b.getBoundingClientRect().bottom <= bottom + 1",
        arg=[approve.element_handle(), visible],
        timeout=3000,
    )
    for part in (comment, approve):
        within(part, 0, visible)
        uncut(card, part)
    shot(page, full_page=False)


def test_a_field_in_the_context_of_several_questions_stays_in_its_view(device, server, repo, shot):
    """A tab of several questions has its fields in the context: a field's focus hides the
    Team row, never the context it stands in, and the keyboard opening brings the field back
    into the context's view."""
    session = gated_session(repo)
    for n in range(3):
        runtime.ask_human(session, "supervisor", f"Question {n}?", "Details.\n" * 6, ["yes", "no"])
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("tab", name="supervisor 3").tap()
    card.get_by_role("button", name="Other…").last.evaluate("b => b.click()")
    own = card.get_by_role("textbox", name="Your own answer")
    expect(own).to_be_focused()
    context = card.get_by_role("region", name="Context of the card")
    expect(context).to_be_visible()
    expect(page.get_by_role("group", name="Team")).to_be_hidden()
    page.evaluate(f"window.moveViewport({ABOVE_KEYBOARD}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{ABOVE_KEYBOARD}px")
    expect(own).to_be_in_viewport()
    found = box(context)
    page.wait_for_function(
        """([field, top, bottom]) => {
          const box = field.getBoundingClientRect();
          return box.top >= top - 1 && box.bottom <= bottom + 1;
        }""",
        arg=[own.element_handle(), found["y"], found["y"] + found["height"]],
        timeout=5000,
    )
    shot(page, full_page=False)


def test_the_expanded_card_keeps_its_context_with_a_field_in_focus(device, server, repo, shot):
    """Expanded to read the note, the human comments on it: the context stays."""
    session = gated_session(repo)
    page = opened(device(KEYBOARD), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").tap()
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    comment.tap()
    expect(comment).to_be_focused()
    expect(card.get_by_role("region", name="Context of the card")).to_be_visible()
    session_around_card_hidden(page, True)
    shot(page, full_page=False)


def test_the_cards_targets_are_44_px_on_a_phone(device, server, repo, shot):
    """A question's tab, a choice, Send answer, Skip question, Minimize and Expand, a gate's
    field and buttons; the choices' area stops at 148 px."""
    session = gated_session(repo)
    choices = [f"Choice {n}: what it does twice" for n in range(6)]
    runtime.ask_human(session, "supervisor", "Which one?", None, choices)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    for part in (
        card.get_by_role("tab", name="supervisor 1"),
        card.get_by_role("button", name=choices[0]),
        send,
        card.get_by_role("button", name="Skip question"),
        card.get_by_role("button", name="Minimize the card"),
        card.get_by_role("button", name="Expand the card"),
    ):
        assert round(box(part)["height"]) == 44, part
    area = card.get_by_role("group", name="Choices")
    assert box(area)["height"] <= 149
    shot(page, "question", full_page=False)
    card.get_by_role("tab", name="ship/x 1").tap()
    field = card.get_by_role("textbox", name="Comment for the next step (optional)")
    frame = card.locator(".answer-box")
    expect(field).to_be_visible()
    assert round(box(frame)["height"]) == 44
    for name in ("Approve", "Reject"):
        assert round(box(card.get_by_role("button", name=name))["height"]) == 44
    shot(page, "gate", full_page=False)


def test_expanded_by_its_button_on_a_phone_the_card_hides_the_tabs_and_the_team(
    device, server, repo, shot
):
    """AC-4: the expand button on a phone hides the session's tabs and the Team row too."""
    session = gated_session(repo)
    page = opened(device(KEYBOARD), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").tap()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    session_around_card_hidden(page, True)
    expect(card.get_by_role("tab", name="ship/x 1")).to_be_focused()
    shot(page, full_page=False)
    card.get_by_role("button", name="Collapse the card").tap()
    session_around_card_hidden(page, False)


def test_with_a_mouse_a_gates_comment_changes_nothing(device, server, repo):
    """In a narrow window that is no phone a field's focus changes nothing."""
    session = gated_session(repo)
    page = opened(device((700, 844), touch=False), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    comment.click()
    expect(comment).to_be_focused()
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    expect(card.get_by_role("region", name="Context of the card")).to_be_visible()


def test_a_flow_events_text_wraps_whole(device, server, repo, shot):
    session = gated_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    detail = page.locator(
        ".run-detail", has_text="flow ship from kit uiflow 1.0.0: Add a login page"
    )
    expect(detail).to_be_visible()
    assert detail.evaluate("d => d.scrollWidth <= d.clientWidth")  # not cut
    actor = box(page.locator(".run-line").first.locator(".run-actor"))
    text = box(detail)
    assert text["y"] >= actor["y"] + actor["height"] - 1  # under the actor's line
    feed = box(page.locator(".chat-feed"))
    group = box(page.locator(".run-group").first)
    assert group["x"] - feed["x"] <= 16, (group, feed)  # from the feed's left edge
    shot(page, full_page=False)


def test_sideways_the_card_starts_minimized_and_a_tab_opens_it(device, server, repo, shot):
    session = gated_session(repo)
    page = opened(device(SIDEWAYS), server, f"/sessions/{session}")
    assert page.evaluate("document.documentElement.dataset.phone") == "short"
    card = waiting_card(page, session)
    expect(card).to_have_class("waiting-card minimized")
    line = card.locator(".waiting-line")
    expect(line).to_have_text("Build it as planned?")
    expect(line).to_be_in_viewport(ratio=1)
    assert box(line)["y"] + box(line)["height"] <= box(page.locator(".chat > .composer"))["y"]
    assert box(top_bar(page))["height"] <= 44
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_be_visible()
    found = box(field)
    assert found["y"] + found["height"] <= SIDEWAYS[1]
    expect(page.get_by_role("group", name="Team")).to_be_hidden()
    expect(page.locator(".composer-to")).to_be_hidden()
    shot(page, "minimized", full_page=False)

    card.get_by_role("tab", name="ship/x 1").tap()
    expect(card).to_have_class("waiting-card expanded")
    expect(card.get_by_role("button", name="Approve")).to_be_visible()
    shot(page, "expanded", full_page=False)
    page.keyboard.press("Escape")
    expect(card).to_have_class("waiting-card minimized")
    keys = page.evaluate("Object.keys(localStorage)")
    assert not [key for key in keys if key.startswith("lado.waitingMinimized")], keys

    page.set_viewport_size({"width": UPRIGHT[0], "height": UPRIGHT[1]})  # turned upright
    expect(card).to_have_class("waiting-card")
    expect(card.get_by_role("button", name="Approve")).to_be_visible()
    shot(page, "upright", full_page=False)


# Terminals


def test_a_team_chip_opens_the_terminal_over_the_screen(device, server, repo, shot):
    session = running_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(page.get_by_role("group", name="Team")).to_be_visible()
    expect(panel).to_be_hidden()
    page.get_by_role("group", name="Team").get_by_role("button", name="supervisor,").tap()
    expect(panel).to_be_visible()
    expect(panel.get_by_role("tabpanel", name="supervisor").locator(".term")).to_have_attribute(
        "data-link", "open"
    )
    found = box(panel)
    assert found["x"] == 0 and found["width"] == UPRIGHT[0], found
    assert found["height"] >= UPRIGHT[1] - 60, found
    shot(page, "terminal", full_page=False)
    panel.get_by_role("button", name="Close terminal").tap()
    expect(panel).to_be_hidden()
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    assert page.evaluate("localStorage.getItem('lado.terminals')") is None


# Tooltips on a tap


def test_a_tap_on_a_kit_shows_its_tooltip_and_a_button_none(device, server, repo, shot):
    session = gated_session(repo)
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    top_bar(page).get_by_role("button", name=session).tap()
    sheet = page.get_by_role("dialog", name=session)
    sheet.locator(".session-kit", has_text="uiflow").tap()
    tooltip = page.get_by_role("tooltip")
    expect(tooltip).to_contain_text("uiflow v1.0.0")
    shot(page, "kit", full_page=False)
    sheet.get_by_role("heading").tap()
    expect(tooltip).to_have_count(0)
    # A button's tooltip only names it: a tap (whose emulated mouse enters it) shows none.
    sheet.get_by_role("button", name="Close").tap()
    toggle = page.get_by_role("button", name="Messages between agents")
    toggle.tap()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    page.wait_for_timeout(600)  # past the hover's delay
    expect(tooltip).to_have_count(0)


def test_the_cards_fields_with_files_fit_the_phone(device, server, repo, shot):
    """LAD-86: a gate's comment and Other… with files fit the narrowest phone: the frame and
    its chips inside the card, nothing scrolls sideways, and the field's text is 16 px so
    the browser does not zoom into it."""
    session = waiting_session(repo)
    page = opened(device(NARROWEST), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    files = [
        {"name": "screenshot-with-a-long-name.png", "mimeType": "image/png", "buffer": b"x"},
        {"name": "server.log", "mimeType": "text/plain", "buffer": b"GET / 500\n"},
    ]
    card.get_by_role("tab", name="ship/x 1").tap()
    gate = card.get_by_role("tabpanel")
    gate.locator("input[type=file]").set_input_files(files)
    comment = gate.get_by_role("textbox", name="Comment for the next step (optional)")
    expect(gate.locator(".file-chip")).to_have_count(2)
    expect(gate.locator(".waiting-send")).to_contain_text("2 files,")
    assert comment.evaluate("f => getComputedStyle(f).fontSize") == "16px"
    frame = box(gate.locator(".answer-box"))
    panel = box(gate)
    assert frame["x"] >= panel["x"] and frame["x"] + frame["width"] <= panel["x"] + panel["width"]
    for chip in gate.locator(".file-chip").all():
        found = box(chip)
        assert found["x"] + found["width"] <= frame["x"] + frame["width"], found
    no_sideways_scroll(page)
    gate.locator(".answer-box").scroll_into_view_if_needed()
    shot(page, "gate", full_page=False)
    card.get_by_role("tab", name="supervisor 1").tap()
    question = card.get_by_role("tabpanel")
    question.get_by_role("button", name="Other…").tap()
    question.locator("input[type=file]").set_input_files(files[:1])
    expect(question.locator(".file-chip")).to_have_count(1)
    own = question.get_by_role("textbox", name="Your own answer")
    assert own.evaluate("f => getComputedStyle(f).fontSize") == "16px"
    no_sideways_scroll(page)
    shot(page, "question", full_page=False)


def test_only_the_cards_placeholder_keeps_14_px_on_a_phone(device, server, repo):
    """The card's field holds the frames' 14 px placeholder; the gate on the Flows tab keeps
    the field's own 16 px."""
    session = gated_session(repo)
    size = "f => getComputedStyle(f, '::placeholder').fontSize"
    name = "Comment for the next step (optional)"
    page = opened(device(UPRIGHT), server, f"/sessions/{session}")
    comment = waiting_card(page, session).get_by_role("textbox", name=name)
    expect(comment).to_be_visible()
    assert comment.evaluate(size) == "14px"
    page.goto(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    gate = page.get_by_role("region", name="Now").get_by_role("article", name="Gate #1", exact=True)
    assert gate.get_by_role("textbox", name=name).evaluate(size) == "16px"


@pytest.mark.parametrize("size", [UPRIGHT, NARROWEST], ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_gates_and_a_questions_tabs_fit_the_phone(device, server, repo, shot, size):
    """Two tabs of the card stand whole in their row, whichever is shown: nothing is cut at the
    row's edge, and each keeps its count."""
    session = waiting_session(repo)
    page = opened(device(size), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    row = card.get_by_role("tablist")
    for name in ("ship/x 1", "supervisor 1"):
        card.get_by_role("tab", name=name).tap()
        expect(card.get_by_role("tab", name=name)).to_have_attribute("aria-selected", "true")
        assert row.evaluate("r => r.scrollWidth <= r.clientWidth"), name
        strip = box(row)
        for tab in card.get_by_role("tab").all():
            found = box(tab)
            assert found["x"] >= strip["x"] - 1, found
            assert found["x"] + found["width"] <= strip["x"] + strip["width"] + 1, found
            expect(tab.locator(".waiting-tab-count")).to_be_visible()
    shot(page, full_page=False)


# Nothing scrolls sideways


PAGES = ["/", "/needs-you", "/sessions", "/projects", "/kits", "/settings", "/report"]
TABS = ["activity", "agents", "flows", "artifacts"]


@pytest.mark.parametrize(
    "size", [NARROWEST, UPRIGHT, (430, 932), SIDEWAYS], ids=lambda s: f"{s[0]}x{s[1]}"
)
def test_no_page_scrolls_sideways(device, server, repo, shot, size):
    session = gated_session(repo)
    page = opened(device(size), server, "/")
    for path in PAGES + [f"/sessions/{session}/{tab}" for tab in TABS]:
        page.goto(f"{server['url']}{path}")
        expect(top_bar(page)).to_be_visible()
        page.wait_for_load_state("networkidle")
        no_sideways_scroll(page)
    shot(page, full_page=False)
