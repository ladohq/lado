"""A stopped session's page in a browser: the bar with Resume session in the composer's place,
the feed's words, the team on a phone, and terminals that fold without touching what is
stored. The fake agent's sessions."""

import json
import re

import pytest
from playwright.sync_api import Browser, Page, expect
from test_gates import gated_session, waiting_card
from test_launch import idle, log_in, stopped_session
from test_main_screen import running_session

from lado import runtime

pytestmark = pytest.mark.ui

UPRIGHT = (390, 844)
SIDEWAYS = (844, 390)


def bar(page: Page):
    return page.locator(".stopped-bar")


def composer(page: Page):
    return page.get_by_role("textbox", name="Write to the supervisor…")


def resume(page: Page) -> None:
    """Resume by the bar, through the window, and wait until the session runs."""
    session = page.url.split("/sessions/")[1].split("/")[0].split("?")[0]
    bar(page).get_by_role("button", name="Resume session").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    expect(dialog.get_by_label("Provider")).to_have_value("fake", timeout=30_000)  # CLIs checked
    dialog.get_by_role("button", name="Resume session").click()
    expect(dialog).to_have_count(0)
    idle(session)
    expect(bar(page)).to_have_count(0)


def stored(page: Page, key: str):
    return page.evaluate("key => localStorage.getItem(key)", key)


@pytest.mark.parametrize("width", [1440, 768, 390])
@pytest.mark.parametrize("said", [False, True], ids=["empty", "with-messages"])
def test_the_bar_stands_in_the_composers_place(page: Page, server, repo, shot, width, said):
    page.set_viewport_size({"width": width, "height": 800})
    session = running_session(repo)
    log_in(page, server, f"/sessions/{session}")
    feed = page.get_by_role("log", name="Chat with the session")
    if said:
        composer(page).fill("before the stop")
        composer(page).press("Enter")
        expect(feed).to_contain_text("before the stop")
    runtime.stop_session(session)  # shown live: no reload
    expect(bar(page)).to_be_visible()
    expect(composer(page)).to_be_hidden()
    expect(bar(page).get_by_role("status")).to_have_text(
        "This session is stoppedIts branches, runs and history are kept"
    )
    if said:
        expect(feed).to_contain_text("before the stop")
    else:
        expect(feed).to_contain_text("No messages with you. Messages between agents are hidden.")
    frame = bar(page).bounding_box()
    above = feed.bounding_box()
    assert frame["y"] >= above["y"] + above["height"] - 1, "the bar stands under the feed"
    assert frame["x"] >= 0 and frame["x"] + frame["width"] <= width
    if width > 600:
        assert frame["height"] >= 52
        button = bar(page).get_by_role("button", name="Resume session").bounding_box()
        assert button["y"] < frame["y"] + frame["height"] / 2 < button["y"] + button["height"]
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    shot(page)
    page.emulate_media(color_scheme="dark")
    shot(page, "dark")


@pytest.fixture
def touch_screen(browser: Browser):
    contexts = []

    def make(size: tuple[int, int]) -> Page:
        width, height = size
        context = browser.new_context(
            viewport={"width": width, "height": height}, is_mobile=True, has_touch=True
        )
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


def test_upright_the_button_spans_the_bar_under_whole_text(touch_screen, server, repo, shot):
    page = touch_screen(UPRIGHT)
    log_in(page, server, f"/sessions/{stopped_session(repo)}")
    frame = bar(page).bounding_box()
    button = bar(page).get_by_role("button", name="Resume session").bounding_box()
    words = bar(page).get_by_role("status").bounding_box()
    assert button["y"] >= words["y"] + words["height"]
    assert button["height"] == 44
    assert button["width"] >= frame["width"] - 2 * 12 - 2  # the frame's padding and border
    for line in bar(page).locator("strong, span").all():
        assert line.evaluate("e => e.scrollWidth <= e.clientWidth"), "a line is cut"
    shot(page)


def test_sideways_the_bar_stays_one_row(touch_screen, server, repo, shot):
    page = touch_screen(SIDEWAYS)
    log_in(page, server, f"/sessions/{stopped_session(repo)}")
    words = bar(page).get_by_role("status").bounding_box()
    button = bar(page).get_by_role("button", name="Resume session").bounding_box()
    assert button["height"] == 44
    assert button["x"] >= words["x"] + words["width"]
    assert button["y"] < words["y"] + words["height"]
    shot(page)


def test_no_team_shows_and_a_phones_toggle_has_its_words(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 800})
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    expect(bar(page)).to_be_visible()
    expect(page.get_by_role("banner").get_by_label("Team")).to_have_count(0)

    page.set_viewport_size({"width": 390, "height": 844})
    toggle = page.get_by_role("button", name="Messages between agents")
    expect(toggle).to_have_text("Messages between agents")
    expect(page.locator(".team-row")).not_to_contain_text("Team")
    assert toggle.bounding_box()["height"] == 44
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_have_css("border-top-color", re.compile(r"^(?!rgba\(0, 0, 0, 0\)).*$"))
    shot(page)


def test_resume_session_brings_the_composer_back_with_its_draft(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server, f"/sessions/{session}")
    composer(page).fill("half a thought")
    runtime.stop_session(session)
    expect(bar(page)).to_be_visible()
    resume(page)
    expect(composer(page)).to_have_value("half a thought")
    shot(page)


def test_the_empty_feed_says_what_the_filter_shows(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 800})
    log_in(page, server, f"/sessions/{stopped_session(repo)}")
    feed = page.get_by_role("log", name="Chat with the session")
    yours = feed.get_by_text("No messages with you. Messages between agents are hidden.")
    expect(yours).to_be_visible()
    shot(page, "yours")
    page.get_by_role("radio", name="All").click()
    words = feed.get_by_text("Nothing was said in this session.")
    expect(words).to_be_visible()
    frame, line = feed.bounding_box(), words.bounding_box()
    middle = line["y"] + line["height"] / 2
    assert abs(middle - (frame["y"] + frame["height"] / 2)) <= 2, "the words stand in the middle"
    shot(page, "all")


def test_an_open_gate_stands_above_the_bar_on_a_phone(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 390, "height": 844})
    session = gated_session(repo)
    runtime.stop_session(session)
    log_in(page, server, f"/sessions/{session}")
    card = waiting_card(page, session)
    expect(card).to_be_visible()
    expect(bar(page)).to_be_visible()
    above, frame = card.bounding_box(), bar(page).bounding_box()
    assert above["y"] + above["height"] <= frame["y"] + 1, "the card and the bar overlap"
    assert frame["y"] + frame["height"] <= 844
    shot(page)


TERMINALS_OPEN = json.dumps({"width": 500, "collapsed": False})


def terminals(page: Page):
    return page.get_by_role("complementary", name="Terminals")


def test_terminals_stored_open_are_folded_and_come_back_with_resume(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 800})
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    page.evaluate("v => localStorage.setItem('lado.terminals', v)", TERMINALS_OPEN)
    page.reload()
    show = terminals(page).get_by_role("button", name="Show the terminals")
    expect(show).to_be_visible()
    assert stored(page, "lado.terminals") == TERMINALS_OPEN
    shot(page)
    resume(page)
    expect(show).to_have_count(0)
    tab = terminals(page).get_by_role("tabpanel", name="supervisor")
    expect(tab.locator(".term")).to_have_attribute("data-link", "open", timeout=20_000)
    assert stored(page, "lado.terminals") == TERMINALS_OPEN


def test_terminals_opened_by_hand_store_nothing_and_fold_on_a_reload(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 800})
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    before = stored(page, "lado.terminals"), stored(page, "lado.lastColumn")
    terminals(page).get_by_role("button", name="Show the terminals").click()
    expect(terminals(page).get_by_text("Agent not running")).to_be_visible()
    shot(page)
    page.emulate_media(color_scheme="dark")
    shot(page, "dark")
    assert (stored(page, "lado.terminals"), stored(page, "lado.lastColumn")) == before
    page.reload()
    expect(terminals(page).get_by_role("button", name="Show the terminals")).to_be_visible()
