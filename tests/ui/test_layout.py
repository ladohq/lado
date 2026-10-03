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
    runtime.spawn_worker(session, "Build the layout\nin three columns")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    return session


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
    expect(panel).to_have_count(0)  # closed until a terminal is opened
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
    shot(page, "terminal")

    chips.first.click()  # a second tab; w1's keeps its socket
    expect(panel.get_by_role("tab")).to_have_text(["w1", "supervisor"])
    expect(panel.get_by_role("tabpanel", name="supervisor").get_by_role("status")).to_have_text(
        "live"
    )
    panel.get_by_role("tab", name="w1").click()
    expect(view.get_by_role("status")).to_have_text("live")


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
