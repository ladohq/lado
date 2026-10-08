"""The session's Agents tab in a browser: the agents, a worker's page with the state of its
work in git, and Finish, refused for unmerged work and done with Discard work…, the worker
then gone from the list without a reload."""

import re
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
    page.goto(f"{server['url']}/sessions/{session}/activity")
    page.get_by_role("button", name="Collapse terminals").click()
    page.get_by_role("link", name="Agents · 2").click()
    # Without an agent the tab opens the supervisor, beside the list.
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/agents/supervisor")
    expect(page.get_by_role("link", name="Agents · 2")).to_be_visible()
    agents = page.get_by_role("navigation", name="Agents")
    expect(agents.get_by_role("link").first).to_contain_text("supervisor")
    expect(page.get_by_role("region", name="Agent supervisor")).to_be_visible()
    shot(page, "supervisor")
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

    # The worker is gone from the list with no reload, and the tab opens the supervisor.
    expect(page.get_by_role("link", name="Agents · 1")).to_be_visible()
    expect(agents.get_by_role("link", name="w1")).to_have_count(0)
    expect(agents.get_by_role("button")).to_have_count(0)
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/agents/supervisor")
    assert state.get_agent(session, "w1") is None
    assert not Path(worktree).exists()
    shot(page, "finished")


def test_in_a_narrow_column_the_agents_take_it_and_a_page_is_not_squeezed(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    session, worktree = session_with_worker(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    # The terminals are open: the session's column is narrower than 900 px.
    expect(page.get_by_role("button", name="Collapse terminals")).to_be_visible()
    page.get_by_role("link", name="Agents · 2").click()
    agents = page.get_by_role("navigation", name="Agents")
    expect(agents).to_be_visible()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/agents")
    expect(page.get_by_role("combobox")).to_have_count(0)
    expect(page.get_by_role("region", name=re.compile("^Agent "))).to_have_count(0)
    shot(page, "list")

    agents.get_by_role("link", name="w1").click()
    worker = page.get_by_role("region", name="Agent w1")
    expect(worker).to_contain_text(worktree)
    expect(agents).to_have_count(0)
    # Each fact's name stands above its value, and the values have the page's width.
    facts = worker.locator(".agent-facts")
    page_box = worker.bounding_box()
    for name in ("Branch", "Work", "Worktree", "Task"):
        term = facts.locator("dt").filter(has_text=re.compile(f"^{name}$"))
        label = term.bounding_box()
        value = term.locator("xpath=following-sibling::dd[1]").bounding_box()
        assert value["y"] >= label["y"] + label["height"] - 1, name
        assert value["width"] > page_box["width"] * 0.9, name
    # The composer's frame (the field and Send in it) has the page's width.
    write = worker.locator(".composer-box").filter(
        has=page.get_by_role("textbox", name="Write to w1…")
    )
    assert write.bounding_box()["width"] > page_box["width"] * 0.9
    shot(page, "worker")
    page.get_by_role("link", name="‹ All agents").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/agents")
    expect(agents).to_be_visible()


def test_a_worker_that_crashed_says_why_it_stopped(page: Page, server, repo, shot, monkeypatch):
    page.set_viewport_size({"width": 1600, "height": 1000})
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake")
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    monkeypatch.setenv("FAKE_AGENT_CRASH_AT_START", "1")  # w1 only: the supervisor runs
    runtime.spawn_worker(session, "task", name="w1")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1")
    page.get_by_role("button", name="Collapse terminals").click()
    # The session loop finds its window gone two passes in a row; the feed brings it.
    row = page.get_by_role("navigation", name="Agents").get_by_role("link", name="w1")
    expect(row).to_contain_text("stopped", timeout=30_000)
    expect(row).to_contain_text(runtime.WINDOW_GONE)
    worker = page.get_by_role("region", name="Agent w1")
    expect(worker.get_by_role("note")).to_have_text(f"Stopped: {runtime.WINDOW_GONE}")
    shot(page, "stopped")
