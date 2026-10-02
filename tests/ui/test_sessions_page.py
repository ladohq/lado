"""The sessions page in a browser: database → API → UI, behind the token."""

import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect

from lado import loop, runtime, state

pytestmark = pytest.mark.ui


def test_the_link_logs_in_and_the_page_lists_the_sessions(page: Page, server, repo, shot):
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)

    page.goto(f"{server['url']}/?token={server['token']}")
    assert page.url == f"{server['url']}/"  # the token left the address bar
    [cookie] = page.context.cookies()
    assert cookie["name"] == f"lado_token_{server['port']}"
    assert cookie["httpOnly"] and cookie["sameSite"] == "Strict"

    row = page.get_by_role("row").filter(has_text=session)
    expect(row).to_contain_text(str(repo))
    expect(row).to_contain_text("running")
    expect(row.get_by_role("cell").last).to_have_text("1")
    shot(page)

    runtime.stop_session(session)
    page.reload()
    expect(row).to_contain_text("stopped")
    expect(row.get_by_role("cell").last).to_have_text("0")
    shot(page, "stopped")


def test_without_the_token_the_page_says_how_to_get_in(page: Page, server, shot):
    page.goto(f"{server['url']}/")
    expect(page.get_by_role("alert")).to_have_text("no valid token: open the link `lado ui` prints")
    assert page.request.get(f"{server['url']}/api/sessions").status == 401
    shot(page)
