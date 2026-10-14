"""The session's Flows tab in a browser: the overview of its runs in two foldable groups,
the open ones as cards with their flow's states, searched from the tab bar; a run's page in
its place with its states, what goes on now (its gate, answered there) and its history of
events, the page following the feed without a reload."""

import re
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import artifacts, loop, runs, runtime, state

pytestmark = pytest.mark.ui

SHIP = """\
name: ship
description: the supervisor plans and builds it, the human approves it
start: plan
states:
  plan: {agent: supervisor, do: sleep 0, produces: [plan], outcomes: {ready: build}}
  build:
    agent: supervisor
    do: sleep 0
    max_visits: 3
    outcomes: {done: check, again: build}
  check:
    gate: approval
    ask: Ship it?
    reads: [plan]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""

BUILT = """\
## Built

- The form has **two steps** now.
- `make check` is green."""


def flow_session(repo, name: str, flow: str) -> str:
    """A running session of the fake agent with kit uiflow, which has the flow `name`."""
    kit = repo.parent / "kits" / "uiflow"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uiflow\nversion: 1.0.0\n")
    (kit / "flows" / f"{name}.yaml").write_text(flow)
    agent_helpers.install_kit(kit)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uiflow"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    return session


def flows_session(repo) -> str:
    """A running session of the fake agent with two runs: ship/x took two steps and waits
    at gate "check", ship/y is at its first step."""
    session = flow_session(repo, "ship", SHIP)
    runs.start(session, "ship", "Add a login page", name="x")
    artifacts.write(session, "supervisor", "ship/x/plan", "a form in two steps")
    runs.advance(session, "supervisor", "ship/x", "ready", "the plan: a form in two steps")
    runs.advance(session, "supervisor", "ship/x", "done", "built the form", BUILT)
    runs.start(session, "ship", "Add a logout button", name="y")
    return session


REVIEWED = """\
name: reviewed
description: built, then reviewed until approved
start: build
states:
  build: {agent: supervisor, do: sleep 0, outcomes: {ready: review}}
  review:
    agent: supervisor
    do: sleep 0
    max_visits: 3
    outcomes: {changes: build, again: review, approved: end}
  end: {end: true}
"""


def reviewed_session(repo) -> str:
    """A running session whose run reviewed/x went ready, changes, ready and again: forward,
    back, forward and back (a stay), by its flow's order (docs/design/ui.md, Flow events)."""
    session = flow_session(repo, "reviewed", REVIEWED)
    runs.start(session, "reviewed", "Add a login page", name="x")
    for outcome, note in [
        ("ready", "built it"),
        ("changes", "two findings"),
        ("ready", "fixed both"),
        ("again", "one more look"),
    ]:
        runs.advance(session, "supervisor", "reviewed/x", outcome, note)
    return session


def tone(chip) -> str:
    """Which of the UI's colours a chip's text has: done, human or another."""
    return chip.evaluate(
        """chip => {
            const of = (token) => {
                const probe = document.createElement("span");
                probe.style.color = `var(${token})`;
                document.body.append(probe);
                const colour = getComputedStyle(probe).color;
                probe.remove();
                return colour;
            };
            const colour = getComputedStyle(chip).color;
            return colour === of("--done") ? "done" : colour === of("--human") ? "human" : colour;
        }"""
    )


def tooltip_lines(page: Page, chip) -> list[str]:
    """The lines of the UI's tooltip that hovering the chip shows."""
    chip.hover()
    tip = page.get_by_role("tooltip")
    expect(tip).to_be_visible()
    lines = tip.locator(".tooltip-line").all_inner_texts()
    page.mouse.move(0, 0)
    expect(tip).to_have_count(0)
    return lines


def read_out(region) -> list[str]:
    """Each step's outcome and direction as the browser's accessibility tree reads them out
    in the region (its aria snapshot, which puts a space between the chip's text and the
    hidden text after it), in order."""
    said = re.findall(r"(\w+) ?, a step (back|forward)", region.aria_snapshot())
    return [f"{outcome}, a step {way}" for outcome, way in said]


FORWARD = ["Forward in the flow, to review"]
BACK = ["Back: the work returns to build", "Runs again: build › review"]
STAY = ["Back: the work returns to review", "Runs again: review"]


def test_a_step_back_has_the_return_icon_and_each_step_says_where_it_goes(
    page: Page, server, repo, shot
):
    """The run's history colours a step by its flow's order, as the chat does (AC-4, AC-6)."""
    page.set_viewport_size({"width": 1600, "height": 1000})
    session = reviewed_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/flows/reviewed%2Fx")
    events = page.get_by_role("region", name="Run reviewed/x").get_by_role("list", name="Events")
    chips = events.locator(".feed-chip")  # the newest first
    expect(chips).to_have_text(["again", "ready", "changes", "ready"])
    expect(chips.locator("svg")).to_have_count(2)
    assert read_out(events) == [
        "again, a step back",
        "ready, a step forward",
        "changes, a step back",
        "ready, a step forward",
    ]
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        assert [tone(chips.nth(n)) for n in range(4)] == ["human", "done", "human", "done"]
        chips.nth(2).hover()
        expect(page.get_by_role("tooltip")).to_be_visible()
        shot(page, f"{theme}-back")
        page.mouse.move(0, 0)
    page.emulate_media(color_scheme="light")
    assert [tooltip_lines(page, chips.nth(n)) for n in range(4)] == [STAY, FORWARD, BACK, FORWARD]


def tab_bar_fit(page: Page) -> dict:
    """How the session's tab bar holds its open search: whether it scrolls, whether the
    search and every tab lie inside it, and which tabs the search covers."""
    return page.get_by_role("navigation", name="Session sections").evaluate(
        """bar => {
            const box = bar.getBoundingClientRect();
            const find = bar.querySelector(".tab-find").getBoundingClientRect();
            const inside = (r) => r.left >= box.left && r.right <= box.right;
            const tabs = [...bar.querySelectorAll(".tab-item")];
            return {
                scrollLeft: bar.scrollLeft,
                scrolls: bar.scrollWidth > bar.clientWidth,
                find_inside: inside(find),
                tabs_inside: tabs.every((one) => inside(one.getBoundingClientRect())),
                tabs_covered: tabs
                    .filter((one) => one.getBoundingClientRect().right > find.left)
                    .map((one) => one.getAttribute("aria-label") ?? one.textContent.trim()),
            };
        }"""
    )


def test_a_runs_page_shows_its_flow_and_steps_and_its_gate_is_answered_there(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1600, "height": 1000})
    session = flows_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    # With the terminals collapsed the session's column is wide enough for the list and the
    # page side by side.
    page.get_by_role("button", name="Collapse terminals").click()
    page.get_by_role("link", name="Flows · 2").click()
    # The overview across the whole column, also when it is wide: no run opens by itself.
    runs_list = page.get_by_role("navigation", name="Flow runs")
    expect(runs_list).to_be_visible()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows")
    expect(page.get_by_role("region", name=re.compile("^Run "))).to_have_count(0)
    # Active (green), the waiting run first, each a card with its flow's states.
    active = runs_list.get_by_role("region", name="Active")
    expect(active.get_by_role("heading", level=3)).to_have_class(re.compile(r"\btone-done\b"))
    cards = active.get_by_role("link")
    expect(cards).to_have_count(2)
    waiting, acting = cards.first, cards.last
    expect(waiting).to_contain_text("check · gate #1")
    expect(waiting).to_have_class(re.compile(r"\bwaits\b"))
    expect(waiting.locator(".pill")).to_have_text("Waits for you")
    expect(waiting.get_by_role("listitem", name="State check")).to_have_class(
        re.compile(r"\bwaiting\b")
    )
    expect(waiting.get_by_role("listitem", name="State build")).to_have_text("build1/3")
    expect(acting).to_contain_text("ship/y")
    expect(acting.locator(".pill")).to_have_count(0)
    expect(acting.get_by_role("listitem", name="State plan")).to_have_attribute(
        "aria-current", "step"
    )
    expect(active.locator(".group-count")).to_have_text("2")
    # History is folded by default.
    expect(runs_list.get_by_role("button", name=re.compile("^History"))).to_have_attribute(
        "aria-expanded", "false"
    )
    shot(page, "overview")
    page.emulate_media(color_scheme="dark")
    shot(page, "overview-dark")
    page.emulate_media(color_scheme="light")
    # In the wide bar the open search sits at its right end beside the tabs, covering none.
    page.get_by_role("button", name="Find a run").click()
    expect(page.get_by_role("searchbox", name="Find a run")).to_be_focused()
    assert tab_bar_fit(page) == {
        "scrollLeft": 0,
        "scrolls": False,
        "find_inside": True,
        "tabs_inside": True,
        "tabs_covered": [],
    }
    shot(page, "search")
    page.keyboard.press("Escape")
    expect(page.get_by_role("searchbox", name="Find a run")).to_have_count(0)

    waiting.click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    expect(runs_list).to_have_count(0)
    run = page.get_by_role("region", name="Run ship/x")
    expect(run.get_by_role("heading", name="ship/x", exact=True)).to_be_visible()
    expect(run.locator(".run-head .pill")).to_have_text("Waits for you")
    expect(run.locator(".run-task-first")).to_have_text("Add a login page")
    expect(run.get_by_role("listitem", name="State check")).to_have_class(
        re.compile(r"\bwaiting\b")
    )
    expect(run.get_by_role("listitem", name="State build")).to_have_text("build1/3")
    expect(run.get_by_role("listitem", name="State build")).to_have_attribute("title", "supervisor")
    plan = run.get_by_role("listitem", name="State plan")
    expect(plan).to_have_attribute("title", "supervisor · writes plan")
    expect(run.get_by_role("listitem", name="State check")).to_have_attribute(
        "title", "you · reads plan"
    )
    expect(run.get_by_role("list", name="Ways back")).to_have_count(0)
    # Now: the gate, compact, without its note and what it reads (they are in the history).
    now = run.get_by_role("region", name="Now")
    expect(now).to_contain_text("Waits for you")
    card = now.get_by_role("article", name="Gate #1", exact=True)
    expect(card).to_contain_text("Ship it?")
    expect(card.get_by_role("list", name="Artifacts it reads")).to_have_count(0)
    # The history, the newest first; the latest step with a note is open.
    events = run.get_by_role("list", name="Events")
    tops = events.locator(".feed-top")
    rows = events.locator(":scope > li")  # a note's Markdown has list items of its own
    expect(tops).to_have_text(
        [
            "supervisor build done, a step forward → check",
            "supervisor plan ready, a step forward → build",
            "supervisor started the run",
        ]
    )
    built = rows.first
    expect(built.get_by_role("button", name="built the form")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(built.locator(".feed-facts")).to_contain_text("From")
    expect(built.locator(".chat-body strong").filter(has_text="two steps")).to_be_visible()
    shot(page, "waiting")

    # Another step opens on a click.
    plan = rows.nth(1)
    plan.get_by_role("button", name="the plan: a form in two steps").click()
    expect(plan.locator(".feed-facts")).to_contain_text("ready")

    card.get_by_role("textbox", name="Comment for the next step (optional)").fill("ship it")
    card.get_by_role("button", name="Approve", exact=True).click()
    # The feed brings the answer: no reload.
    expect(card).to_have_count(0)
    expect(now).to_contain_text("Ended ·")
    expect(run.locator(".run-head .pill")).to_have_text("Ended")
    # The end comes first, the human's answer after it, open with its note.
    expect(tops.first).to_have_text("ended the run")
    expect(tops.nth(1)).to_have_text("you check approved, a step forward → end")
    answer = rows.nth(1)
    expect(answer.get_by_role("button", name=re.compile("^approved: ship it"))).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(events).not_to_contain_text("at end")  # the end's detail is in Now only
    expect(now).to_contain_text("at end")
    expect(run.get_by_role("listitem", name="State end")).to_have_attribute("aria-current", "step")
    expect(page.get_by_role("link", name="Flows · 1")).to_be_visible()
    assert state.get_run(session, "ship/x").status == state.ENDED
    # The order turns, and the start comes first.
    run.get_by_role("button", name="Newest first ↓").click()
    expect(tops.first).to_have_text("supervisor started the run")
    expect(tops.last).to_have_text("ended the run")
    run.get_by_role("button", name="Oldest first ↑").click()
    shot(page, "ended")
    # Back on the overview, the ended run is a row of History, opened by its heading.
    page.get_by_role("link", name="‹ All runs (1 open, 1 ended)").click()
    runs_list.get_by_role("button", name=re.compile("^History")).click()
    history = runs_list.get_by_role("region", name="History")
    expect(history.get_by_role("link")).to_contain_text("ended")
    expect(history.get_by_role("list", name="States")).to_have_count(0)


def test_in_a_narrow_column_the_overview_is_searched_from_the_tab_bar_and_a_run_has_the_way_back(
    page: Page, server, repo, shot
):
    # Wide enough for the four tabs with their counts (Agents, Flows, Artifacts), narrow
    # enough for the overview alone.
    page.set_viewport_size({"width": 1480, "height": 900})
    session = flows_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    # The terminals are open: the session's column is narrower than 900 px.
    expect(page.get_by_role("button", name="Collapse terminals")).to_be_visible()
    expect(page.get_by_role("button", name="Find a run")).to_have_count(0)
    page.get_by_role("link", name="Flows · 2").click()
    runs_list = page.get_by_role("navigation", name="Flow runs")
    expect(runs_list).to_be_visible()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows")
    expect(runs_list.get_by_role("region", name="Active").get_by_role("link")).to_have_count(2)
    expect(runs_list.get_by_role("list", name="States")).to_have_count(2)
    expect(page.get_by_role("region", name=re.compile("^Run "))).to_have_count(0)
    shot(page, "overview")
    # The search is in the tab bar: "/" opens it; it is the address's ?find=.
    expect(page.get_by_role("searchbox", name="Find a run")).to_have_count(0)
    page.keyboard.press("/")  # the focus is on the Flows tab, a link
    search = page.get_by_role("searchbox", name="Find a run")
    expect(search).to_be_focused()
    search.fill("logout")
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows?find=logout")
    expect(runs_list.get_by_role("link")).to_have_count(1)
    # The open field fits the narrow bar: nothing scrolls, it lies over the last tabs, and
    # Activity and the magnifier show whole.
    fit = tab_bar_fit(page)
    covered = fit.pop("tabs_covered")
    assert fit == {"scrollLeft": 0, "scrolls": False, "find_inside": True, "tabs_inside": True}
    assert "Flows · 2" in covered and "Activity" not in covered
    shot(page, "search")
    runs_list.get_by_role("link", name="ship/y").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows/ship%2Fy")
    run = page.get_by_role("region", name="Run ship/y")
    expect(run.get_by_role("region", name="Now")).to_contain_text("supervisor · plan · visit 1")
    expect(runs_list).to_have_count(0)
    expect(page.get_by_role("button", name="Find a run")).to_have_count(0)
    shot(page, "run")
    page.get_by_role("link", name="‹ All runs (2 open, 0 ended)").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows?find=logout")
    expect(page.get_by_role("searchbox", name="Find a run")).to_have_value("logout")
    expect(runs_list.get_by_role("link")).to_have_count(1)
    # The browser's Back from a run's page comes back the same way.
    runs_list.get_by_role("link", name="ship/y").click()
    expect(run).to_be_visible()
    page.go_back()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows?find=logout")
    expect(runs_list.get_by_role("link")).to_have_count(1)
