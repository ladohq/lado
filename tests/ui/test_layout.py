"""The session page's layout in a browser: the list, the session with its team and feed, and
the terminal panel on the right that a chip opens; a run's events in the feed and the
session under Needs you, from lado.db's journal to the page."""

import json
import re
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runs, runtime, state

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
    expect(view.locator(".term")).to_have_attribute("data-link", "open")  # before any click
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
    team = page.get_by_role("toolbar", name="Team")
    chips = team.get_by_role("button")
    expect(chips).to_have_count(2)
    expect(chips.first).to_have_accessible_name("supervisor, idle")
    expect(chips.nth(1)).not_to_have_attribute("title", re.compile(".*"))
    panel = page.get_by_role("complementary", name="Terminals")
    expect(chips.first).to_have_attribute("aria-pressed", "true")  # the supervisor's, at first
    shot(page, "layout")

    chips.nth(1).click()
    expect(chips.nth(1)).to_have_attribute("aria-pressed", "true")
    view = panel.get_by_role("tabpanel", name="w1")
    expect(view.locator(".term")).to_have_attribute("data-link", "open")
    expect(view).to_contain_text("Viewing")
    chat = page.get_by_role("region", name="Chat").bounding_box()
    right = panel.bounding_box()
    assert right["x"] >= chat["x"] + chat["width"]  # beside the chat, not under it
    assert right["height"] > 600  # the page's height
    shot(page, "terminal")

    chips.first.click()  # back to the supervisor's tab; w1's keeps its socket
    expect(panel.get_by_role("tab")).to_have_text(["supervisor", "w1"])
    expect(panel.get_by_role("tabpanel", name="supervisor").locator(".term")).to_have_attribute(
        "data-link", "open"
    )
    panel.get_by_role("tab", name="w1").click()
    expect(view.locator(".term")).to_have_attribute("data-link", "open")


def test_yours_all_stands_on_the_tabs_line_beside_the_open_terminal(page: Page, server, repo, shot):
    """The chat column narrow, as the terminal panel opens beside it: Yours | All stays on the
    tabs' line, and no row stands above the feed (LAD-77, LAD-197)."""
    page.set_viewport_size({"width": 1160, "height": 900})
    session = running_session(repo)
    for name in ("analyst", "developer"):
        runtime.spawn_worker(session, f"Work as {name}", name=name)
    for name in ("analyst", "developer"):
        agent_helpers.wait_for(
            lambda name=name: state.get_agent(session, name).status == state.IDLE,
            f"{name} idle",
            session,
        )
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tabpanel", name="supervisor").locator(".term")).to_have_attribute(
        "data-link", "open"
    )
    expect(page.get_by_role("toolbar", name="Team").get_by_role("button")).to_have_count(3)
    choice = page.get_by_role("radiogroup", name="Messages between agents")
    expect(choice.get_by_role("radio", name="Yours")).to_have_attribute("aria-checked", "true")
    column = page.get_by_role("region", name="Chat").bounding_box()
    assert column["width"] <= 484  # narrow: the terminal panel takes the rest
    tabs = page.get_by_role("navigation", name="Session sections").bounding_box()
    box = choice.bounding_box()
    assert tabs["y"] <= box["y"] and box["y"] + box["height"] <= tabs["y"] + tabs["height"]
    feed = page.get_by_role("log", name="Chat with the session").bounding_box()
    assert feed["y"] == tabs["y"] + tabs["height"]  # no row above it
    assert box["x"] + box["width"] <= tabs["x"] + tabs["width"]
    shot(page)


BUILD = """\
name: build
description: a worker builds it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: end}}
  end: {end: true}
"""


def chip_box(chip) -> dict:
    """What makes a team chip's look: its box and its name's font."""
    return chip.evaluate(
        """c => {
          const s = getComputedStyle(c);
          const name = getComputedStyle(c.querySelector('.team-chip-name'));
          return {height: c.getBoundingClientRect().height, radius: s.borderRadius,
                  padding: s.padding, gap: s.gap, name: name.fontWeight + ' ' + name.fontSize};
        }"""
    )


def test_a_runs_worker_is_a_chip_like_the_others_in_the_runs_frame_which_links_to_flows(
    page: Page, server, repo, shot
):
    kit = repo.parent / "kits" / "uibuild"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uibuild\nversion: 1.0.0\n")
    (kit / "flows" / "build.yaml").write_text(BUILD)
    agent_helpers.install_kit(kit)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uibuild"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    runtime.spawn_worker(session, "Look around", name="w1")
    runs.start(session, "build", "Add a login page", name="x")
    runs.spawn_worker(session, "build/x", name="dev")
    for name in ("w1", "dev"):
        agent_helpers.wait_for(
            lambda name=name: state.get_agent(session, name).status == state.IDLE,
            f"{name} idle",
            session,
        )
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    team = page.get_by_role("toolbar", name="Team")
    expect(team.get_by_role("button")).to_have_count(3)
    expect(team.get_by_role("button").first).to_have_accessible_name("supervisor, idle")
    expect(team.get_by_role("button").nth(1)).to_have_accessible_name("w1, worker, idle")
    frame = team.get_by_role("group", name="run build/x")
    chip = frame.get_by_role("button")
    expect(chip).to_have_accessible_name("dev, worker, idle")
    expect(frame).to_have_text("dev")  # no name, no state, no role
    # The session's one run is its first: the frame's dashes and icon in --run-1, no fill.
    expect(frame).to_have_attribute("data-colour", "1")
    look = frame.evaluate(
        """e => {
          const s = getComputedStyle(e), probe = document.createElement('i');
          probe.style.color = 'var(--run-1)';
          e.append(probe);
          const run = getComputedStyle(probe).color;
          probe.remove();
          const icon = getComputedStyle(e.querySelector('.team-run-link')).color;
          return [s.borderTopStyle, s.borderTopColor === run, icon === run, s.backgroundColor];
        }"""
    )
    assert look == ["dashed", True, True, "rgba(0, 0, 0, 0)"]
    link = frame.get_by_role("link", name="run build/x in Flows")
    link.focus()
    expect(page.get_by_role("tooltip")).to_have_text("flow build/x")
    shot(page, "team")
    link.blur()
    # Every chip alike, the supervisor's, its worker's and the run's: no role on any.
    expect(team.get_by_role("button")).to_have_text(["supervisor", "w1", "dev"])
    one = {"height": 24, "radius": "12px", "padding": "0px 9px", "gap": "6px", "name": "600 13px"}
    for each in team.get_by_role("button").all():
        assert chip_box(each) == one
    plain = team.get_by_role("button").first.bounding_box()
    # In the team's own wrapping row, after the supervisor's chips.
    assert frame.evaluate("e => e.parentElement.getAttribute('aria-label')") == "Team"
    # On their line now that the toggle is small (LAD-77), the taller frame centred on it.
    box = frame.bounding_box()
    assert box["y"] + box["height"] >= plain["y"] + plain["height"]
    assert box["x"] > plain["x"]

    chip.click()
    expect(chip).to_have_attribute("aria-pressed", "true")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tabpanel", name="dev").locator(".term")).to_have_attribute(
        "data-link", "open"
    )

    link.click()
    expect(page).to_have_url(re.compile(f"/sessions/{session}/flows/build%2Fx$"))


def test_the_panel_collapses_to_a_strip_and_opens_no_terminal_until_it_is_opened(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
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
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
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
    expect(panel_edge).to_have_attribute("aria-valuenow", "448")
    list_edge.hover()
    assert list_edge.evaluate("e => getComputedStyle(e).cursor") == "col-resize"
    drag(page, list_edge, 60)
    expect(panel_edge).to_have_attribute("aria-valuenow", "424")  # 40 % of what is left
    drag(page, panel_edge, -50)
    expect(list_edge).to_have_attribute("aria-valuenow", "320")
    expect(panel_edge).to_have_attribute("aria-valuenow", "474")
    page.reload()
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.locator(".term")).to_have_attribute("data-link", "open")
    assert round(page.locator(".session-list").bounding_box()["width"]) == 320
    assert round(panel.bounding_box()["width"]) == 474
    shot(page)

    # A narrower window folds the list, narrows the panel, keeps the chat, and forgets nothing.
    page.set_viewport_size({"width": 950, "height": 900})
    expect(panel_edge).to_have_attribute("aria-valuenow", "422")
    expect(list_edge).to_have_count(0)
    assert page.locator(".session-main").bounding_box()["width"] >= 420
    shot(page, "narrower")
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(panel_edge).to_have_attribute("aria-valuenow", "474")
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


# The smallest flow a run can have: the run's item in the feed is built from its snapshot.
DEMO = {
    "name": "feature",
    "description": "d",
    "start": "design",
    "states": {
        "design": {"agent": "supervisor", "do": "Design it.", "outcomes": {"ready": "done"}},
        "done": {"end": True},
    },
}


def test_a_runs_events_show_in_the_feed_and_its_gate_puts_the_session_under_needs_you(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    sessions = page.get_by_role("navigation", name="Sessions")
    expect(sessions.get_by_role("region", name="Running")).to_contain_text(session)

    run = state.Run(
        session, "feature/demo", "feature", json.dumps(DEMO), {}, "demo", "design", "/w", "b"
    )
    # A loop limit: its card reads no artifacts.
    gate = state.Gate(session, "feature/demo", "design", "loop", "Again?", ["continue", "cancel"])
    state.add_run(run, [("supervisor", state.FLOW_START, "at design")], gate)
    chat = page.get_by_role("log", name="Chat with the session")
    # The run's events are a group under the run's name, which links to the run.
    lines = chat.get_by_role("list", name="Flow run feature/demo").get_by_role("listitem")
    expect(lines.first).to_contain_text("supervisorstartedat design")
    expect(chat.get_by_role("article", name=f"Gate #{gate.id}")).to_contain_text("Again?")
    expect(
        chat.locator(".run-group").first.get_by_role("link", name="feature/demo")
    ).to_have_attribute("href", f"/sessions/{session}/flows/feature%2Fdemo")
    expect(chat.get_by_role("link", name="Flows")).to_have_count(0)
    needs_you = sessions.get_by_role("region", name="Needs you")
    expect(needs_you).to_contain_text(session)
    expect(needs_you).to_contain_text("1 gate")
    shot(page)


def test_a_chips_tooltip_says_its_name_role_and_provider(page: Page, server, repo, shot):
    session = with_worker(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chip = page.get_by_role("toolbar", name="Team").get_by_role("button", name="w1,")
    chip.hover()
    tip = page.get_by_role("tooltip")
    expect(tip.locator(".tooltip-line")).to_have_text(
        ["w1", re.compile(r"^idle · "), re.compile(r"^\w+ · fake$"), "Click to open the terminal"]
    )
    expect(chip).to_have_attribute("aria-describedby", tip.get_attribute("id"))
    shot(page)
    page.mouse.move(5, 5)
    expect(tip).to_have_count(0)


LONG_NAMES = ["reviewer-of-the-layout", "frontend-developer-two", "w3", "architect-on-call", "w5"]


def test_many_tabs_stay_on_one_line_and_scroll_with_the_supervisors_tab_kept(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    for name in LONG_NAMES:
        runtime.spawn_worker(session, "sleep 0", name=name)
    for name in LONG_NAMES:
        agent_helpers.wait_for(
            lambda name=name: state.get_agent(session, name).status == state.IDLE, name, session
        )
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents")
    narrow = json.dumps({"width": 300, "collapsed": False})
    page.evaluate(f"() => localStorage.setItem('lado.terminals', '{narrow}')")
    page.reload()
    agents = page.get_by_role("navigation", name="Agents")
    for name in LONG_NAMES:
        agents.locator(".agent-row-name", has_text=re.compile(f"^{name}$")).click()
        page.get_by_role("region", name=f"Agent {name}").get_by_role(
            "button", name="Open terminal"
        ).click()
        # The session's column is narrow: the page took it; back to the list.
        page.get_by_role("link", name="‹ All agents").click()

    panel = page.get_by_role("complementary", name="Terminals")
    tabs = panel.get_by_role("tab")
    expect(tabs).to_have_count(6)
    row = panel.get_by_role("tablist")
    ys = {round(tabs.nth(i).bounding_box()["y"]) for i in range(6)}
    assert len(ys) == 1  # one line
    # No tab is squeezed under its content: each ends where the next begins (the
    # supervisor's, sticky, lies over the others that pass under it).
    boxes = [tabs.nth(i).locator("xpath=..").bounding_box() for i in range(1, 6)]
    for one, next_one in zip(boxes, boxes[1:], strict=False):
        assert one["x"] + one["width"] <= next_one["x"] + 1
    # Nor does anything spill out of a tab.
    for tab in panel.locator(".term-tab").all():
        assert tab.evaluate("e => e.scrollWidth <= e.clientWidth"), tab.inner_text()
    assert row.evaluate("e => e.scrollWidth > e.clientWidth")  # it scrolls
    long = panel.get_by_role("tab", name="reviewer-of-the-layout").locator(".term-tab-name")
    assert long.evaluate("e => e.scrollWidth > e.clientWidth")  # cut with an ellipsis
    assert long.bounding_box()["width"] >= 70
    # The last tab opened is in view; the supervisor's stays at the left; the buttons stay.
    strip = row.bounding_box()
    last = tabs.last.bounding_box()
    assert last["x"] + last["width"] <= strip["x"] + strip["width"] + 1
    first = tabs.first.bounding_box()
    assert abs(first["x"] - strip["x"]) <= 1
    for button in ("Expand terminal", "Collapse terminals"):
        box = panel.get_by_role("button", name=button).bounding_box()
        assert box["x"] + box["width"] <= panel.bounding_box()["x"] + panel.bounding_box()["width"]
    expect(tabs.first.locator(".dot")).to_have_class("dot dot-small dot-idle")
    shot(page)

    # The wheel scrolls the tabs sideways.
    before = row.evaluate("e => e.scrollLeft")
    row.hover()
    page.mouse.wheel(0, -400)
    page.wait_for_function(
        "before => document.querySelector('.term-tabs').scrollLeft < before", arg=before
    )

    panel.get_by_role("button", name="Collapse terminals").click()
    buttons = panel.get_by_role("list", name="Agents").get_by_role("button")
    expect(buttons).to_have_count(6)
    expect(buttons.first).to_have_accessible_name("Open supervisor's terminal")
    shot(page, "collapsed")


def gives_the_focus_back(page: Page, opener, window, by: str = "Escape") -> None:
    """Opens `window` from `opener` by the keyboard and closes it by Esc or its Cancel: the
    focus is on the opener with no tooltip, and Tab goes on from there."""
    opener.focus()
    page.keyboard.press("Enter")
    expect(window).to_be_visible()
    if by == "Escape":
        page.keyboard.press("Escape")
    else:
        window.get_by_role("button", name=by).focus()
        page.keyboard.press("Enter")
    expect(window).to_have_count(0)
    expect(opener).to_be_focused()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    page.keyboard.press("Tab")
    assert opener.evaluate(
        "button => button.compareDocumentPosition(document.activeElement)"
        " & Node.DOCUMENT_POSITION_FOLLOWING"
    ), page.evaluate("document.activeElement.outerHTML.slice(0, 200)")


def test_the_session_list_and_session_windows_give_the_focus_back(page: Page, server, repo):
    session = with_worker(repo)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1?token={server['token']}")
    worker = page.get_by_role("region", name="Agent w1")
    gives_the_focus_back(
        page,
        worker.get_by_role("button", name="Finish…"),
        page.get_by_role("dialog", name="Finish w1?"),
    )
    gives_the_focus_back(
        page,
        page.get_by_role("button", name="New session"),
        page.get_by_role("dialog", name="New session"),
        "Cancel",
    )
    page.get_by_role("button", name="System").click()
    gives_the_focus_back(
        page,
        page.get_by_role("button", name="Open on another device"),
        page.get_by_role("dialog", name="Open LADO on another device"),
    )


def test_forget_gives_the_focus_back_with_no_tooltip(page: Page, server, repo):
    session = with_worker(repo)
    runtime.stop_session(session)
    page.goto(f"{server['url']}/sessions/{session}?token={server['token']}")
    forget = (
        page.get_by_role("banner").locator(".session-head").get_by_role("button", name="Forget…")
    )
    window = page.get_by_role("dialog", name=f'Forget session "{session}"?')
    gives_the_focus_back(page, forget, window)
    gives_the_focus_back(page, forget, window, "Cancel")
    # Cancel by the mouse, and the pointer gone from it: nothing shows over the button.
    forget.click()
    window.get_by_role("button", name="Cancel").click()
    expect(window).to_have_count(0)
    expect(forget).to_be_focused()
    page.mouse.move(700, 600)
    page.wait_for_timeout(500)  # past the tooltip's delay
    expect(page.get_by_role("tooltip")).to_have_count(0)


def test_add_kit_gives_the_focus_back(page: Page, server):
    page.goto(f"{server['url']}/kits/available?token={server['token']}")
    gives_the_focus_back(
        page,
        page.get_by_role("button", name="Add kit…"),
        page.get_by_role("dialog", name="Add kit"),
        "Cancel",
    )
