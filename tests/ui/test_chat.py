"""The chat in a session's Activity tab, in a browser: the human writes to the supervisor
(the fake agent), and answers its question."""

import json

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import state

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def tall(page: Page):
    """A window with room for the session's head, the chat and the terminal panel under it;
    in a smaller one the page scrolls (the Layout task moves the terminal beside the chat)."""
    page.set_viewport_size({"width": 1280, "height": 1000})


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
    reply.get_by_text("merged w1").click()
    expect(reply.locator("strong")).to_have_text("All")
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
