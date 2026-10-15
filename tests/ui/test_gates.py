"""Flow gates in a session's chat, in a browser: the human answers a gate on its tab of the
waiting card, and a gate answered elsewhere (`lado answer`) leaves the card and is a closed
line on the open page."""

import re
import subprocess
import sys
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import artifacts, loop, runs, runtime, state

pytestmark = pytest.mark.ui

SHIP = """\
name: ship
description: the supervisor plans and reviews it, the human approves it
start: plan
states:
  plan: {agent: supervisor, do: sleep 0, produces: [plan], outcomes: {ready: review}}
  review: {agent: supervisor, do: sleep 0, outcomes: {done: check}}
  check:
    gate: approval
    ask: Build it as planned?
    reads: [plan]
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


def waiting_card(page: Page, session: str):
    """The session's waiting card above the composer (or on Needs you)."""
    return page.get_by_role("region", name=f"What waits for you in {session}")


def gated_session(repo) -> str:
    """A running session of the fake agent whose run ship/x waits at gate "check": review's
    note before it carries the artifact review, and the gate reads plan."""
    kit = repo.parent / "kits" / "uiflow"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uiflow\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    agent_helpers.install_kit(kit)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uiflow"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    runs.start(session, "ship", "Add a login page", name="x")
    plan = "# The plan\n\nTwo steps."
    artifacts.write(
        session, "supervisor", "ship/x/plan", plan, title="The plan", summary="two steps"
    )
    runs.advance(session, "supervisor", "ship/x", "ready", "planned")
    artifacts.write(session, "supervisor", "ship/x/review", REVIEW, summary="split it")
    runs.advance(
        session,
        "supervisor",
        "ship/x",
        "done",
        "the plan is reviewed",
        REVIEW,
        attached=["ship/x/review"],
    )
    return session


TWELVE_LINES = "\n".join(f"line {n} of the answer" for n in range(1, 13))

# A text field in the waiting card: its height in lines (by its line height, without its
# padding and border), whether it scrolls inside and shows its last line (the caret's, after a
# fill), and its lower edge against the card's list, the Send row and the window.
MEASURE_FIELD = """field => {
  const style = getComputedStyle(field);
  const line = parseFloat(style.lineHeight);
  const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  const box = field.getBoundingClientRect();
  const list = field.closest('.waiting-list').getBoundingClientRect();
  const panel = field.closest('[role=tabpanel]');
  const send = panel.querySelector('.waiting-send').getBoundingClientRect();
  return {
    lines: Math.round(((field.clientHeight - padding) / line) * 10) / 10,
    scrolls: field.scrollHeight > field.clientHeight + 1,
    atEnd: field.scrollTop + field.clientHeight >= field.scrollHeight - 1,
    resize: style.resize,
    inList: box.top >= list.top - 1 && box.bottom <= list.bottom + 1,
    aboveSend: box.bottom <= send.top + 1,
    inWindow: box.top >= 0 && box.bottom <= window.innerHeight,
  };
}"""


def measured(field) -> dict:
    return field.evaluate(MEASURE_FIELD)


def assert_long_field_fits(field) -> None:
    """A field with 12 lines: 8 lines high, scrolled to its last line, its lower edge within
    the card's list, above the Send row and within the window."""
    got = measured(field)
    want = {"lines": 8, "scrolls": True, "atEnd": True, "resize": "none"}
    assert {key: got[key] for key in want} == want, got
    assert got["inList"] and got["aboveSend"] and got["inWindow"], got


def test_a_gates_long_comment_grows_to_8_lines_and_stays_above_the_send_row(
    page: Page, server, repo, shot
):
    """LAD-70: the comment for the next step grows with its text from 3 lines to 8, then
    scrolls; its lower edge stays above the Send row and within the window."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = waiting_card(page, session).get_by_role("tabpanel")
    field = panel.get_by_role("textbox", name="Comment for the next step (optional)")
    expect(field).to_be_visible()
    assert measured(field)["lines"] == 3
    field.fill(TWELVE_LINES)
    expect(field).to_be_focused()
    assert_long_field_fits(field)
    shot(page, full_page=False)


def test_the_human_answers_a_gate_on_its_tab(page: Page, server, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    waits = page.get_by_role("article", name="Gate #1 waits")
    expect(waits).to_contain_text("Gate #1 ship/x · check waits: Build it as planned?")
    expect(waiting_card(page, session).get_by_role("tab", name="ship/x 1")).to_be_visible()
    card = waiting_card(page, session).get_by_role("tabpanel")
    expect(card).to_contain_text("Build it as planned?")
    expect(card.locator("strong").first).to_have_text("the plan is reviewed")
    expect(card).to_contain_text("Split it in two, then ship.")
    # The note in full with its artifact, then the artifact the gate reads, under it.
    note = card.locator(".gate-note")
    expect(note.get_by_role("button", name="Open artifact ship/x/review")).to_be_visible()
    reads = card.get_by_role("list", name="Artifacts it reads")
    expect(reads.get_by_role("listitem")).to_have_count(1)
    expect(reads).to_contain_text("The plan — two steps")
    shot(page, "card")
    reads.get_by_role("button", name="Open artifact ship/x/plan").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/plan")
    expect(panel).to_contain_text("Two steps.")
    shot(page, "read")
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)
    card.get_by_role("textbox", name="Comment for the next step (optional)").fill(
        "split the form first"
    )
    card.get_by_role("button", name="Reject").click()
    line = page.get_by_role("article", name="Gate #1", exact=True)
    expect(line).to_contain_text("Gate #1 · ship/x · check: reject by human")
    expect(line).to_contain_text("split the form first")
    expect(line.get_by_role("button", name="Approve", exact=True)).to_have_count(0)
    expect(waiting_card(page, session)).to_have_count(0)
    expect(waits).to_have_count(0)
    run = state.get_run(session, "ship/x")
    assert (run.state, run.note) == ("plan", "rejected: split the form first")
    step = [m for m in state.list_messages(session) if m.recipient == "supervisor"][-1]
    assert "Note from the previous step: rejected: split the form first" in step.body
    line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human").click()
    expect(line).to_contain_text("Build it as planned?")
    shot(page, "answered")


def test_the_humans_answer_is_the_runs_move_at_the_bottom_with_its_comment(
    page: Page, server, repo, shot
):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    feed = page.get_by_role("log", name="Chat with the session")
    card = waiting_card(page, session).get_by_role("tabpanel")
    card.get_by_role("textbox", name="Comment for the next step (optional)").fill("ship it\nnow")
    card.get_by_role("button", name="Approve", exact=True).click()
    # One line: the run's move from You, the comment under it; the run's end may follow it.
    # The gate's opening stays above, with the gate: its line says "waits for you".
    last = feed.locator(":scope > .run-group").last
    expect(last.locator("li.run-gate_open")).to_have_count(0)
    you = page.locator(".run-actor", has_text=re.compile(r"^You$"))
    move = last.get_by_role("listitem").filter(has=you)
    expect(move.locator(".run-state")).to_have_text(["check", "end"])
    expect(move.locator(".run-outcome")).to_have_text("approved")
    expect(move.locator(".run-comment")).to_contain_text("ship it")
    expect(move.locator(".run-comment br")).to_have_count(1)
    expect(feed.get_by_role("article", name="Your answer to gate #1")).to_have_count(0)
    expect(move).to_be_in_viewport()
    shot(page, "move")
    line = feed.get_by_role("article", name="Gate #1", exact=True)
    expect(line).to_contain_text("Gate #1 · ship/x · check: approve by human")
    link = feed.locator(":scope > .run-group").last.get_by_role("link", name="ship/x")
    expect(link).to_have_attribute("href", f"/sessions/{session}/flows/ship%2Fx")


def test_a_gate_answered_with_lado_answer_leaves_the_card_on_the_open_page(
    page: Page, server, repo, shot
):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    tab = waiting_card(page, session).get_by_role("tabpanel")
    expect(tab.get_by_role("button", name="Approve", exact=True)).to_be_visible()
    answer = subprocess.run(
        [sys.executable, "-m", "lado.cli", "answer", session, "1", "approve", "-m", "ship it"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert answer.returncode == 0, answer.stderr
    expect(waiting_card(page, session)).to_have_count(0)
    line = page.get_by_role("article", name="Gate #1", exact=True)
    expect(line).to_contain_text("Gate #1 · ship/x · check: approve by human")
    expect(line).to_contain_text("ship it")
    shot(page)


VIEW = (
    "I disagree with the review: the form is split, but **no test** covers the second "
    "step. Reject and ask for one."
)


def test_a_gate_with_a_recommendation_that_disagrees(page: Page, server, repo, shot):
    """The supervisor's view is part of the gate's tab in the waiting card: preparing, then
    given with the recommended option as the blue button, in light and dark; closed, one
    quiet line in the feed."""
    session = gated_session(repo)
    page.set_viewport_size({"width": 1800, "height": 1100})  # the chat at its own width
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session).get_by_role("tabpanel")
    expect(card.get_by_role("button", name="Approve", exact=True)).to_be_visible()
    # The re-ask below is a notice from outside any turn: the end of a supervisor's turn
    # still to come would mark it missing. So first the turn on the gate's own request,
    # the last message queued to it, must have ended.
    agent_helpers.wait_for(
        lambda: state.get_gate(1).recommendation_state == state.REC_MISSING,
        "gate #1's request handled",
        session,
    )
    queued = [
        m.summary
        for m in state.list_messages(session)
        if m.recipient == "supervisor" and m.state in (state.PENDING, state.SENT)
    ]
    assert queued == []
    state.ask_recommendation(session, state.GATE, 1, None, "")  # asked again
    card.locator("form.answer").scroll_into_view_if_needed()
    block = card.get_by_role("region", name="Supervisor's recommendation")
    expect(block).to_have_text("SSupervisor is preparing a recommendation…")
    expect(card.get_by_role("button", name="Approve", exact=True)).to_have_class("primary")
    expect(card.get_by_role("button", name="Reject", exact=True)).to_be_enabled()
    shot(page, "preparing")
    runtime.recommend(session, "supervisor", VIEW, gate=1, choice="reject", disagrees=True)
    expect(block.locator(".rec-differs")).to_have_text("disagrees with supervisor")
    expect(block.locator("strong")).to_have_text("no test")
    expect(card.get_by_role("button", name="Reject", exact=True)).to_have_class("primary")
    expect(card.get_by_role("button", name="Approve", exact=True)).to_have_class("quiet")
    # Between the note and the answer.
    order = card.locator(".gate-note, .gate-reads, .rec, form.answer").evaluate_all(
        "all => all.map(one => one.className)"
    )
    assert order == ["gate-note", "gate-reads", "rec differs", "answer"]
    card.locator("form.answer").scroll_into_view_if_needed()
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"given-{theme}")
    page.emulate_media(color_scheme="light")
    card.get_by_role("button", name="Reject", exact=True).click()
    line = page.get_by_role("article", name="Gate #1", exact=True)
    expect(line).to_contain_text("Gate #1 · ship/x · check: reject by human")
    line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human").click()
    quiet = line.locator("details.rec-closed")
    expect(quiet.locator("summary")).to_have_text(
        "SSupervisor recommended: Reject · disagreed with supervisor"
    )
    expect(quiet.locator(".chat-body")).not_to_be_visible()
    quiet.locator("summary").click()
    expect(quiet.locator(".chat-body")).to_contain_text("no test covers the second step")
    expect(line.locator(".rec")).to_have_count(0)
    shot(page, "closed")
