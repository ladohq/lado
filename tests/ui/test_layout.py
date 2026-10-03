"""The session page's layout in a browser: the list, the session with its team and feed, and
the terminal panel on the right that a chip opens; a run's events in the feed and the
session under Needs you, from lado.db's journal to the page."""

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1440, "height": 900})


def with_worker(repo) -> str:
    session = running_session(repo)
    runtime.spawn_worker(session, "Build the layout\nin three columns", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    return session


def test_the_panel_shows_the_supervisors_terminal_when_the_page_opens(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    view = panel.get_by_role("tabpanel", name="supervisor")
    expect(view.get_by_role("status")).to_have_text("live")  # before any click
    expect(panel.get_by_role("tab", name="supervisor")).to_have_attribute("aria-selected", "true")
    expect(panel.get_by_role("button", name="Close supervisor's terminal")).to_have_count(0)
    chat = page.get_by_role("region", name="Chat").bounding_box()
    right = panel.bounding_box()
    assert right["x"] >= chat["x"] + chat["width"]
    shot(page)


def test_a_chip_opens_its_agents_terminal_on_the_right_of_the_chat(page: Page, server, repo, shot):
    session = with_worker(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    team = page.get_by_role("group", name="Team")
    chips = team.get_by_role("button")
    expect(chips).to_have_count(2)
    expect(chips.first).to_have_accessible_name("supervisor, supervisor, idle")
    expect(chips.nth(1)).to_have_attribute("title", "Build the layout")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(chips.first).to_have_attribute("aria-pressed", "true")  # the supervisor's, at first
    shot(page, "layout")

    chips.nth(1).click()
    expect(chips.nth(1)).to_have_attribute("aria-pressed", "true")
    view = panel.get_by_role("tabpanel", name="w1")
    expect(view.get_by_role("status")).to_have_text("live")
    expect(view).to_contain_text("Viewing")
    chat = page.get_by_role("region", name="Chat").bounding_box()
    right = panel.bounding_box()
    assert right["x"] >= chat["x"] + chat["width"]  # beside the chat, not under it
    assert right["height"] > 600  # the page's height
    # The switch stays on the team's row: the feed keeps its height.
    switch = page.get_by_role("checkbox", name="Show agent messages").bounding_box()
    first = chips.first.bounding_box()
    assert switch["y"] < first["y"] + first["height"]
    shot(page, "terminal")

    chips.first.click()  # back to the supervisor's tab; w1's keeps its socket
    expect(panel.get_by_role("tab")).to_have_text(["supervisor", "w1"])
    expect(panel.get_by_role("tabpanel", name="supervisor").get_by_role("status")).to_have_text(
        "live"
    )
    panel.get_by_role("tab", name="w1").click()
    expect(view.get_by_role("status")).to_have_text("live")


def test_the_panel_collapses_to_a_strip_and_opens_no_terminal_until_it_is_opened(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("status")).to_have_text("live")
    panel.get_by_role("button", name="Collapse terminals").click()
    assert panel.bounding_box()["width"] < 50
    shot(page)

    sockets = []
    page.on("websocket", lambda socket: sockets.append(socket.url))
    page.reload()
    expect(panel.get_by_role("button", name="Terminals")).to_be_visible()  # still collapsed
    page.wait_for_timeout(500)
    assert sockets == []
    panel.get_by_role("button", name="Terminals").click()
    expect(panel.get_by_role("status")).to_have_text("live")
    assert len(sockets) == 1


def drag(page: Page, splitter, by: float) -> None:
    box = splitter.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + by / 2, y)
    page.mouse.move(x + by, y)
    page.mouse.up()


def test_the_list_and_the_panel_are_resized_on_their_edges_and_keep_their_widths(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    list_edge = page.get_by_role("separator", name="Resize the session list")
    panel_edge = page.get_by_role("separator", name="Resize the terminals")
    expect(list_edge).to_have_attribute("aria-valuenow", "260")
    expect(panel_edge).to_have_attribute("aria-valuenow", "480")
    list_edge.hover()
    assert list_edge.evaluate("e => getComputedStyle(e).cursor") == "col-resize"
    drag(page, list_edge, 60)
    drag(page, panel_edge, -50)
    expect(list_edge).to_have_attribute("aria-valuenow", "320")
    expect(panel_edge).to_have_attribute("aria-valuenow", "530")
    page.reload()
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("status")).to_have_text("live")
    assert round(page.locator(".session-list").bounding_box()["width"]) == 320
    assert round(panel.bounding_box()["width"]) == 530
    shot(page)

    # A narrower window narrows the columns, keeps the session readable, and forgets nothing.
    page.set_viewport_size({"width": 1100, "height": 900})
    expect(panel_edge).not_to_have_attribute("aria-valuenow", "530")
    assert page.locator(".session-main").bounding_box()["width"] >= 360
    shot(page, "narrower")
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(panel_edge).to_have_attribute("aria-valuenow", "530")
    expect(list_edge).to_have_attribute("aria-valuenow", "320")


def test_the_window_never_scrolls_and_the_feed_scrolls_by_itself(page: Page, server, repo, shot):
    session = running_session(repo)
    for n in range(40):
        runtime.send_message(session, "supervisor", "human", f"progress note {n}")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    expect(chat).to_contain_text("progress note 39")
    page.mouse.move(700, 400)
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(300)
    scrolled = page.evaluate(
        "() => [document.scrollingElement.scrollHeight, document.scrollingElement.clientHeight,"
        " window.scrollY]"
    )
    assert scrolled[0] == scrolled[1] and scrolled[2] == 0
    assert chat.evaluate("e => e.scrollHeight > e.clientHeight")
    assert page.evaluate("() => getComputedStyle(document.body).overscrollBehaviorY") == "none"
    shot(page)


def test_a_runs_events_show_in_the_feed_and_its_gate_puts_the_session_under_needs_you(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    sessions = page.get_by_role("navigation", name="Sessions")
    expect(sessions.get_by_role("region", name="Running")).to_contain_text(session)

    run = state.Run(session, "feature/demo", "feature", {}, {}, "demo", "design", "/w", "b")
    gate = state.Gate(session, "feature/demo", "approve", "approval", "OK?", ["approved"])
    state.add_run(run, [("supervisor", state.FLOW_START, "at design")], gate)
    chat = page.get_by_role("log", name="Chat with the session")
    lines = chat.get_by_role("listitem")
    expect(lines.first).to_contain_text("feature/demo: at design")
    expect(lines.last).to_contain_text("waits for you")
    expect(lines.first.get_by_role("link", name="Flows")).to_have_attribute(
        "href", f"/sessions/{session}/flows"
    )
    needs_you = sessions.get_by_role("region", name="Needs you")
    expect(needs_you).to_contain_text(session)
    expect(needs_you).to_contain_text("1 gate")
    shot(page)
