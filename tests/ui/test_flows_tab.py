"""The session's Flows tab in a browser: the runs in two groups, a run's page with its
states, what goes on now (its gate, answered there) and its history of events, the page
following the feed without a reload."""

import re
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import loop, runs, runtime, state

pytestmark = pytest.mark.ui

SHIP = """\
name: ship
description: the supervisor plans and builds it, the human approves it
start: plan
states:
  plan: {agent: supervisor, do: sleep 0, outcomes: {ready: build}}
  build:
    agent: supervisor
    do: sleep 0
    max_visits: 3
    outcomes: {done: check, again: build}
  check:
    gate: approval
    ask: Ship it?
    needs: [build]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""

BUILT = """\
## Built

- The form has **two steps** now.
- `make check` is green."""


def flows_session(repo) -> str:
    """A running session of the fake agent with two runs: ship/x took two steps and waits
    at gate "check", ship/y is at its first step."""
    kit = repo / ".lado" / "kits" / "uiflow"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uiflow\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uiflow"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    runs.start(session, "ship", "Add a login page", name="x")
    runs.advance(session, "supervisor", "ship/x", "ready", "the plan: a form in two steps")
    runs.advance(session, "supervisor", "ship/x", "done", "built the form", BUILT)
    runs.start(session, "ship", "Add a logout button", name="y")
    return session


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
    # The first run that waits for the human opens.
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    expect(page.get_by_role("link", name="Flows · 2")).to_be_visible()
    runs_list = page.get_by_role("navigation", name="Flow runs")
    # Two groups, both open: Active, the waiting run first; History, empty yet.
    active = runs_list.get_by_role("region", name="Active")
    expect(active.get_by_role("link")).to_have_count(2)
    expect(active.get_by_role("link").first).to_contain_text("check · gate #1")
    expect(active.get_by_role("link").first).to_have_class(re.compile(r"\bwaits\b"))
    expect(active.get_by_role("link").last).to_contain_text("ship/y")
    expect(active.locator(".group-count")).to_have_text("2")
    history = runs_list.get_by_role("region", name="History")
    expect(history).to_contain_text("No ended runs yet")
    expect(runs_list.get_by_role("region", name="Waiting for you")).to_have_count(0)
    expect(runs_list.get_by_role("button")).to_have_count(0)  # nothing folds

    run = page.get_by_role("region", name="Run ship/x")
    expect(run.get_by_role("heading", name="ship/x", exact=True)).to_be_visible()
    expect(run.locator(".run-head .pill")).to_have_text("Waits for you")
    expect(run.locator(".run-task-first")).to_have_text("Add a login page")
    expect(run.get_by_role("listitem", name="State check")).to_have_class(
        re.compile(r"\bwaiting\b")
    )
    expect(run.get_by_role("listitem", name="State build")).to_have_text("build1/3")
    expect(run.get_by_role("listitem", name="State build")).to_have_attribute("title", "supervisor")
    expect(run.get_by_role("list", name="Ways back")).to_have_count(0)
    # Now: the gate, compact, without the notes it needs (they are in the history).
    now = run.get_by_role("region", name="Now")
    expect(now).to_contain_text("Waits for you")
    card = now.get_by_role("article", name="Gate #1", exact=True)
    expect(card).to_contain_text("Ship it?")
    expect(card.get_by_role("list", name="Notes it needs")).to_have_count(0)
    # The history, the newest first; the latest step with a note is open.
    events = run.get_by_role("list", name="Events")
    tops = events.locator(".feed-top")
    rows = events.locator(":scope > li")  # a note's Markdown has list items of its own
    expect(tops).to_have_text(
        [
            "supervisor build done → check",
            "supervisor plan ready → build",
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
    expect(tops.nth(1)).to_have_text("you check approved → end")
    answer = rows.nth(1)
    expect(answer.get_by_role("button", name=re.compile("^approved: ship it"))).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(events).not_to_contain_text("at end")  # the end's detail is in Now only
    expect(now).to_contain_text("at end")
    expect(run.get_by_role("listitem", name="State end")).to_have_attribute("aria-current", "step")
    expect(page.get_by_role("link", name="Flows · 1")).to_be_visible()
    expect(history.get_by_role("link")).to_contain_text("ended")
    assert state.get_run(session, "ship/x").status == state.ENDED
    # The order turns, and the start comes first.
    run.get_by_role("button", name="Newest first ↓").click()
    expect(tops.first).to_have_text("supervisor started the run")
    expect(tops.last).to_have_text("ended the run")
    run.get_by_role("button", name="Oldest first ↑").click()
    shot(page, "ended")


def test_in_a_narrow_column_the_runs_take_it_and_a_run_has_the_way_back(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = flows_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    # The terminals are open: the session's column is narrower than 900 px.
    expect(page.get_by_role("button", name="Collapse terminals")).to_be_visible()
    page.get_by_role("link", name="Flows · 2").click()
    runs_list = page.get_by_role("navigation", name="Flow runs")
    expect(runs_list).to_be_visible()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows")
    expect(page.get_by_role("combobox")).to_have_count(0)
    expect(page.get_by_role("region", name=re.compile("^Run "))).to_have_count(0)
    shot(page, "list")
    page.get_by_role("searchbox", name="Find a run").fill("logout")
    expect(runs_list.get_by_role("link")).to_have_count(1)
    runs_list.get_by_role("link", name="ship/y").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows/ship%2Fy")
    run = page.get_by_role("region", name="Run ship/y")
    expect(run.get_by_role("region", name="Now")).to_contain_text("supervisor · plan · visit 1")
    expect(runs_list).to_have_count(0)
    shot(page, "run")
    page.get_by_role("link", name="‹ All runs (2 open, 0 ended)").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/flows")
    expect(page.get_by_role("searchbox", name="Find a run")).to_have_value("logout")
    expect(runs_list.get_by_role("link")).to_have_count(1)
