"""The session's Agents tab in a browser: the agents, a worker's page with the state of its
work in git, and Finish, refused for unmerged work and done with Discard work…, the worker
then among the finished ones without a reload."""

import uuid
from pathlib import Path

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import loop, runtime, state

pytestmark = pytest.mark.ui


def session_with_worker(repo) -> tuple[str, str]:
    """A running session of the fake agent with worker w1, which committed a file on its
    branch that is not merged."""
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake")
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    worker = runtime.spawn_worker(session, "Build the login form\nwith two steps", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    Path(worker.cwd, "form.txt").write_text("form\n")
    runtime.git(worker.cwd, "add", "form.txt")
    runtime.git(worker.cwd, "commit", "-q", "-m", "the login form")
    return session, worker.cwd


def test_a_workers_page_shows_its_work_and_finish_discards_it(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1600, "height": 1000})
    session, worktree = session_with_worker(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents")
    page.get_by_role("button", name="Collapse terminals").click()
    # Without an agent the tab opens the supervisor.
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/agents/supervisor")
    expect(page.get_by_role("link", name="Agents · 2")).to_be_visible()
    agents = page.get_by_role("navigation", name="Agents")
    expect(agents.get_by_role("link").first).to_contain_text("supervisor")
    agents.get_by_role("link", name="w1").click()
    worker = page.get_by_role("region", name="Agent w1")
    expect(worker).to_contain_text(f"lado/{session}/w1")
    expect(worker).to_contain_text(worktree)
    expect(worker).to_contain_text("1 commit ahead of main · 0 behind · 0 files not committed")
    expect(worker).to_contain_text("“the login form”")
    expect(worker).to_contain_text("Build the login form")
    shot(page, "worker")

    worker.get_by_role("button", name="Finish…").click()
    dialog = page.get_by_role("dialog", name="Finish w1?")
    expect(dialog).to_contain_text(f"branch lado/{session}/w1 is not merged into main")
    shot(page, "refused")
    dialog.get_by_role("button", name="Discard work…").click()
    expect(dialog).to_contain_text("1 commit not in main is lost")
    shot(page, "discard")
    dialog.get_by_role("button", name="Discard and finish").click()
    expect(dialog).to_be_hidden()

    # The worker is gone from the live list and is among the finished, with no reload.
    expect(page.get_by_role("link", name="Agents · 1")).to_be_visible()
    expect(agents.get_by_role("link", name="w1")).to_have_count(0)
    agents.get_by_role("button", name="Finished (1)").click()
    finished = agents.get_by_role("region", name="Finished").get_by_role("link")
    expect(finished).to_contain_text("w1")
    expect(finished).to_contain_text("discarded")
    assert state.get_agent(session, "w1") is None
    assert not Path(worktree).exists()
    finished.click()
    expect(page.get_by_role("region", name="Agent w1")).to_contain_text("discarded")
    shot(page, "finished")
