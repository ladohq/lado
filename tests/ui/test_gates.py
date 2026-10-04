"""Flow gates in a session's chat, in a browser: the human answers a gate on its card, and
a gate answered elsewhere (`lado answer`) folds into a line on the open page."""

import subprocess
import sys
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import loop, runs, runtime, state

pytestmark = pytest.mark.ui

SHIP = """\
name: ship
description: the supervisor plans it, the human approves it
start: plan
states:
  plan: {agent: supervisor, do: sleep 0, outcomes: {ready: check}}
  check:
    gate: approval
    ask: Build it as planned?
    needs: [plan]
    outcomes: {approved: end, rejected: plan}
  end: {end: true}
"""

REVIEW = """\
## Review of the plan

- The form is **too big** for one step.
- Tests: `make check` is green.

Split it in two, then ship."""


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def gated_session(repo) -> str:
    """A running session of the fake agent whose run ship/x waits at gate "check"."""
    kit = repo / ".lado" / "kits" / "uiflow"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uiflow\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uiflow"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    runs.start(session, "ship", "Add a login page", name="x")
    runs.advance(session, "supervisor", "ship/x", "ready", "the plan is reviewed", REVIEW)
    return session


def test_the_human_answers_a_gate_on_its_card(page: Page, server, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = page.get_by_role("article", name="Gate #1", exact=True)
    expect(card.get_by_role("heading", name="Gate #1 · ship/x · check")).to_be_visible()
    expect(card).to_contain_text("Build it as planned?")
    expect(card.locator("strong").first).to_have_text("the plan is reviewed")
    expect(card).to_contain_text("Split it in two, then ship.")
    expect(page.get_by_text("Gate #1 waits:")).to_be_visible()
    card.get_by_role("button", name="Note from plan: the plan is reviewed").click()
    shot(page, "card")
    card.get_by_role("textbox", name="Comment for the next step (optional)").fill(
        "split the form first"
    )
    card.get_by_role("button", name="Reject").click()
    line = page.get_by_role("article", name="Gate #1", exact=True)
    expect(line).to_contain_text("Gate #1 · ship/x · check: reject by human")
    expect(line).to_contain_text("split the form first")
    expect(line.get_by_role("button", name="Approve", exact=True)).to_have_count(0)
    expect(page.get_by_text("Gate #1 waits:")).to_have_count(0)
    run = state.get_run(session, "ship/x")
    assert (run.state, run.note) == ("plan", "rejected: split the form first")
    step = [m for m in state.list_messages(session) if m.recipient == "supervisor"][-1]
    assert "Note from the previous step: rejected: split the form first" in step.body
    line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human").click()
    expect(line).to_contain_text("Build it as planned?")
    shot(page, "answered")


def test_the_humans_answer_is_their_bubble_at_the_bottom_and_leads_to_the_gate(
    page: Page, server, repo, shot
):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    feed = page.get_by_role("log", name="Chat with the session")
    card = feed.get_by_role("article", name="Gate #1", exact=True)
    card.get_by_role("textbox", name="Comment for the next step (optional)").fill("ship it")
    card.get_by_role("button", name="Approve", exact=True).click()
    bubble = feed.get_by_role("article", name="Your answer to gate #1")
    expect(bubble).to_contain_text("Gate #1 · approve")
    expect(bubble).to_contain_text("ship it")
    # The run's events after the answer (the run moved on) may follow it as lines.
    expect(feed.locator(":scope > article").last).to_have_attribute(
        "aria-label", "Your answer to gate #1"
    )
    expect(bubble).to_be_in_viewport()
    shot(page, "bubble")
    bubble.get_by_role("link", name="Gate #1 · approve").click()
    expect(card).to_be_in_viewport()
    expect(card).to_contain_text("Gate #1 · ship/x · check: approve by human")


def test_a_gate_answered_with_lado_answer_folds_on_the_open_page(page: Page, server, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = page.get_by_role("article", name="Gate #1", exact=True)
    expect(card.get_by_role("button", name="Approve", exact=True)).to_be_visible()
    answer = subprocess.run(
        [sys.executable, "-m", "lado.cli", "answer", session, "1", "approve", "-m", "ship it"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert answer.returncode == 0, answer.stderr
    expect(card).to_contain_text("Gate #1 · ship/x · check: approve by human")
    expect(card).to_contain_text("ship it")
    expect(card.get_by_role("button", name="Approve", exact=True)).to_have_count(0)
    shot(page)
