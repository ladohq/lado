"""Flow gates in a session's chat, in a browser: the human answers a gate on its tab of the
waiting card, and a gate answered elsewhere (`lado answer`) leaves the card and is a closed
line on the open page."""

import base64
import re
import subprocess
import sys
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_images import png
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


# The ring an item draws around itself (a field's focus outline or box-shadow ring, a
# marked question's ring), against what its clipping boxes (`clips`, selectors of its
# ancestors) show of it: how far the ring stays inside the visible area of each on each side
# (a negative number is the part cut), and the ring's width, read from the computed style.
MEASURE_RING = """(item, clips) => {
  const style = getComputedStyle(item);
  const outline = style.outlineStyle === 'none' ? 0
    : parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
  const shadow = style.boxShadow === 'none' ? '' : style.boxShadow.replace(/rgba?\\([^)]*\\)/g, '');
  const lengths = (shadow.match(/-?[\\d.]+px/g) || []).map(parseFloat);
  const [x = 0, y = 0, blur = 0, spread = 0] = lengths;
  const ring = Math.max(outline, spread + blur + Math.max(Math.abs(x), Math.abs(y)));
  const shown = clips.map(selector => {
    const el = item.closest(selector);
    const r = el.getBoundingClientRect();
    const left = r.left + el.clientLeft, top = r.top + el.clientTop;
    return {left, top, right: left + el.clientWidth, bottom: top + el.clientHeight};
  });
  const box = item.getBoundingClientRect();
  return {
    ring,
    left: box.left - ring - Math.max(...shown.map(s => s.left)),
    top: box.top - ring - Math.max(...shown.map(s => s.top)),
    right: Math.min(...shown.map(s => s.right)) - box.right - ring,
    bottom: Math.min(...shown.map(s => s.bottom)) - box.bottom - ring,
  };
}"""

# What clips an item of the waiting card: its scrolling list and the panel around it.
IN_WAITING_CARD = (".waiting-list", ".waiting-panel")


def assert_ring_whole(item, ring: float, clips=IN_WAITING_CARD) -> None:
    """The item draws a ring of `ring` px, and its clipping boxes show it whole on all four
    sides."""
    got = item.evaluate(MEASURE_RING, list(clips))
    assert got["ring"] == ring, got
    cut = {side: got[side] for side in ("left", "top", "right", "bottom") if got[side] < -0.5}
    assert not cut, got


def comment_field(page: Page, session: str):
    panel = waiting_card(page, session).get_by_role("tabpanel")
    return panel.get_by_role("textbox", name="Comment for the next step (optional)")


def frame_of(field):
    """The frame of a field that takes files (LAD-86): it draws the field's focus ring."""
    return field.locator(
        "xpath=ancestor::div[contains(concat(' ', @class, ' '), ' answer-box ')][1]"
    )


def test_a_gates_comment_with_the_focus_shows_its_ring_whole(page: Page, server, repo, shot):
    """LAD-78: the comment's focus ring (its frame's, 3 px out, LAD-86) is whole on the left,
    the top, the right and the bottom, within the card's list."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    field = comment_field(page, session)
    field.click()
    expect(field).to_be_focused()
    assert_ring_whole(frame_of(field), 3)
    shot(page, full_page=False)


def test_a_gates_long_comment_shows_its_ring_whole(page: Page, server, repo, shot):
    """LAD-78: a comment of 12 lines, 8 lines high and scrolled into view, keeps its ring
    whole on all four sides."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    field = comment_field(page, session)
    field.fill(TWELVE_LINES)
    expect(field).to_be_focused()
    assert_long_field_fits(field)
    assert_ring_whole(frame_of(field), 3)
    shot(page, full_page=False)


def test_a_gates_comment_in_a_narrow_window_shows_its_ring_whole(page: Page, server, repo, shot):
    """LAD-78: in a window 600 px wide the comment's focus ring is whole too."""
    page.set_viewport_size({"width": 600, "height": 900})
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    field = comment_field(page, session)
    field.click()
    expect(field).to_be_focused()
    assert_ring_whole(frame_of(field), 3)
    shot(page, full_page=False)


def test_a_gates_long_comment_on_the_flows_tab_shows_its_ring_whole(page: Page, server, repo, shot):
    """LAD-78: on the Flows tab's gate card, a comment of 12 lines grows to the page's lower
    edge and is scrolled into view with its focus ring whole: the run's page (`.list-main`)
    scrolls there, not the waiting card's list."""
    page.set_viewport_size({"width": 1280, "height": 640})
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    card = page.get_by_role("region", name="Now").get_by_role("article", name="Gate #1", exact=True)
    field = card.get_by_role("textbox", name="Comment for the next step (optional)")
    field.fill(TWELVE_LINES)
    expect(field).to_be_focused()
    # Grown past the window's lower edge, so the page scrolled to bring it into view.
    assert page.locator(".list-main").evaluate("main => main.scrollTop") > 0
    assert_ring_whole(frame_of(field), 3, clips=(".list-main",))
    shot(page, full_page=False)


# Where a gate's tab puts its question, its comment field and its Send row: their left
# edges from the panel's, and the Send row's top from the panel's.
MEASURE_PLACES = """panel => {
  const frame = panel.getBoundingClientRect();
  const at = el => el.getBoundingClientRect();
  return {
    question: at(panel.querySelector('.waiting-gate').firstElementChild).left - frame.left,
    field: at(panel.querySelector('.answer textarea')).left - frame.left,
    send: at(panel.querySelector('.waiting-send')).top - frame.top,
  };
}"""

# The list's room as it was before LAD-78, for the comparison.
BEFORE_RING_ROOM = ".waiting-list { padding: 0 6px 4px 0 !important; margin: 0 !important; }"


def test_the_room_for_the_ring_moves_nothing_on_a_gates_tab(page: Page, server, repo, shot):
    """LAD-78: the question and the comment field start as far from the panel's left edge
    as before the list kept room for the ring, and the Send row stands where it stood."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = waiting_card(page, session).locator(".waiting-panel")
    expect(comment_field(page, session)).to_be_visible()
    now = panel.evaluate(MEASURE_PLACES)
    shot(page, full_page=False)
    page.add_style_tag(content=BEFORE_RING_ROOM)
    before = panel.evaluate(MEASURE_PLACES)
    assert now == before


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
    # The feed shows the closed gate before the answer's request has queued the next step:
    # lado.db is read only once the server answered.
    answer = f"{server['url']}/api/sessions/{session}/gates/1/answer"
    with page.expect_response(answer) as answered:
        card.get_by_role("button", name="Reject").click()
    assert answered.value.ok
    line = page.get_by_role("article", name="Gate #1", exact=True)
    head = line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human")
    expect(head).to_be_visible()
    expect(line.get_by_role("button", name="Approve", exact=True)).to_have_count(0)
    expect(waiting_card(page, session)).to_have_count(0)
    expect(waits).to_have_count(0)
    run = state.get_run(session, "ship/x")
    assert (run.state, run.note) == ("plan", "rejected: split the form first")
    step = [m for m in state.list_messages(session) if m.recipient == "supervisor"][-1]
    assert "Note from the previous step: rejected: split the form first" in step.body
    # The comment once: under the human's move, on the human's ground; the folded card has
    # its chip by the move's direction, "by you" and a chevron.
    feed = page.get_by_role("log", name="Chat with the session")
    move = feed.locator("li.run-event.mine")
    expect(move.locator(".run-comment")).to_have_text("split the form first")
    expect(feed.get_by_text("split the form first")).to_have_count(1)
    expect(move).to_have_css("background-color", line_ground(page))
    expect(head.locator(".run-outcome.back")).to_have_text("reject")
    expect(head.locator(".gate-head-by")).to_have_text("by you")
    chevron = head.locator(".gate-chevron")
    expect(chevron.locator("svg")).to_be_visible()
    expect(head).to_have_attribute("aria-expanded", "false")
    # The chevron first, before the flag; the time last (LAD-136).
    flag, turn = head.locator(".avatar-gate").bounding_box(), chevron.bounding_box()
    assert flag is not None and turn is not None and turn["x"] + turn["width"] <= flag["x"]
    expect(chevron).to_have_css("transform", "none")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        line.scroll_into_view_if_needed()
        shot(page, f"folded-{theme}", full_page=False)
    # Opened from the keyboard: down in the same frame, the question and the answer.
    head.focus()
    page.keyboard.press("Enter")
    expect(head).to_have_attribute("aria-expanded", "true")
    expect(chevron).to_have_css("transform", "matrix(-1, 0, 0, -1, 0, 0)")  # turned up
    opened = line.locator(".gate-closed-card")
    expect(opened.locator(".gate-question")).to_have_text("Build it as planned?")
    plaque = opened.locator(".question-answer")
    expect(plaque.locator(".answer-who")).to_have_text("You")
    expect(plaque.locator(".answer-target")).to_have_text("→ plan")
    expect(plaque.locator(".chat-body")).to_have_text("split the form first")
    note = opened.locator("details.gate-row").first
    expect(note.locator("summary")).to_have_text("Notethe plan is reviewed · 1 artifact")
    expect(note.locator(".gate-note")).not_to_be_visible()
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"opened-{theme}", full_page=False)
    note.locator("summary").click()
    expect(note.get_by_role("button", name="Open artifact ship/x/review")).to_be_visible()
    expect(note).to_contain_text("Split it in two, then ship.")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"note-{theme}", full_page=False)
    page.emulate_media(color_scheme="light")
    head.focus()
    page.keyboard.press("Space")
    expect(head).to_have_attribute("aria-expanded", "false")
    expect(opened).to_have_count(0)


def line_ground(page: Page) -> str:
    """The human's ground (--action-ground) as the browser computes a background colour."""
    return page.evaluate(
        """() => {
          const probe = document.createElement('div');
          probe.style.background = 'var(--action-ground)';
          document.body.append(probe);
          const colour = getComputedStyle(probe).backgroundColor;
          probe.remove();
          return colour;
        }"""
    )


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
    expect(
        line.get_by_role("button", name="Gate #1 · ship/x · check: approve by human")
    ).to_be_visible()
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
    expect(
        line.get_by_role("button", name="Gate #1 · ship/x · check: approve by human")
    ).to_be_visible()
    # The comment under the move it made, not on the gate's card.
    expect(line).not_to_contain_text("ship it")
    expect(page.locator("li.run-event.mine .run-comment")).to_have_text("ship it")
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
    line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human").click()
    quiet = line.locator("details.gate-row", has_text="Supervisor")
    expect(quiet.locator("summary")).to_have_text(
        "Supervisorrecommended Reject · you agreed · disagreed with supervisor"
    )
    expect(quiet.locator(".chat-body")).not_to_be_visible()
    quiet.locator("summary").click()
    expect(quiet.locator(".chat-body")).to_contain_text("no test covers the second step")
    expect(line.locator(".rec")).to_have_count(0)
    shot(page, "closed")


# A file put on the clipboard and pasted into the focused element, as a browser does with a
# screenshot (named image.png); its bytes base64.
PASTE_IMAGE = """(field, data) => {
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  const clip = new DataTransfer();
  clip.items.add(new File([bytes], 'image.png', { type: 'image/png' }));
  const paste = { clipboardData: clip, bubbles: true, cancelable: true };
  field.dispatchEvent(new ClipboardEvent('paste', paste));
}"""

# A file dragged and dropped from the desktop, as the browser's drag events carry it.
DROPPED_NOTES = (
    "() => { const d = new DataTransfer();"
    " d.items.add(new File(['split it\\n'], 'notes.txt', { type: 'text/plain' })); return d; }"
)


def test_the_human_answers_a_gate_with_files_the_next_step_gets(page: Page, server, repo, shot):
    """A gate's comment takes files as the composer does: a paste, the paperclip and a drop on
    the field; Reject uploads them and answers; the move shows the comment, the preview and
    the chips, the opened gate's card the chips only."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session).get_by_role("tabpanel")
    field = card.get_by_role("textbox", name="Comment for the next step (optional)")
    clip = card.get_by_role("button", name="Attach files")
    expect(clip).to_have_attribute("title", re.compile("up to 10 files"))  # the limits loaded
    field.evaluate(PASTE_IMAGE, base64.b64encode(png(320, 180)).decode())
    card.locator("input[type=file]").set_input_files(
        [{"name": "server.log", "mimeType": "text/plain", "buffer": b"GET / 500\n" * 30}]
    )
    box = card.locator(".answer-box")
    box.scroll_into_view_if_needed()
    box.dispatch_event("dragenter", {"dataTransfer": page.evaluate_handle(DROPPED_NOTES)})
    expect(box.get_by_text("Drop to attach · up to 10 files, 25.0 MB each")).to_be_visible()
    shot(page, "drop", full_page=False)
    box.dispatch_event("drop", {"dataTransfer": page.evaluate_handle(DROPPED_NOTES)})
    chips = card.get_by_role("list", name="Attached files").locator(".file-name")
    expect(chips).to_have_text([re.compile(r"^screenshot-\d{6}\.png$"), "server.log", "notes.txt"])
    expect(page.locator(".composer .file-chip")).to_have_count(0)  # the drop went to the field
    expect(card.locator(".waiting-send")).to_contain_text("3 files,")
    field.fill("the button covers the field")
    shot(page, "tab", full_page=False)
    card.get_by_role("button", name="Reject", exact=True).click()
    expect(waiting_card(page, session)).to_have_count(0)
    feed = page.get_by_role("log", name="Chat with the session")
    you = page.locator(".run-actor", has_text=re.compile(r"^You$"))
    move = feed.locator(".run-group li").filter(has=you).last
    comment = move.locator(".run-comment")
    expect(comment).to_contain_text("the button covers the field")
    expect(comment.locator(".chat-image img")).to_have_js_property("naturalWidth", 320)
    expect(comment.locator(".chip")).to_have_count(3)
    move.scroll_into_view_if_needed()
    shot(page, "move", full_page=False)
    line = feed.get_by_role("article", name="Gate #1", exact=True)
    line.get_by_role("button", name="Gate #1 · ship/x · check: reject by human").click()
    answer = line.locator(".gate-closed-card .question-answer")
    expect(answer.locator(".chip")).to_have_count(3)
    expect(answer.locator(".chat-image")).to_have_count(0)
    chip = answer.locator(".chip").first.bounding_box()
    frame = answer.bounding_box()
    assert chip and frame and chip["x"] + chip["width"] <= frame["x"] + frame["width"]  # inside
    answer.scroll_into_view_if_needed()
    shot(page, "card", full_page=False)
    gate = state.get_gate(1)
    names = [a.artifact.name for a in runs.gate_answer_attachments(gate)]
    assert len(names) == 3 and names[1].startswith("server-") and names[2].startswith("notes-")
    step = state.last_note(session, "ship/x")
    assert step.summary == "rejected: the button covers the field"
