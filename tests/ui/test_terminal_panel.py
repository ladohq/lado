"""Agents' terminals in a browser, in the panel on the right: the supervisor's opened from
its chip to view, then taken control of and typed into; another agent's opened from the
Agents tab to view, with its history read only."""

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state, tmux

pytestmark = pytest.mark.ui


def test_the_supervisors_terminal_opens_to_view_and_takes_what_the_human_types_in_control(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("group", name="Team").get_by_role("button", name="supervisor,").click()
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tab", name="supervisor")).to_have_attribute("aria-selected", "true")
    expect(panel.get_by_role("status")).to_have_text("live")
    expect(panel).to_contain_text("Viewing")
    panel.get_by_role("button", name="Take control").click()
    panel.get_by_role("alertdialog").get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("In control")
    expect(panel.get_by_role("status")).to_have_text("live")
    panel.locator(".xterm").click()
    page.keyboard.type("lines 3")
    page.keyboard.press("Enter")
    expect(panel.locator(".xterm-rows")).to_contain_text("line 3")
    inputs = state.home() / "agents" / session / "supervisor" / "inputs.jsonl"
    assert '"lines 3"' in inputs.read_text().splitlines()
    shot(page)


def test_an_agents_terminal_opens_to_view_with_its_history(page: Page, server, repo, shot):
    session = running_session(repo)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    tmux.send_text(session, "w1", "lines 120")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents")
    agents = page.get_by_role("table", name=f"Agents of {session}")
    agents.get_by_role("button", name="Open w1's terminal").click()

    panel = page.get_by_role("complementary", name="Terminals")
    view = panel.get_by_role("tabpanel", name="w1")
    expect(view.get_by_role("status")).to_have_text("live")
    expect(view).to_contain_text("Viewing")
    expect(view.locator(".xterm-rows")).to_contain_text("line 120")
    # The whole window shows in the panel: its last row too, where the live lines are.
    screen = view.locator(".term-screen").bounding_box()
    last = view.locator(".xterm-rows > div").last.bounding_box()
    assert screen["y"] <= last["y"] and last["y"] + last["height"] <= screen["y"] + screen["height"]
    latest = view.locator(".xterm-rows > div", has_text="line 120").bounding_box()
    assert latest["y"] + latest["height"] <= screen["y"] + screen["height"]
    shot(page, "view")

    view.locator(".xterm").hover()
    page.mouse.wheel(0, -300)
    history = view.get_by_role("region", name="History (read only)")
    expect(history).to_contain_text("line 1\n")
    shot(page, "history")
    history.get_by_role("button", name="Back to live ↓").click()
    expect(history).to_have_count(0)

    # Typing while viewing reaches nobody.
    view.locator(".xterm").click()
    page.keyboard.type("lines 5\n")
    page.wait_for_timeout(500)
    inputs = (state.home() / "agents" / session / "w1" / "inputs.jsonl").read_text()
    assert "lines 5" not in inputs

    view.get_by_role("button", name="Take control").click()
    view.get_by_role("alertdialog").get_by_role("button", name="Take control").click()
    expect(view).to_contain_text("In control")
    expect(view.get_by_role("status")).to_have_text("live")
    shot(page, "control")
