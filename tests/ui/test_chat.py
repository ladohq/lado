"""The chat in a session's Activity tab, in a browser: the human writes to the supervisor
(the fake agent), and answers its question."""

import functools
import json
import re

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_artifacts_tab import MANY, MEASURE_TABLES
from test_gates import gated_session
from test_images import png
from test_main_screen import log_in, running_session

from lado import artifacts, runtime, state

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def inputs(session: str) -> list:
    log = agent_helpers.fake_logs(session, "supervisor") / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_the_human_writes_and_the_supervisor_gets_it_and_replies(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    expect(chat).to_contain_text("No messages yet")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    field.fill("send human merged w1 | **All** checks pass.\\nBranch lado/x.")
    field.press("Enter")
    expect(field).to_have_value("")
    mine = chat.get_by_role("article", name="Message from you")
    expect(mine).to_contain_text("send human merged w1")
    reply = chat.get_by_role("article", name="Message from supervisor")
    expect(reply).to_contain_text("merged w1")
    assert any(i.startswith("[from human] send human merged w1") for i in inputs(session))
    expect(reply.locator("strong")).to_have_text("All")  # a body to the human shows at once
    shot(page)


def waiting_card(page: Page, session: str):
    return page.get_by_role("region", name=f"What waits for you in {session}")


def test_the_supervisor_asks_twice_and_the_human_answers_both_in_one_tab(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    card = waiting_card(page, session)
    for asked, ask in enumerate(["askhuman Ship it? | yes, later", "askhuman Which port?"], 1):
        field.fill(ask)
        field.press("Enter")
        expect(card.get_by_role("tab", name=f"supervisor {asked}")).to_be_visible()
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    chat = page.get_by_role("log", name="Chat with the session")
    lines = chat.get_by_role("article", name="Question from supervisor")
    expect(lines).to_have_count(2)
    expect(lines.first).to_contain_text("supervisor asked: Ship it?")
    ship, port = card.get_by_role("listitem").all()
    send = card.get_by_role("button", name="Send 2 answers to supervisor")
    expect(send).to_be_disabled()
    ship.get_by_role("button", name="yes", exact=True).click()
    expect(card).to_contain_text("1 of 2 answered")
    port.get_by_role("button", name="Other…").click()
    port.get_by_role("textbox", name="Your own answer").fill("8123")
    expect(send).to_be_enabled()
    shot(page, "open")
    send.click()
    expect(card).to_have_count(0)
    # Both reached the supervisor in one hand-over: one input.
    asked = [m.id for m in state.list_messages(session) if m.kind == state.QUESTION]
    both = f"[from human] Answer to #{asked[0]}: yes\n[from human] Answer to #{asked[1]}: 8123"
    agent_helpers.wait_for(lambda: both in inputs(session), "both answers in one input", session)
    # Each answer is in its question's card: the choice marked in the list only, who
    # answered under it; no row of its own.
    cards = chat.get_by_role("article", name="Question from supervisor")
    expect(cards.nth(0).locator(".chosen")).to_have_text("✓ yes")
    expect(cards.nth(0).locator(".question-answer .answer-head")).to_have_text("You · answered")
    expect(cards.nth(0).locator(".question-answer")).not_to_contain_text("yes")
    expect(cards.nth(1).locator(".question-answer")).to_contain_text("8123")
    expect(page.get_by_role("article", name="Message from you")).to_have_count(2)  # the asks
    shot(page, "answered")


def test_a_workers_question_with_the_supervisors_recommendation_open_and_closed(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    runtime.send_message(session, "human", "w1", "askhuman Ship it? | yes, later")
    question = agent_helpers.wait_for(
        lambda: next((m for m in state.list_messages(session) if m.kind == state.QUESTION), None),
        "the question",
        session,
    )
    # LADO asks the supervisor for its recommendation in a transaction after the
    # question's; recommending earlier, the request would set it back to asked and the
    # supervisor's turn on it mark it missing. So first that turn must have ended.
    agent_helpers.wait_for(
        lambda: (
            state.get_message(session, question.id).recommendation_state == state.REC_MISSING
        ),
        "the question's request handled",
        session,
    )
    queued = [
        m.summary
        for m in state.list_messages(session)
        if m.recipient == "supervisor" and m.state in (state.PENDING, state.SENT)
    ]
    assert queued == []
    runtime.recommend(
        session,
        "supervisor",
        "Later: CI is red on the branch.",
        question=question.id,
        choice="later",
        disagrees=True,
    )
    page.set_viewport_size({"width": 1800, "height": 1000})  # the chat at its own width
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session)
    item = card.get_by_role("listitem", name=f"Question #{question.id}")
    block = item.get_by_role("region", name="Supervisor's recommendation")
    expect(block).to_contain_text("Later: CI is red on the branch.")
    expect(block.locator(".rec-differs")).to_have_text("disagrees with w1")
    # The recommended choice is picked ahead: Send sends it as it is.
    expect(item.get_by_role("button", name="later")).to_have_attribute("aria-pressed", "true")
    expect(item.get_by_role("button", name="yes")).to_have_attribute("aria-pressed", "false")
    shot(page, "open")
    card.get_by_role("button", name="Send answer to w1").click()
    expect(card).to_have_count(0)
    closed = page.get_by_role("log", name="Chat with the session").get_by_role(
        "article", name="Question from w1"
    )
    expect(closed.locator(".chosen")).to_have_text("✓ later")
    quiet = closed.locator("details.rec-closed")
    expect(quiet.locator("summary")).to_have_text(
        "SSupervisor recommended: later · disagreed with w1"
    )
    expect(closed.locator(".question-answer")).not_to_contain_text("later")
    expect(closed.locator(".rec")).to_have_count(0)
    quiet.locator("summary").click()
    expect(quiet.locator(".chat-body")).to_contain_text("CI is red")
    shot(page, "closed")


def test_three_tabs_switch_a_gate_is_approved_on_its_tab_and_the_card_expands(
    page: Page, server, repo, shot
):
    """The supervisor's question, the gate of run ship/x and w1's question: three tabs in the
    order they were asked; the gate's Approve moves the run; the card over the chat's area
    and Esc (docs/design/ui.md, The waiting card)."""
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Which branch?", "No epic: main.", ["main", "epic"])
    runtime.spawn_worker(session, "sleep 0", name="w1")
    runtime.ask_human(session, "w1", "Run the paid test?", None, ["yes", "no"], False)
    page.set_viewport_size({"width": 1400, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session)
    tabs = card.get_by_role("tab")
    expect(tabs).to_have_count(3)
    expect(tabs.nth(0)).to_have_accessible_name("ship/x 1")
    expect(tabs.nth(1)).to_have_accessible_name("supervisor 1")
    expect(tabs.nth(2)).to_have_accessible_name("w1 1")
    expect(tabs.nth(0)).to_have_attribute("aria-selected", "true")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"{theme}-three-tabs")
    page.emulate_media(color_scheme="light")
    tabs.nth(2).click()
    expect(card.get_by_role("tabpanel")).to_contain_text("Run the paid test?")
    expect(card.get_by_role("button", name="Other…")).to_have_count(0)  # choices only
    # The gate's line leads back to its tab.
    page.get_by_role("article", name="Gate #1 waits").get_by_role(
        "button", name="Answer gate #1"
    ).click()
    expect(tabs.nth(0)).to_have_attribute("aria-selected", "true")
    expand = card.get_by_role("button", name="Expand the card")
    expand.click()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    # Over the chat's area only: the feed and the composer hidden, no scrim, no dialog; the
    # session's tabs seen and usable.
    chat = page.get_by_role("region", name="Chat", exact=True).bounding_box()
    box = card.bounding_box()
    assert box["x"] >= chat["x"] - 1 and box["y"] >= chat["y"] - 1, (box, chat)
    assert box["x"] + box["width"] <= chat["x"] + chat["width"] + 1, (box, chat)
    assert box["y"] + box["height"] <= chat["y"] + chat["height"] + 1, (box, chat)
    assert box["width"] >= chat["width"] - 1 and box["height"] >= chat["height"] - 1, (box, chat)
    assert box["x"] > 32, box  # not the window's
    expect(page.get_by_role("log", name="Chat with the session")).to_be_hidden()
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_hidden()
    expect(page.locator(".waiting-overlay, .panel-scrim")).to_have_count(0)
    expect(page.get_by_role("dialog")).to_have_count(0)
    sections = page.get_by_role("navigation", name="Session sections")
    expect(sections.get_by_role("link", name="Agents")).to_be_visible()
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"{theme}-expanded")
    page.emulate_media(color_scheme="light")
    page.keyboard.press("Escape")
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    expect(card.get_by_role("button", name="Expand the card")).to_be_focused()
    card.get_by_role("tabpanel").get_by_role("button", name="Approve", exact=True).click()
    expect(tabs).to_have_count(2)
    agent_helpers.wait_for(
        lambda: state.get_run(session, "ship/x").state != "check", "the run moved on", session
    )
    shot(page, "approved")


def on_top(page: Page, panel) -> bool:
    """Whether what the window shows at the middle of the panel is the panel's."""
    box = panel.bounding_box()
    return page.evaluate(
        "([x, y]) => !!document.elementFromPoint(x, y)?.closest('.artifact-panel')",
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
    )


def asked_with_a_plan(session: str) -> None:
    artifacts.write(session, "supervisor", "plan", "# The plan\n\nJ1 to J9.", title="The plan")
    runtime.ask_human(
        session,
        "supervisor",
        "Shall I do it myself?",
        "See the plan.",
        ["myself", "wait"],
        attached=["plan"],
    )


def test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost(
    page: Page, server, repo, shot
):
    """LAD-48: a chip in the expanded card opens the panel over it; the first Esc closes the
    panel, the second folds the card (docs/design/ui.md, The waiting card)."""
    session = running_session(repo)
    asked_with_a_plan(session)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    card.get_by_role("button", name="myself").click()
    chip = card.get_by_role("button", name="Open artifact plan")
    chip.click()
    panel = page.get_by_role("dialog", name="Artifact plan")
    expect(panel).to_contain_text("J1 to J9.")
    assert on_top(page, panel)
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"{theme}-panel")
    page.emulate_media(color_scheme="light")
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)
    expect(chip).to_be_focused()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(card.get_by_role("button", name="myself")).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Escape")
    expect(card).not_to_have_class(re.compile(r"\bexpanded\b"))
    expect(card.get_by_role("button", name="Expand the card")).to_be_focused()
    expect(card.get_by_role("button", name="myself")).to_have_attribute("aria-pressed", "true")


def test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways(
    page: Page, server, repo, shot
):
    """In a narrow chat the tabs keep one line: names cut, then the row scrolls sideways;
    the shown tab lies on the panel, scrolls into view when chosen, and the expand button
    stays at the right (docs/design/ui.md, The waiting card)."""
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Which branch?", None, ["main", "epic"])
    for name in ("developer-with-a-long-name", "reviewer-of-the-design", "analyst"):
        runtime.spawn_worker(session, "sleep 0", name=name)
        runtime.ask_human(session, name, f"A question of {name}?", None, ["yes", "no"], False)
    page.set_viewport_size({"width": 1000, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session)
    tabs = card.get_by_role("tab")
    expect(tabs).to_have_count(5)
    row = card.get_by_role("tablist")
    expand = card.get_by_role("button", name="Expand the card")
    panel = card.get_by_role("tabpanel")

    def check(shown):
        tops = [tab.bounding_box()["y"] for tab in tabs.all()]
        assert max(tops) - min(tops) <= 1.5, tops  # one line (the shown tab 1 px lower)
        on, under = shown.bounding_box(), panel.bounding_box()
        assert abs(on["y"] + on["height"] - under["y"]) <= 1.5, (on, under)  # on the panel
        seen = row.bounding_box()
        assert seen["x"] - 1 <= on["x"] and on["x"] + on["width"] <= seen["x"] + seen["width"] + 1
        assert seen["x"] + seen["width"] <= expand.bounding_box()["x"]

    check(tabs.nth(0))
    assert row.evaluate("e => e.scrollWidth > e.clientWidth")  # it scrolls sideways
    right = expand.bounding_box()["x"]
    shot(page, "first")
    tabs.nth(4).click()
    expect(tabs.nth(4)).to_have_attribute("aria-selected", "true")
    check(tabs.nth(4))
    assert expand.bounding_box()["x"] == right
    page.emulate_media(color_scheme="dark")
    shot(page, "last-dark")


def test_the_chat_looks_as_a_feed_in_light_and_dark(page: Page, server, repo, shot):
    """A group of the supervisor's messages, a closed question and the human's answer, an
    open gate's line, the waiting card and the composer, in both themes and in a narrow
    column."""
    session = gated_session(repo)
    say = functools.partial(state.queue_message, session, mark=state.DELIVERED)
    say("human", "supervisor", "Make the chat more presentable, please")
    say("supervisor", "human", "Looking at the page myself", "I took **screenshots** of the UI.")
    say("supervisor", "human", "Started the run; working out what to improve")
    runtime.ask_human(session, "supervisor", "Which look?", "- A: messenger\n- B: feed", ["A", "B"])
    [question] = [m for m in state.list_messages(session) if m.kind == state.QUESTION]
    runtime.answer_question(session, question.id, text="Show me all three\nside by side")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    rows = chat.get_by_role("article", name="Message from supervisor")
    expect(rows).to_have_count(2)
    expect(rows.nth(0).locator(".feed-who")).to_have_text("supervisor")
    expect(rows.nth(1)).to_have_class(re.compile(r"\bcontinued\b"))
    expect(rows.nth(1).locator(".feed-head")).to_have_count(0)
    asked = chat.get_by_role("article", name="Question from supervisor")
    given = asked.locator(".question-answer")
    expect(given).to_contain_text("Show me all three")
    expect(given.locator("br")).to_have_count(1)  # the human's line break, as typed
    gate = chat.get_by_role("article", name="Gate #1 waits")
    expect(gate.locator(".avatar-gate")).to_be_visible()
    expect(waiting_card(page, session).get_by_role("tab", name="ship/x 1")).to_be_visible()
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(page.locator(".composer-box").get_by_role("button", name="Send")).to_be_disabled()
    one_line = field.bounding_box()["height"]
    field.fill("one\ntwo\nthree")
    assert field.bounding_box()["height"] > one_line  # the field grows with its text
    field.fill("")
    assert chat.evaluate("feed => feed.scrollWidth <= feed.clientWidth")  # no sideways scroll
    page.emulate_media(color_scheme="light")
    shot(page, "light")
    page.emulate_media(color_scheme="dark")
    shot(page, "dark")
    gate.scroll_into_view_if_needed()
    shot(page, "dark-gate")
    page.emulate_media(color_scheme="light")
    shot(page, "light-gate")
    page.emulate_media(color_scheme="light")
    page.set_viewport_size({"width": 480, "height": 900})
    expect(rows.nth(1).locator(".feed-side time")).to_have_css("opacity", "1")
    assert chat.evaluate("feed => feed.scrollWidth <= feed.clientWidth")
    shot(page, "narrow")


def test_the_cards_buttons_are_one_height_in_light_and_dark(page: Page, server, repo, shot):
    """A question's choices, Other…, Skip and Send, and a gate's Approve and Reject on its
    tab: one height (docs/design/ui.md, The waiting card)."""
    session = gated_session(repo)
    runtime.ask_human(session, "supervisor", "Ship today?", None, ["yes, today", "after the tag"])
    page.set_viewport_size({"width": 1800, "height": 1000})  # the chat at its own width
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = waiting_card(page, session)

    def heights() -> list:
        buttons = card.locator(".waiting-option, .waiting-send button").all()
        assert buttons
        return [round(button.bounding_box()["height"]) for button in buttons]

    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        card.get_by_role("tab", name="ship/x 1").click()
        expect(card.get_by_role("button", name="Approve", exact=True)).to_be_visible()
        assert set(heights()) == {32}, heights()
        shot(page, f"{theme}-gate")
        card.get_by_role("tab", name="supervisor 1").click()
        card.get_by_role("button", name="Other…").click()
        card.get_by_role("textbox", name="Your own answer").fill("on the dark theme it blends in")
        expect(card.get_by_role("button", name="Send answer to supervisor")).to_be_enabled()
        assert set(heights()) == {32}, heights()
        shot(page, f"{theme}-question")
        card.get_by_role("button", name="Other…").click()  # unpicked again
    page.emulate_media(color_scheme="light")


REPORT = """\
## Report

| AC | status | test |
| :--- | :---: | --- |
| 1. a table renders | done | `web/src/Body.test.tsx` and `tests/ui/test_artifacts_tab.py` |
| 2. the chat renders it too | done | `tests/ui/test_chat.py::test_a_message_with_a_wide_table` |

- [x] tables
- [ ] ~~single tilde~~, see https://github.com/remarkjs/remark-gfm

> No concerns.
"""


@pytest.mark.parametrize("width", [900, 390])
def test_a_message_s_table_wraps_one_too_wide_scrolls_in_its_frame_and_the_chat_does_not(
    page: Page, server, repo, shot, width
):
    session = running_session(repo)
    state.queue_message(session, "supervisor", "human", "DONE", REPORT, mark=state.DELIVERED)
    noted = "Merged.[^1]\n\n[^1]: after the review"
    state.queue_message(session, "supervisor", "human", "merged", noted, mark=state.DELIVERED)
    state.queue_message(session, "supervisor", "human", "matrix", MANY, mark=state.DELIVERED)
    page.set_viewport_size({"width": width, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    frames = chat.locator(".md-table")
    expect(frames.first.get_by_role("columnheader")).to_have_text(["AC", "status", "test"])
    expect(frames).to_have_count(2)
    expect(chat.locator("input[type=checkbox]")).to_have_count(2)
    expect(chat.locator("del")).to_have_text("single tilde")
    report, many = chat.evaluate(MEASURE_TABLES, "[role=log]")
    assert report["scroll"] <= report["client"], report  # it fits, its cells wrapping
    assert report["sticking"] == 0, report
    assert many["scroll"] > many["client"], many  # too many columns: it scrolls in its frame
    assert report["sideways"] == many["sideways"] == [], (report, many)
    assert chat.evaluate("feed => feed.scrollWidth <= feed.clientWidth")
    # A body ends at its text: its last block has no margin under it.
    expect(chat.locator(".chat-body blockquote")).to_have_css("margin-bottom", "0px")
    # A footnote's "Footnotes" heading is for the ear only.
    label = chat.get_by_role("heading", name="Footnotes")
    expect(label).to_have_count(1)
    assert label.bounding_box()["height"] <= 1
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        frames.first.scroll_into_view_if_needed()
        shot(page, f"{theme}-report")
        frames.last.scroll_into_view_if_needed()
        shot(page, f"{theme}-many")
    page.emulate_media(color_scheme="light")


def test_each_message_says_its_text_once_runs_are_groups_and_replies_are_in_the_card(
    page: Page, server, repo, shot
):
    """The human's long text with its line breaks, an agent's long report cut and opened, an
    agents' message to each other, a run's events as a group, a question answered in its
    card and one answered late, in both themes (docs/design/ui.md, Message text)."""
    session = gated_session(repo)
    say = functools.partial(state.queue_message, session, mark=state.DELIVERED)
    first = "I think we should fix how the chat shows the human's messages."
    text = f"{first}\nNow a long one shows twice.\n\n- once as a heading\n- once folded"
    say("human", "supervisor", first, text)  # as runtime._human_text splits it
    report = "\n\n".join(f"line {n} of the report" for n in range(1, 41))
    say("supervisor", "human", "Decisions of the day", report)
    say("supervisor", "w1", "please review the branch", "the **diff** is small")
    runtime.ask_human(session, "supervisor", "Font of the chat?", None, ["Plex", "Inter"])
    say("supervisor", "human", "While you think: making the mockups")
    runtime.ask_human(session, "supervisor", "Ship today?", None, ["yes", "no"])
    first_q, second_q = [m for m in state.list_messages(session) if m.kind == state.QUESTION]
    runtime.answer_question(session, second_q.id, choice="yes")  # right under it: in the card
    runtime.answer_question(session, first_q.id, choice="Inter", text="closest to Slack")  # late
    page.set_viewport_size({"width": 1800, "height": 1000})  # the chat at its own width
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    mine = chat.get_by_role("article", name="Message from you")
    expect(mine.locator("br")).to_have_count(1)
    assert mine.inner_text().count(first) == 1
    expect(mine.get_by_role("heading")).to_have_count(0)
    long = chat.get_by_role("article", name="Message from supervisor").first
    expect(long).to_contain_text("line 12 of")
    expect(long).not_to_contain_text("line 13 of")
    group = chat.get_by_role("list", name="Flow run ship/x")
    expect(group.get_by_role("listitem").last).to_contain_text("waits for you")
    late = chat.get_by_role("article", name=f"You answered question #{first_q.id}")
    expect(late).to_contain_text("Inter · closest to Slack")
    cards = chat.get_by_role("article", name="Question from supervisor")
    # The choice once, in the list; the reply block has only the comment.
    expect(cards.nth(0).locator(".chosen")).to_have_text("✓ Inter")
    expect(cards.nth(0).locator(".question-answer")).not_to_contain_text("Inter")
    expect(cards.nth(0).locator(".question-answer .chat-body")).to_have_text("closest to Slack")
    expect(cards.nth(1).locator(".chosen")).to_have_text("✓ yes")
    expect(cards.nth(1).locator(".question-answer")).not_to_contain_text("yes")
    page.get_by_role("checkbox", name="Show agent messages").check()
    between = chat.get_by_role("article", name="Message from supervisor to w1")
    expect(between.locator("summary")).to_contain_text("please review the branch")
    assert chat.evaluate("feed => feed.scrollWidth <= feed.clientWidth")  # no sideways scroll
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        chat.evaluate("feed => { feed.scrollTop = 0 }")
        shot(page, f"{theme}-top")
        chat.evaluate("feed => { feed.scrollTop = feed.scrollHeight }")
        shot(page, f"{theme}-bottom")
    page.emulate_media(color_scheme="light")
    mine.evaluate("row => row.scrollIntoView({ block: 'start' })")
    shot(page, "texts")
    between.locator("summary").click()
    expect(between.locator("strong")).to_have_text("diff")
    long.get_by_role("button", name="Show more").click()
    expect(long).to_contain_text("line 40 of")
    expect(long.get_by_role("button", name="Show less")).to_have_attribute("aria-expanded", "true")
    long.scroll_into_view_if_needed()
    shot(page, "opened")


def long_session(repo) -> tuple[str, int]:
    """A running session whose chat has an open question and then 120 messages to the
    human; the question's id."""
    session = running_session(repo)
    runtime.ask_human(session, "supervisor", "Old question?", None, ["yes", "no"])
    for n in range(1, 121):
        state.queue_message(session, "supervisor", "human", f"note {n}", mark=state.DELIVERED)
    [question] = [m for m in state.list_messages(session) if m.kind == state.QUESTION]
    return session, question.id


def visible_in(chat, article) -> bool:
    """Whether the article is inside the chat's scrolled view."""
    box, view = article.bounding_box(), chat.bounding_box()
    return box is not None and view["y"] <= box["y"] < view["y"] + view["height"]


def test_a_long_chat_opens_with_its_latest_page_and_loads_earlier_ones_at_the_top(
    page: Page, server, repo, shot
):
    session, _ = long_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    expect(chat.get_by_text("note 120", exact=True)).to_be_visible()
    articles = chat.get_by_role("article")
    assert articles.count() <= 50
    expect(chat.get_by_text("note 70", exact=True)).to_have_count(0)
    shot(page, "opened")
    first = chat.get_by_role("article").first
    expect(first).to_contain_text("note 71")
    chat.evaluate("feed => { feed.scrollTop = 0; }")
    expect(chat.get_by_text("note 21", exact=True)).to_have_count(1)
    assert visible_in(chat, chat.get_by_role("article").filter(has_text="note 71"))  # no jump
    shot(page, "earlier")
    for _ in range(5):  # down to the start
        if chat.get_by_text("Start of session").count():
            break
        chat.evaluate("feed => { feed.scrollTop = 0; }")
        page.wait_for_timeout(300)
    expect(chat.get_by_text(f"Start of session {session}")).to_be_visible()
    expect(chat.get_by_role("article", name="Question from supervisor")).to_have_count(1)
    chat.evaluate("feed => { feed.scrollTop = 0; }")
    expect(chat.get_by_text(f"Start of session {session}")).to_be_in_viewport()
    shot(page, "start")


AT_BOTTOM = "feed => feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40"


def note(session: str, text: str) -> None:
    state.queue_message(session, "supervisor", "human", text, mark=state.DELIVERED)


def chat_read_at(page: Page, server, repo, where: str):
    """A long chat with an open question, the human's scroll put at `where` (a JS
    expression of `feed`); its feed (by its class: a role leaves a hidden one out), the
    card, the session and the feed's scrollTop."""
    session, _ = long_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.locator(".chat-feed")
    card = waiting_card(page, session)
    expect(chat.get_by_text("note 120", exact=True)).to_be_visible()
    expect(card).to_be_visible()
    top = chat.evaluate(f"feed => {{ feed.scrollTop = {where}; return feed.scrollTop; }}")
    page.wait_for_timeout(300)  # the scroll event ran
    return chat, card, session, top


def test_at_the_bottom_messages_that_come_while_the_card_is_expanded_show_after_its_fold(
    page: Page, server, repo, shot
):
    """LAD-48, F5: the scroll rule holds while the expanded card hides the feed."""
    chat, card, session, _ = chat_read_at(page, server, repo, "feed.scrollHeight")
    assert chat.evaluate(AT_BOTTOM)
    card.get_by_role("button", name="Expand the card").click()
    expect(chat).to_be_hidden()
    for n in range(1, 6):
        note(session, f"late {n}")
    expect(chat.get_by_text("late 5", exact=True)).to_have_count(1)
    card.get_by_role("button", name="Collapse the card").click()
    expect(chat).to_be_visible()
    # Once shown, by the next frame (a ResizeObserver's callback, before the paint).
    page.wait_for_function(f"({AT_BOTTOM})(document.querySelector('.chat-feed'))", timeout=2000)
    expect(chat.get_by_text("late 5", exact=True)).to_be_in_viewport()
    shot(page)


def test_reading_above_the_human_stays_there_through_the_expanded_card_and_the_next_message(
    page: Page, server, repo, shot
):
    """LAD-48, F5: a hidden feed is not taken for one at the bottom."""
    chat, card, session, read = chat_read_at(page, server, repo, "feed.scrollHeight / 2")
    card.get_by_role("button", name="Expand the card").click()
    expect(chat).to_be_hidden()
    note(session, "later 1")
    expect(chat.get_by_text("later 1", exact=True)).to_have_count(1)
    card.get_by_role("button", name="Collapse the card").click()
    expect(chat).to_be_visible()
    note(session, "later 2")
    expect(chat.get_by_text("later 2", exact=True)).to_have_count(1)
    page.wait_for_timeout(300)
    assert abs(chat.evaluate("feed => feed.scrollTop") - read) <= 2
    shot(page)


def test_a_link_to_an_old_open_question_shows_its_tab_the_chat_had_not_loaded(
    page: Page, server, repo, shot
):
    session, question = long_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity#message-{question}")
    card = waiting_card(page, session)
    expect(card.get_by_role("tab", name="supervisor 1")).to_have_attribute("aria-selected", "true")
    expect(card.locator(f'[data-item="{question}"]')).to_have_class(re.compile(r"\bmarked\b"))
    expect(card).to_contain_text("Old question?")
    chat = page.get_by_role("log", name="Chat with the session")
    assert chat.get_by_role("article").count() <= 50  # no page loaded for it
    shot(page)


def test_the_human_attaches_files_and_the_agent_gets_them(page: Page, server, repo, shot):
    """The paperclip's picker, chips (a PDF with the crossed-out eye and its hint), the drop
    zone, then Send: the message with its chips and the image's preview; the agent's line."""
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    expect(chat).to_contain_text("No messages yet")
    picker = page.locator(".composer input[type=file]")
    picker.set_input_files(
        [
            {"name": "screenshot.png", "mimeType": "image/png", "buffer": SHOT},
            {"name": "server.log", "mimeType": "text/plain", "buffer": b"GET / 500\n" * 300},
            {"name": "spec.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.7\n"},
        ]
    )
    files = page.get_by_role("list", name="Attached files")
    expect(files.get_by_role("listitem")).to_have_count(3)
    expect(page.locator(".composer-to")).to_contain_text("3 files")
    eye = files.get_by_role("button", name="The agent sees only this file's name and size")
    expect(eye).to_have_count(1)
    page.get_by_role("textbox", name="Write to the supervisor…").fill("read")
    shot(page, "files")
    eye.focus()
    hint = page.get_by_role("tooltip")
    expect(hint).to_contain_text("Agents read text and PNG")
    expect(hint).to_have_attribute("data-side", re.compile(r"^(below|above)$"))
    arrow = hint.evaluate(
        "el => { const a = getComputedStyle(el, '::before');"
        " return { content: a.content, x: el.getBoundingClientRect().left + parseFloat(a.left) } }"
    )
    eye_box = eye.bounding_box()
    assert eye_box is not None and arrow["content"] == '""'
    assert abs(arrow["x"] - (eye_box["x"] + eye_box["width"] / 2)) <= 1  # at the eye's centre
    shot(page, "hint")
    page.locator(".chat-feed").dispatch_event(
        "dragenter", {"dataTransfer": page.evaluate_handle(DRAGGED)}
    )
    expect(page.get_by_text("Drop to attach · up to 10 files, 25.0 MB each")).to_be_visible()
    shot(page, "drop")
    page.locator(".chat-feed").dispatch_event(
        "dragleave", {"dataTransfer": page.evaluate_handle(DRAGGED)}
    )
    page.get_by_role("button", name="Send").click()
    mine = chat.get_by_role("article", name="Message from you")
    expect(mine.get_by_role("button", name=re.compile(r"^Open artifact "))).to_have_count(3)
    preview = mine.get_by_role("button", name=re.compile(r"^Open image screenshot-"))
    expect(preview.locator("img")).to_have_js_property("naturalWidth", 320)
    box = preview.locator("img").bounding_box()
    assert box is not None and (box["width"], box["height"]) == (240, 135)  # at most 240 × 180
    expect(files).to_have_count(0)
    [message] = [m for m in state.list_messages(session) if m.sender == "human"]
    line = f"[from human] read (#{message.id}, 3 artifacts: call read_messages)"
    agent_helpers.wait_for(lambda: line in inputs(session), "the agent's line", session)
    shot(page, "sent")
    preview.click()
    expect(page.get_by_role("dialog", name=re.compile(r"^Artifact screenshot-"))).to_be_visible()


# Files dragged over the page, as the browser's drag events carry them.
DRAGGED = "() => { const d = new DataTransfer(); d.items.add(new File(['x'], 'x.txt')); return d; }"

SHOT = png(320, 180)
