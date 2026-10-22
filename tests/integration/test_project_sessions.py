"""Sessions in projects as the human meets them: `lado start --project --repo` and its
refusals as the CLI's own process, the supervisor's start_session from its `lado mcp`
through real tmux, hooks and the session loop, `lado project delete` with sessions, and the
upgrade of a lado.db from before projects had sessions (openspec change
sessions-in-projects). The fake agent stands in for an LLM."""

import json
import os
import subprocess
import sys

import agent_helpers
import fake_provider
import pytest
from agent_helpers import bare_remote, fake_logs, init_repo, wait_for

from lado import projects, runtime, state

pytestmark = pytest.mark.integration


@pytest.fixture
def shop(tmp_path, monkeypatch):
    """LADO_REPOS=<tmp>/ws (for the CLI's processes and the agents, which inherit it), the
    project shop titled Shop and its repository frontend made by hand; the repository."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    return init_repo(projects.folder("shop") / "frontend")


def lado(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def idle(session: str) -> bool:
    agent = state.get_agent(session, "supervisor")
    return agent is not None and agent.status == state.IDLE


def seen(session: str) -> dict:
    path = fake_logs(session, "supervisor") / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def stop_all() -> None:
    for sess in state.list_sessions():
        if not sess.stopped_at:
            runtime.stop_session(sess.name)


IN_SHOP = "lado: {} belongs to the project Shop: start a session in the project"


def test_a_session_in_a_project_starts_shows_in_ls_and_resumes_with_it(shop):
    try:
        started = lado(
            "start", "--project", "shop", "--repo", "frontend", "--provider", "fake", "--no-attach"
        )
        assert started.returncode == 0, started.stderr
        assert f'Started session "shop-frontend" in {shop} (project shop)' in started.stdout
        wait_for(lambda: idle("shop-frontend"), "the supervisor idle", "shop-frontend")
        sess = state.get_session("shop-frontend")
        assert (sess.repo, sess.project) == (str(shop), "shop")
        listed = lado("ls").stdout.splitlines()
        assert listed[0] == f"shop-frontend  {shop}  project shop"
        assert lado("stop", "shop-frontend").returncode == 0
        again = lado("start", "--project", "shop", "--repo", "frontend", "--no-attach")
        assert again.returncode == 0, again.stderr
        assert again.stdout.startswith(f'Resumed session "shop-frontend" in {shop}')
        assert state.get_session("shop-frontend").project == "shop"
    finally:
        stop_all()


def _approve_and_start(session: str, name: str) -> None:
    """The supervisor of `session` writes a brief, asks the human to start `name` with it,
    the human approves, and the supervisor calls start_session: its result in `seen`."""
    choice = runtime.START_CHOICE.format(name=name)
    runtime.send_message(session, "human", "supervisor", "artifact_write brief brief.md")
    wait_for(lambda: "artifact_write" in seen(session), "the brief written", session)
    runtime.send_message(
        session, "human", "supervisor", f"askhuman Start {name}? | {choice}, No --artifacts brief"
    )
    question = wait_for(
        lambda: next((m for m in state.list_messages(session) if m.kind == state.QUESTION), None),
        "the question",
        session,
    )
    runtime.answer_question(session, question.id, choice, None)
    runtime.send_message(session, "human", "supervisor", f"start_session {name} {question.id}")
    wait_for(lambda: "start_session_text" in seen(session), "start_session's result", session)


def test_the_supervisors_session_is_in_its_project(shop):
    (shop / "brief.md").write_text("# Fix the login\n")
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    try:
        wait_for(lambda: idle("shop-frontend"), "the supervisor idle", "shop-frontend")
        _approve_and_start("shop-frontend", "fix-login")
        assert seen("shop-frontend")["start_session"]["session"] == "fix-login"
        fix = state.get_session("fix-login")
        assert (fix.repo, fix.project) == (str(shop), "shop")
        wait_for(lambda: idle("fix-login"), "fix-login's supervisor idle", "fix-login")
        runtime.stop_session("fix-login")
        runtime.start_session(str(shop), "fix-login", None, resume=True)  # as the UI resumes
        assert state.get_session("fix-login").project == "shop"
    finally:
        stop_all()


def test_start_session_from_a_session_without_a_project_inside_projects_is_refused(shop):
    (shop / "brief.md").write_text("# Fix the login\n")
    runtime.start_session(None, "site", None, "fake", project="shop", repo_name="frontend")
    with state.connect() as db:  # as a session started there before schema 33
        db.execute("UPDATE sessions SET project = NULL WHERE name = 'site'")
    try:
        wait_for(lambda: idle("site"), "the supervisor idle", "site")
        _approve_and_start("site", "fix-login")
        text = " ".join(seen("site")["start_session_text"])
        assert f"{shop} belongs to the project Shop: start a session in the project" in text
        assert state.get_session("fix-login") is None
    finally:
        stop_all()


def test_every_new_session_without_the_project_is_refused_and_nothing_is_made(shop, tmp_path):
    folder = lado("start", str(shop), "--provider", "fake", "--no-attach")
    assert (folder.returncode, folder.stderr.splitlines()) == (
        1,
        [
            IN_SHOP.format(shop),
            "lado: Start a session in the project: lado start --project shop --repo frontend",
        ],
    )
    web = projects.folder("shop") / "web"
    cloned = lado("start", bare_remote(tmp_path), str(web), "--provider", "fake", "--no-attach")
    assert (cloned.returncode, cloned.stderr.splitlines()[0]) == (1, IN_SHOP.format(web))
    site = projects.folder("shop") / "site"
    fresh = lado("start", "--new", str(site), "--provider", "fake", "--no-attach")
    assert (fresh.returncode, fresh.stderr.splitlines()[0]) == (1, IN_SHOP.format(site))
    assert sorted(p.name for p in projects.folder("shop").iterdir()) == ["frontend"]
    assert state.list_sessions() == []


def test_delete_refuses_a_running_session_then_forgets_it_stopped(shop):
    try:
        runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
        wait_for(lambda: idle("shop-frontend"), "the supervisor idle", "shop-frontend")
        refused = lado("project", "delete", "shop", "--yes")
        assert (refused.returncode, refused.stderr) == (
            1,
            "lado: project shop has sessions not stopped: shop-frontend; stop them first with "
            "lado stop <name>\n",
        )
        assert shop.is_dir() and state.get_project("shop")
        assert lado("stop", "shop-frontend").returncode == 0
        deleted = lado("project", "delete", "shop", "--yes")
        assert deleted.returncode == 0, deleted.stderr
        assert deleted.stdout.splitlines()[0] == "Sessions to forget: shop-frontend"
        assert not os.path.lexists(projects.folder("shop")) and state.get_project("shop") is None
        assert state.get_session("shop-frontend") is None
        assert "shop-frontend" not in lado("ls").stdout
    finally:
        stop_all()


def test_delete_refuses_while_a_session_from_before_projects_runs_in_its_folder(shop):
    runtime.start_session(None, "site", None, "fake", project="shop", repo_name="frontend")
    with state.connect() as db:  # started there before schema 33: no project
        db.execute("UPDATE sessions SET project = NULL WHERE name = 'site'")
    try:
        wait_for(lambda: idle("site"), "the supervisor idle", "site")
        refused = lado("project", "delete", "shop", "--yes")
        assert refused.returncode == 1
        assert "has sessions not stopped: site;" in refused.stderr
        assert shop.is_dir() and state.get_project("shop")
    finally:
        stop_all()


def test_a_session_from_before_schema_33_under_projects_resumes_without_a_project(shop):
    runtime.start_session(None, "site", None, "fake", project="shop", repo_name="frontend")
    wait_for(lambda: idle("site"), "the supervisor idle", "site")
    runtime.stop_session("site")
    with state.connect() as db:
        db.execute("UPDATE sessions SET project = NULL WHERE name = 'site'")
    agent_helpers.previous_schema()
    try:
        resumed = lado("start", str(shop), "--name", "site", "--no-attach")
        assert resumed.returncode == 0, resumed.stderr
        assert state.schema_version() == state.SCHEMA_VERSION
        assert resumed.stdout.startswith(f'Resumed session "site" in {shop}')
        assert state.get_session("site").project is None
    finally:
        stop_all()
