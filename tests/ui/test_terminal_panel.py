"""Agents' terminals in a browser, in the panel on the right: the supervisor's opened from
its chip to view, then taken control of and typed into; another agent's opened from the
Agents tab to view, where the wheel up points at Take control."""

import re

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
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tab", name="supervisor")).to_have_attribute("aria-selected", "true")
    expect(panel.get_by_role("status")).to_have_text("live")
    expect(panel).to_contain_text("Viewing")
    panel.get_by_role("button", name="Take control").click()
    ask = page.get_by_role("dialog", name="Take control of supervisor")
    expect(ask).to_be_visible()
    shot(page, "ask")
    ask.get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("In control")
    expect(panel.get_by_role("status")).to_have_text("live")
    panel.locator(".xterm").click()
    page.keyboard.type("lines 3")
    page.keyboard.press("Enter")
    expect(panel.locator(".xterm-rows")).to_contain_text("line 3")
    inputs = agent_helpers.fake_logs(session, "supervisor") / "inputs.jsonl"
    assert '"lines 3"' in inputs.read_text().splitlines()
    shot(page)


def test_an_agents_terminal_opens_to_view_and_its_wheel_points_at_take_control(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    tmux.send_text(session, "w1", "lines 120")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1")
    agent = page.get_by_role("region", name="Agent w1")
    agent.get_by_role("button", name="Open terminal").click()

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

    # The wheel up points at Take control in the bar, the one button, instead of scrolling.
    view.locator(".xterm").hover()
    page.mouse.wheel(0, -300)
    hint = view.get_by_role("status").filter(has_text="Scrolling works after Take control.")
    expect(hint).to_be_visible()
    take = view.get_by_role("button", name="Take control")
    expect(take).to_have_count(1)
    expect(take).to_have_class(re.compile(r"\battention\b"))
    expect(view.get_by_role("region", name="History (read only)")).to_have_count(0)
    # Under the button, over the terminal, inside the panel, and not covered by it.
    box, button, panel_box = hint.bounding_box(), take.bounding_box(), panel.bounding_box()
    assert box["y"] >= button["y"] + button["height"]
    assert (
        panel_box["x"] <= box["x"]
        and box["x"] + box["width"] <= panel_box["x"] + panel_box["width"]
    )
    middle = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    assert page.evaluate(
        "([x, y]) => !!document.elementFromPoint(x, y).closest('.term-hint')", middle
    )
    shot(page, "hint")
    page.emulate_media(color_scheme="dark")
    shot(page, "hint-dark")
    page.emulate_media(color_scheme="light")

    # Typing while viewing reaches nobody.
    view.locator(".xterm").click()
    page.keyboard.type("lines 5\n")
    page.wait_for_timeout(500)
    inputs = (agent_helpers.fake_logs(session, "w1") / "inputs.jsonl").read_text()
    assert "lines 5" not in inputs

    view.get_by_role("button", name="Take control").click()
    expect(hint).to_have_count(0)
    page.get_by_role("dialog").get_by_role("button", name="Take control").click()
    expect(view).to_contain_text("In control")
    expect(view.get_by_role("status")).to_have_text("live")
    shot(page, "control")


def test_dont_ask_again_takes_control_at_once_after_a_reload(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("status")).to_have_text("live")
    take = panel.get_by_role("button", name="Take control")
    assert "goes straight to supervisor" in take.get_attribute("title")
    take.click()
    ask = page.get_by_role("dialog", name="Take control of supervisor")
    page.keyboard.press("Escape")  # Esc is Cancel
    expect(ask).to_have_count(0)
    expect(panel).to_contain_text("Viewing")
    take.click()
    ask.get_by_role("checkbox", name="Don't ask again").check()
    shot(page)
    ask.get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("In control")

    page.reload()
    expect(panel.get_by_role("status")).to_have_text("live")
    panel.get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("In control")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_expand_shows_the_terminal_over_the_page_with_the_same_socket(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    sockets = []
    page.on("websocket", lambda socket: sockets.append(socket.url))
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("status")).to_have_text("live")
    narrow = panel.bounding_box()
    panel.get_by_role("button", name="Expand terminal").click()
    content = page.locator(".content").bounding_box()
    wide = panel.bounding_box()
    assert wide == content  # the whole content: the rail and the top bar stay
    assert wide["width"] > narrow["width"]
    expect(panel.get_by_role("status")).to_have_text("live")
    shot(page)

    # In control Esc goes to the agent; Restore terminal puts the panel back.
    panel.get_by_role("button", name="Take control").click()
    page.get_by_role("dialog").get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("In control")
    expect(panel.get_by_role("status")).to_have_text("live")
    panel.locator(".xterm").click()
    page.keyboard.press("Escape")
    page.keyboard.type("after esc")
    page.keyboard.press("Enter")
    expect(panel).to_have_class("terminals expanded")
    inputs = agent_helpers.fake_logs(session, "supervisor") / "inputs.jsonl"
    agent_helpers.wait_for(
        lambda: inputs.exists() and '"\\u001bafter esc"' in inputs.read_text(),
        "Esc at the agent",
        session,
    )
    panel.get_by_role("button", name="Restore terminal").click()
    assert panel.bounding_box()["width"] == narrow["width"]
    expect(panel).to_contain_text("In control")

    # In view Esc puts it back.
    panel.get_by_role("button", name="Release").click()
    panel.get_by_role("button", name="Expand terminal").click()
    panel.locator(".xterm").click()
    page.keyboard.press("Escape")
    expect(panel).to_have_class("terminals")
    # One socket to view, one in control, one to view again: expanding opened none.
    assert [url.rsplit("=", 1)[1] for url in sockets] == ["view", "control", "view"]


def test_the_supervisors_terminal_comes_back_live_when_its_stopped_session_resumes(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    runtime.stop_session(session)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    status = panel.get_by_role("tabpanel", name="supervisor").get_by_role("status")
    expect(status).to_contain_text("closed")
    expect(panel.get_by_role("button", name="Reconnect")).to_be_visible()
    shot(page, "stopped")

    runtime.start_session(str(repo), session, None, "fake")
    expect(status).to_have_text("live", timeout=20_000)  # no reload
    shot(page, "resumed")
