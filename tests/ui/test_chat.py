"""The chat in a session's Activity tab, in a browser: the human writes to the supervisor
(the fake agent), and answers its question."""

import json

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def inputs(session: str) -> list:
    log = state.home() / "agents" / session / "supervisor" / "inputs.jsonl"
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
    expect(card).to_contain_text("Answered: yes")
    question = next(m for m in state.list_messages(session) if m.kind == state.QUESTION)
    line = f"[from human] Answer to #{question.id}: yes"
    expect(page.get_by_role("article", name="Message from you").last).to_contain_text(
        f"Answer to #{question.id}: yes"
    )
    agent_helpers.wait_for(lambda: line in inputs(session), "the answer", session)
    shot(page, "answered")


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
