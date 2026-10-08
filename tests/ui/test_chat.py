"""The chat in a session's Activity tab, in a browser: the human writes to the supervisor
(the fake agent), and answers its question."""

import functools
import json
import re

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_gates import gated_session
from test_images import png
from test_main_screen import log_in, running_session

from lado import runtime, state

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


def test_the_supervisor_asks_and_the_human_answers_in_a_card(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("textbox", name="Write to the supervisor…").fill(
        "askhuman Ship it? | yes, later"
    )
    page.get_by_role("button", name="Send").click()
    card = page.get_by_role("article", name="Question from supervisor")
    expect(card.get_by_role("button", name="later")).to_be_visible()
    shot(page, "open")
    card.get_by_role("button", name="yes").click()
    # The answer is in the card: the choice marked, who answered; no row of its own.
    expect(card.locator(".chosen")).to_have_text("✓ yes")
    expect(card.locator(".question-answer .answer-head")).to_have_text("You · answered")
    expect(card.locator(".answer-choice")).to_have_text("✓ yes")
    expect(page.get_by_role("article", name="Message from you")).to_have_count(1)  # the ask
    question = next(m for m in state.list_messages(session) if m.kind == state.QUESTION)
    line = f"[from human] Answer to #{question.id}: yes"
    agent_helpers.wait_for(lambda: line in inputs(session), "the answer", session)
    shot(page, "answered")


def test_the_chat_looks_as_a_feed_in_light_and_dark(page: Page, server, repo, shot):
    """A group of the supervisor's messages, a closed question and the human's answer, an
    open gate and the composer, in both themes and in a narrow column."""
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
    gate = chat.get_by_role("article", name="Gate #1", exact=True)
    expect(gate.locator(".avatar-gate")).to_be_visible()
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


def test_a_message_with_a_wide_table_shows_it_in_a_frame_and_the_chat_does_not_scroll(
    page: Page, server, repo, shot
):
    session = running_session(repo)
    state.queue_message(session, "supervisor", "human", "DONE", REPORT, mark=state.DELIVERED)
    noted = "Merged.[^1]\n\n[^1]: after the review"
    state.queue_message(session, "supervisor", "human", "merged", noted, mark=state.DELIVERED)
    page.set_viewport_size({"width": 900, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    frame = chat.locator(".md-table")
    expect(frame.get_by_role("columnheader")).to_have_text(["AC", "status", "test"])
    expect(chat.locator("input[type=checkbox]")).to_have_count(2)
    expect(chat.locator("del")).to_have_text("single tilde")
    assert frame.evaluate("frame => frame.scrollWidth > frame.clientWidth")
    assert chat.evaluate("feed => feed.scrollWidth <= feed.clientWidth")
    # A body ends at its text: its last block has no margin under it.
    expect(chat.locator(".chat-body blockquote")).to_have_css("margin-bottom", "0px")
    # A footnote's "Footnotes" heading is for the ear only.
    label = chat.get_by_role("heading", name="Footnotes")
    expect(label).to_have_count(1)
    assert label.bounding_box()["height"] <= 1
    shot(page)


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
    expect(cards.nth(0).locator(".answer-choice")).to_have_text("✓ Inter")
    expect(cards.nth(1).locator(".answer-choice")).to_have_text("✓ yes")
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


def test_needs_you_leads_to_an_old_question_the_chat_had_not_loaded(page: Page, server, repo, shot):
    session, question = long_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    page.get_by_role("link", name=f"Question #{question} in the chat").click()
    chat = page.get_by_role("log", name="Chat with the session")
    card = chat.get_by_role("article", name="Question from supervisor")
    expect(card).to_be_visible()
    assert visible_in(chat, card)
    assert chat.get_by_role("article").count() > 50
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
