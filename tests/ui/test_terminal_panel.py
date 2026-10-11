"""Agents' terminals in a browser, in the panel on the right: the supervisor's opened from
its chip to view, then taken control of and typed into; another agent's opened from the
Agents tab to view, where the wheel up points at Take control."""

import re

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui


def test_the_supervisors_terminal_opens_to_view_and_takes_what_the_human_types_in_control(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tab", name="supervisor")).to_have_attribute("aria-selected", "true")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    expect(panel).to_contain_text("Viewing")
    panel.get_by_role("button", name="Take control").click()
    ask = page.get_by_role("dialog", name="Take control of supervisor")
    expect(ask).to_be_visible()
    shot(page, "ask")
    ask.get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("You're typing into supervisor")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
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
    # The lines come from its task: keys typed into its window would race LADO's paste of it.
    runtime.spawn_worker(session, "lines 120", name="w1")
    agent_helpers.wait_for(
        lambda: (
            agent_helpers.unreceived(session, "w1") == 0
            and state.get_agent(session, "w1").status == state.IDLE
        ),
        "w1 idle after its task",
        session,
    )
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1")
    agent = page.get_by_role("region", name="Agent w1")
    agent.get_by_role("button", name="Open terminal").click()

    panel = page.get_by_role("complementary", name="Terminals")
    view = panel.get_by_role("tabpanel", name="w1")
    expect(view.locator(".term")).to_have_attribute("data-link", "open")
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
    expect(view).to_contain_text("You're typing into w1")
    expect(view.locator(".term")).to_have_attribute("data-link", "open")
    shot(page, "control")


def test_dont_ask_again_takes_control_at_once_after_a_reload(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
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
    expect(panel).to_contain_text("You're typing into supervisor")

    page.reload()
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    panel.get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("You're typing into supervisor")
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
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    narrow = panel.bounding_box()
    panel.get_by_role("button", name="Expand terminal").click()
    content = page.locator(".content").bounding_box()
    wide = panel.bounding_box()
    assert wide == content  # the whole content: the rail and the top bar stay
    assert wide["width"] > narrow["width"]
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    shot(page)

    # In control Esc goes to the agent; Restore terminal puts the panel back.
    panel.get_by_role("button", name="Take control").click()
    page.get_by_role("dialog").get_by_role("button", name="Take control").click()
    expect(panel).to_contain_text("You're typing into supervisor")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
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
    expect(panel).to_contain_text("You're typing into supervisor")

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
    view = panel.get_by_role("tabpanel", name="supervisor")
    status = view.get_by_role("status")
    expect(status).to_have_text(f'closed: session "{session}" is stopped')
    expect(view.get_by_role("alert")).to_have_count(0)  # the reason once
    expect(panel.get_by_role("button", name="Reconnect")).to_be_visible()
    expect(panel.get_by_role("button", name="Take control")).to_have_count(0)
    shot(page, "stopped")

    runtime.start_session(str(repo), session, None, "fake")
    expect(view.locator(".term")).to_have_attribute(
        "data-link", "open", timeout=20_000
    )  # no reload
    expect(status).to_have_text("")
    shot(page, "resumed")


def colour(page: Page, value: str) -> str:
    """A colour as the browser computes it, for comparing with an element's."""
    return page.evaluate(
        """value => {
            const probe = document.createElement("div");
            probe.style.color = value;
            document.querySelector(".term").append(probe);
            const out = getComputedStyle(probe).color;
            probe.remove();
            return out;
        }""",
        value,
    )


def hide_the_page(page: Page) -> None:
    page.evaluate(
        """() => {
            const hidden = {configurable: true, get: () => "hidden"};
            Object.defineProperty(document, "visibilityState", hidden);
            document.dispatchEvent(new Event("visibilitychange"));
        }"""
    )


def test_control_is_marked_and_ends_by_itself(page: Page, server, repo, shot):
    session = running_session(repo)
    sockets = []  # the page's side of each terminal socket, to drop one
    page.route_web_socket(
        re.compile(r".*/terminal\?mode=.*"),
        lambda ws: (ws.connect_to_server(), sockets.append(ws)),
    )
    log_in(page, server)
    page.evaluate("() => localStorage.setItem('lado.askControl', 'never')")
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    term = panel.locator(".term")
    tools = panel.locator(".term-tools")
    tab = panel.get_by_role("tab", name=re.compile("^supervisor,"))
    expect(term).to_have_attribute("data-link", "open")
    expect(panel.get_by_role("status")).to_have_text("")  # no word while it is open
    expect(tools).to_contain_text("Viewing")
    expect(tab.get_by_role("img", name="In control")).to_have_count(0)
    shot(page, "view")

    panel.get_by_role("button", name="Take control").click()
    expect(term).to_have_attribute("data-mode", "control")
    expect(term).to_have_attribute("data-link", "open")
    expect(tools).to_contain_text("You're typing into supervisor")
    action = colour(page, "var(--action)")
    assert tools.evaluate("e => getComputedStyle(e).backgroundColor") == colour(
        page, "var(--action-ground)"
    )
    assert panel.locator(".term-control").evaluate("e => getComputedStyle(e).color") == action
    release = panel.get_by_role("button", name="Release")
    assert release.evaluate("e => getComputedStyle(e).borderTopColor") == action
    frame = panel.locator(".term-screen").evaluate("e => getComputedStyle(e).boxShadow")
    assert frame.startswith(action) and frame.endswith("0px 0px 0px 2px inset")
    expect(tab.get_by_role("img", name="In control")).to_be_visible()
    shot(page, "control")
    page.emulate_media(color_scheme="dark")
    shot(page, "control-dark")
    page.emulate_media(color_scheme="light")

    # The page hidden: back to view, silently.
    hide_the_page(page)
    expect(term).to_have_attribute("data-mode", "view")
    expect(tab.get_by_role("img", name="In control")).to_have_count(0)
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(panel.get_by_role("alert")).to_have_count(0)
    page.evaluate("() => { delete document.visibilityState; }")

    # The control socket lost after it was open: back to view, the reason in the bar.
    expect(term).to_have_attribute("data-link", "open")
    panel.get_by_role("button", name="Take control").click()
    expect(term).to_have_attribute("data-link", "open")
    expect(term).to_have_attribute("data-mode", "control")
    sockets[-1].close(code=4500, reason="the terminal closed")
    expect(term).to_have_attribute("data-mode", "view")
    expect(term).to_have_attribute("data-link", "open")
    view_socket = sockets[-1]
    view_socket.close(code=4500, reason="the terminal closed")
    expect(panel.get_by_role("status")).to_have_text("reconnecting: the terminal closed")
    take = panel.get_by_role("button", name="Take control")
    expect(take).to_be_disabled()
    expect(take).to_have_attribute("title", "No connection to the terminal yet")
    shot(page, "reconnecting")
    expect(term).to_have_attribute("data-link", "open")  # by itself, after RETRY_MS

    # The ring turns, but not for those who ask for less motion.
    spin = """() => {
        const ring = document.createElement("span");
        ring.className = "term-spin";
        document.querySelector(".term-tools").append(ring);
        const name = getComputedStyle(ring).animationName;
        ring.remove();
        return name;
    }"""
    assert page.evaluate(spin) == "term-spin"
    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate(spin) == "none"
    page.emulate_media(reduced_motion="no-preference")


def test_a_narrow_panel_keeps_the_control_words_on_one_line(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    log_in(page, server)
    page.evaluate(
        """() => {
            localStorage.setItem('lado.askControl', 'never');
            localStorage.setItem('lado.terminals', JSON.stringify({width: 280, collapsed: false}));
        }"""
    )
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    assert round(panel.bounding_box()["width"]) == 280
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    panel.get_by_role("button", name="Take control").click()
    expect(panel.locator(".term")).to_have_attribute("data-mode", "control")
    words = panel.locator(".term-control-words")
    name = panel.locator(".term-control-agent")
    release = panel.get_by_role("button", name="Release")
    middle = lambda box: box["y"] + box["height"] / 2  # noqa: E731
    assert abs(middle(words.bounding_box()) - middle(release.bounding_box())) < 2
    assert words.evaluate("e => e.scrollWidth <= e.clientWidth")  # never cut
    assert name.evaluate("e => e.scrollWidth > e.clientWidth")  # cut with "…"
    assert name.evaluate("e => getComputedStyle(e).textOverflow") == "ellipsis"
    assert panel.locator(".term-control").get_attribute("title") == "You're typing into supervisor"
    shot(page, "narrow")
