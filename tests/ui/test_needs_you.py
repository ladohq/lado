"""Needs you in a browser: what waits for the human in every session, answered in place and
gone at once, also when answered elsewhere (`lado answer`); its count on the rail; and a
browser notification for something new while the tab is hidden."""

import re
import subprocess
import sys

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_chat import asked_with_a_plan, on_top
from test_gates import gated_session
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def rail_link(page: Page, waiting: int = 0):
    name = f"Needs you, {waiting} waiting" if waiting else "Needs you"
    return page.get_by_role("navigation", name="Sections").get_by_role(
        "link", name=name, exact=True
    )


def test_the_human_answers_what_waits_in_place_and_it_goes(page: Page, server, repo, shot):
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Merge w1 now?", "Tests pass.", ["yes", "later"])
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    group = page.get_by_role("region", name=f"Session {session}")
    card = group.get_by_role("region", name=f"What waits for you in {session}")
    expect(card.get_by_role("tab", name="ship/x 1")).to_have_attribute("aria-selected", "true")
    expect(card.get_by_role("tab", name="supervisor 1")).to_be_visible()
    expect(group.get_by_role("link", name=f"{session}'s chat")).to_have_text("In the chat")
    expect(rail_link(page, 2)).to_be_visible()
    expect(page).to_have_title("(2) Needs you · LADO")
    shot(page, "waiting")

    card.get_by_role("button", name="Approve", exact=True).click()
    expect(card.get_by_role("tab", name="ship/x 1")).to_have_count(0)
    expect(rail_link(page, 1)).to_be_visible()
    card.get_by_role("button", name="yes", exact=True).click()
    card.get_by_role("button", name="Send answer to supervisor").click()
    expect(page.get_by_text("Nothing waits for you")).to_be_visible()
    expect(rail_link(page)).to_be_visible()
    expect(page).to_have_title("Needs you · LADO")
    shot(page, "nothing")


def test_cards_taller_than_the_window_leave_the_page_at_its_top(page: Page, server, repo, shot):
    """Each card shows its first tab without scrolling the page: the tabs' row scrolls only
    sideways (review of LAD-28, F4)."""
    body = "\n\n".join(f"Point {n}: what the agent found and why it matters." for n in range(8))
    sessions = []
    for _ in range(3):
        session = running_session(repo)
        for n in range(3):
            runtime.ask_human(session, "supervisor", f"Question {n}?", body, ["yes", "no"])
        sessions.append(session)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    for session in sessions:
        card = page.get_by_role("region", name=f"What waits for you in {session}")
        expect(card.get_by_role("tab", name="supervisor 3")).to_be_visible()
    content = page.locator(".content")
    assert content.evaluate("e => e.scrollHeight > e.clientHeight")  # taller than the window
    page.wait_for_timeout(300)  # the cards' effects ran
    assert content.evaluate("e => e.scrollTop") == 0
    shot(page, "top")


def test_a_gate_answered_with_lado_answer_goes_without_a_reload(page: Page, server, repo, shot):
    session = gated_session(repo)
    # The supervisor got the gate's line; once that turn is over, it waits for the human.
    agent_helpers.wait_for(
        lambda: (
            state.get_agent(session, "supervisor").status == state.IDLE
            and all(
                m.state not in (state.PENDING, state.SENT)
                for m in state.list_messages(session)
                if m.recipient == "supervisor"
            )
        ),
        "the supervisor idle with its messages delivered",
        session,
    )
    state.set_status(session, "supervisor", state.WAITING)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    group = page.get_by_role("region", name=f"Session {session}")
    agent = group.get_by_role("article", name="supervisor waits")
    expect(agent).to_contain_text("waits for you in its terminal")
    gate = group.get_by_role("tab", name="ship/x 1")
    expect(gate).to_be_visible()
    page.get_by_role("button", name="Collapse menu").click()
    expect(rail_link(page, 2)).to_be_visible()
    shot(page, "collapsed rail")
    answer = subprocess.run(
        [sys.executable, "-m", "lado.cli", "answer", session, "1", "approve"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert answer.returncode == 0, answer.stderr
    expect(gate).to_have_count(0)
    expect(rail_link(page, 1)).to_be_visible()
    agent.get_by_role("button", name="Open supervisor's terminal").click()
    expect(page).to_have_url(re.compile(rf"/sessions/{session}/activity$"))
    tab = page.get_by_role("tab", name=re.compile(r"^supervisor,"))
    expect(tab).to_have_attribute("aria-selected", "true")
    shot(page, "terminal")


def test_an_expanded_card_fills_the_page_and_a_chip_opens_the_panel_over_needs_you(
    page: Page, server, repo, shot
):
    """LAD-48: expanded, a session's card fills the page's content area, the other sessions
    hidden; its chip opens the artifact panel over Needs you, and Back closes it with the
    card as it was (docs/design/ui.md, Needs you)."""
    session, other = running_session(repo), running_session(repo)
    asked_with_a_plan(session)
    runtime.ask_human(other, "supervisor", "Tag it?", None, ["yes", "no"])
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    card = page.get_by_role("region", name=f"What waits for you in {session}")
    others = page.get_by_role("region", name=f"Session {other}")
    expect(others).to_be_visible()
    card.get_by_role("button", name="myself").click()
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(others).to_be_hidden()
    name_line = page.get_by_role("heading", name=f"{session} {session}'s chat")
    expect(name_line).to_be_visible()
    assert name_line.bounding_box()["y"] < card.bounding_box()["y"]
    content = page.locator(".content").bounding_box()
    box = card.bounding_box()
    assert box["y"] + box["height"] >= content["y"] + content["height"] - 40, (box, content)
    shot(page, "expanded")

    card.get_by_role("button", name="Open artifact plan").click()
    expect(page).to_have_url(re.compile(rf"/needs-you\?view=[^&]+&session={session}$"))
    panel = page.get_by_role("dialog", name="Artifact plan")
    expect(panel).to_contain_text("J1 to J9.")
    assert on_top(page, panel)
    shot(page, "panel")
    page.go_back()
    expect(panel).to_have_count(0)
    expect(page).to_have_url(re.compile(r"/needs-you$"))
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(card.get_by_role("button", name="myself")).to_have_attribute("aria-pressed", "true")

    # A narrow window: the expanded card is the window's height under the top bar.
    page.set_viewport_size({"width": 390, "height": 760})
    page.wait_for_timeout(100)
    box = card.bounding_box()
    assert box["height"] >= 760 - 52 - 1, box
    card.get_by_role("button", name="Collapse the card").click()
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_be_in_viewport()
    top = page.locator(".topbar").bounding_box()
    assert abs(card.bounding_box()["y"] - (top["y"] + top["height"])) <= 2, card.bounding_box()
    shot(page, "narrow")


# The page's Notification, recorded; and the tab hidden while window.hidden is true.
SPY = """
(() => {
  window.hidden = false;
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => (window.hidden ? "hidden" : "visible"),
  });
  const Real = window.Notification;
  window.notified = [];
  window.Notification = class extends Real {
    constructor(title, options) {
      super(title, options);
      window.notified.push(this);
    }
  };
})();
"""


@pytest.fixture
def notifying(playwright):
    """A page that may show notifications: Playwright's full Chromium (its headless shell
    denies them whatever is granted), the permission granted, Notification recorded."""
    browser = playwright.chromium.launch(channel="chromium")
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.grant_permissions(["notifications"])
    page = context.new_page()
    page.add_init_script(SPY)
    yield page
    browser.close()


def test_a_new_question_notifies_a_hidden_tab_and_its_click_leads_to_it(
    notifying: Page, server, repo, shot
):
    page = notifying
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    page.get_by_role("button", name="Enable notifications").click()
    expect(page.get_by_text("Browser notifications are on.")).to_be_visible()
    shot(page, "on")
    page.goto(f"{server['url']}/sessions")  # any page: the shell notifies
    expect(rail_link(page, 1)).to_be_visible()
    page.evaluate("window.hidden = true")
    runtime.ask_human(session, "supervisor", "Merge w1 now?", None, ["yes"])
    expect(rail_link(page, 2)).to_be_visible()
    page.wait_for_function("window.notified.length === 1")
    [question] = [m for m in state.list_messages(session) if m.kind == state.QUESTION]
    shown = page.evaluate(
        "(({title, body, tag, silent}) => ({title, body, tag, silent}))(window.notified[0])"
    )
    assert shown == {
        "title": f"LADO · {session}",
        "body": "Merge w1 now?",
        "tag": f"question:{question.id}",
        "silent": True,
    }
    page.evaluate("window.notified[0].onclick()")
    expect(page).to_have_url(re.compile(rf"/sessions/{session}/activity#message-{question.id}$"))
    card = page.get_by_role("region", name=f"What waits for you in {session}")
    expect(card.get_by_role("tab", name="supervisor 1")).to_have_attribute("aria-selected", "true")
    expect(card.locator(f'[data-item="{question.id}"]')).to_be_in_viewport()
    shot(page, "clicked")
