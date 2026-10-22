"""The phone layout in a browser (docs/design/ui.md, Phone layout; LAD-95): Chromium with a
touch screen (`is_mobile`, `has_touch`) upright at 390x844 and 360x780 and sideways at
844x390, and with a mouse at the same sizes, which must keep the computer's layout."""

import re

import pytest
from playwright.sync_api import Browser, Page, expect
from test_gates import gated_session, waiting_card
from test_main_screen import log_in, running_session

from lado import runtime

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


def keeps_the_computers_frame(page: Page) -> None:
    """None of the phone's frame (LAD-109): no variable of usePhoneViewport on <html>, and
    the app in the page's flow."""
    root = "getComputedStyle(document.documentElement).getPropertyValue('--phone-height')"
    assert page.evaluate(root) == ""
    assert page.locator(".app").evaluate("a => getComputedStyle(a).position") == "static"


# A computer and a tablet keep their layout


@pytest.mark.parametrize("size", [(1280, 800), (800, 900), UPRIGHT], ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_computer_keeps_its_layout(device, server, repo, shot, size):
    session = running_session(repo)
    page = opened(device(size, touch=False), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.phone") is None
    expect(rail(page)).to_be_visible()
    expect(page.get_by_role("button", name=MENU)).to_have_count(0)
    expect(top_bar(page).get_by_role("button", name="Copy path")).to_be_visible()  # the facts
    expect(
        page.get_by_role("navigation", name="Sessions", exact=True)
    ).to_be_visible()  # list or strip
    expect(page.get_by_role("complementary", name="Terminals")).to_be_visible()
    keeps_the_computers_frame(page)
    shot(page)


def test_a_tablet_keeps_its_layout(device, server, repo, shot):
    session = running_session(repo)
    page = opened(device((820, 1180)), server, f"/sessions/{session}")
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.phone") is None
    expect(rail(page)).to_be_visible()
    expect(page.get_by_role("button", name=MENU)).to_have_count(0)
    keeps_the_computers_frame(page)
    shot(page, full_page=False)


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
    assert box(card)["height"] <= chat["height"] / 2 + 1
    assert page.locator(".chat-feed").evaluate("f => getComputedStyle(f).overflowY") == "auto"
    expect(page.locator(".composer-keys")).to_be_hidden()
    expect(page.locator(".composer-to")).to_have_text("to supervisor")
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
    at its bottom, the top bar stays at its top, the composer and Send within it, the card at
    most half the chat; when it grows back, the app does too."""
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
    assert box(card)["height"] <= box(page.get_by_role("region", name="Chat"))["height"] / 2 + 1
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


# A field of the card above the keyboard (LAD-126): the keyboard leaves 400 px of 874 visible.

KEYBOARD = (402, 874)
ABOVE_KEYBOARD = 400


def session_around_card_hidden(page: Page, hidden: bool) -> None:
    """The session's tabs and the Team row, hidden while the card is expanded on a phone."""
    for part in (
        page.get_by_role("navigation", name="Session sections"),
        page.get_by_role("group", name="Team"),
    ):
        (expect(part).to_be_hidden if hidden else expect(part).to_be_visible)()


def test_a_gates_comment_expands_the_card_above_the_keyboard(device, server, repo, shot):
    """AC-1, AC-3: a tap on the gate's comment expands the card, the field focused; with the
    keyboard's 400 px the field and Approve / Reject are in sight, the session's tabs and the
    Team row hidden; the keyboard closed, the card stays expanded until Collapse."""
    session = gated_session(repo)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    session_around_card_hidden(page, False)
    comment.tap()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(comment).to_be_focused()
    page.evaluate(f"window.moveViewport({ABOVE_KEYBOARD}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{ABOVE_KEYBOARD}px")
    session_around_card_hidden(page, True)
    expect(comment).to_be_focused()
    comment.fill("check the migration")
    for part in (
        comment,
        card.get_by_role("button", name="Approve"),
        card.get_by_role("button", name="Reject"),
    ):
        within(part, 0, ABOVE_KEYBOARD)
    shot(page, "keyboard", full_page=False)

    page.evaluate(f"window.moveViewport({KEYBOARD[1]}, 0)")  # the keyboard closes
    expect(page.locator(".app")).to_have_css("height", f"{KEYBOARD[1]}px")
    comment.blur()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(comment).to_have_value("check the migration")
    shot(page, "closed", full_page=False)
    card.get_by_role("button", name="Collapse the card").tap()
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    session_around_card_hidden(page, False)
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    assert box(card)["y"] + box(card)["height"] <= box(page.locator(".chat > .composer"))["y"] + 1


def test_an_own_answer_expands_the_card_above_the_keyboard(device, server, repo, shot):
    """AC-2: a tap on Other… expands the card with its field focused; the field and Send
    are in sight with the keyboard's 400 px."""
    session = question_session(repo)
    phone = device(KEYBOARD)
    phone.add_init_script(FAKE_VIEWPORT)
    page = opened(phone, server, f"/sessions/{session}")
    card, send = question_tab(page, session)
    card.get_by_role("button", name="Other…").tap()
    own = card.get_by_role("textbox", name="Your own answer")
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(own).to_be_focused()
    page.evaluate(f"window.moveViewport({ABOVE_KEYBOARD}, 0)")
    expect(page.locator(".app")).to_have_css("height", f"{ABOVE_KEYBOARD}px")
    session_around_card_hidden(page, True)
    within(own, 0, ABOVE_KEYBOARD)
    within(send, 0, ABOVE_KEYBOARD)
    shot(page, full_page=False)


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


def test_with_a_mouse_a_gates_comment_does_not_expand_the_card(device, server, repo):
    """AC-4: in a window as narrow as a phone with a mouse a field's focus expands nothing."""
    session = gated_session(repo)
    page = opened(device(KEYBOARD, touch=False), server, f"/sessions/{session}")
    card = waiting_card(page, session)
    comment = card.get_by_role("textbox", name="Comment for the next step (optional)")
    comment.click()
    expect(comment).to_be_focused()
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))


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
