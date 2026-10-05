"""A session's agents in the UI server's API: what each does, the state of its work, and
finishing a worker. In process, with FastAPI's test client."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lado import runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8123
OWN = "http://testserver"  # the test client's Host
AGENTS = "/api/sessions/s/agents"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "Build the layout\nwith three columns", name="w1")
    return "s"


def commit(worktree, name="work.txt"):
    Path(worktree, name).write_text("done\n")
    runtime.git(worktree, "add", name)
    runtime.git(worktree, "commit", "-q", "-m", f"add {name}")


def utc(when) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def test_an_agent_says_its_branch_worktree_and_since_when(client, session):
    state.set_status("s", "w1", state.BUSY)
    supervisor, worker = client.get(AGENTS).json()
    assert (supervisor["branch"], supervisor["worktree"]) == (None, None)
    w1 = state.get_agent("s", "w1")
    assert (worker["branch"], worker["worktree"]) == ("lado/s/w1", w1.cwd)
    spawned, since = state.agent_times("s", "w1")
    assert (worker["spawned_at"], worker["since"]) == (utc(spawned), utc(since))
    assert worker["since"] == utc(state.status_since("s")["w1"])  # as lado ls says
    assert supervisor["spawned_at"] == utc(state.agent_times("s", "supervisor")[0])


def test_details_give_the_whole_task_and_the_state_of_the_work(client, session):
    w1 = state.get_agent("s", "w1")
    commit(w1.cwd)
    Path(w1.cwd, "draft.txt").write_text("x")
    details = client.get(f"{AGENTS}/w1/details").json()
    assert details["task"].startswith("Build the layout\nwith three columns")
    work = details["work"]
    assert {k: work[k] for k in ("branch", "base", "ahead", "behind", "uncommitted")} == {
        "branch": "lado/s/w1",
        "base": "main",
        "ahead": 1,
        "behind": 0,
        "uncommitted": 1,
    }
    assert work["last_commit"]["sha"] == runtime.git(w1.cwd, "rev-parse", "HEAD")
    assert work["last_commit"]["subject"] == "add work.txt"
    assert work["last_commit"]["at"].endswith("Z")
    assert details["work_problem"] is None


def test_details_of_the_supervisor_have_no_work_and_no_problem(client, session):
    assert client.get(f"{AGENTS}/supervisor/details").json() == {
        "task": None,
        "work": None,
        "work_problem": None,
    }


def test_details_say_why_the_work_cannot_be_read(client, session, repo):
    w1 = state.get_agent("s", "w1")
    runtime.git(str(repo), "worktree", "remove", "--force", w1.cwd)
    details = client.get(f"{AGENTS}/w1/details").json()
    assert details["work"] is None
    assert details["work_problem"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/sessions/x/agents/w1/details",
        f"{AGENTS}/w9/details",
        f"{AGENTS}/w9/finish-preview",
    ],
)
def test_an_unknown_session_or_agent_is_404(client, session, path):
    assert client.get(path).status_code == 404


def test_there_is_no_list_of_finished_agents(client, session):
    runtime.finish_worker("s", "w1")
    assert client.get(f"{AGENTS}/finished").status_code == 404


def test_finish_preview_is_the_cores(client, session):
    commit(state.get_agent("s", "w1").cwd)
    preview = client.get(f"{AGENTS}/w1/finish-preview").json()
    assert preview["removes_worktree"] is True
    assert preview["refused"].startswith("branch lado/s/w1 is not merged into main")
    assert (preview["work"]["ahead"], preview["work"]["uncommitted"]) == (1, 0)
    refused = client.get(f"{AGENTS}/supervisor/finish-preview")
    assert refused.status_code == 400
    assert "lado stop s" in refused.json()["detail"]


def test_finish_ends_a_merged_worker_and_says_what_it_did(client, session):
    w1 = state.get_agent("s", "w1")
    answer = client.post(f"{AGENTS}/w1/finish", json={"discard": False})
    assert answer.status_code == 200, answer.text
    assert answer.json()["result"] == (
        f'Finished worker "w1" (merged): removed window, worktree {w1.cwd} and branch lado/s/w1'
    )
    assert state.get_agent("s", "w1") is None


def test_finish_of_unmerged_work_is_refused_and_discard_ends_it(client, session):
    commit(state.get_agent("s", "w1").cwd)
    refused = client.post(f"{AGENTS}/w1/finish", json={"discard": False})
    assert refused.status_code == 400
    assert "is not merged into main" in refused.json()["detail"]
    assert state.get_agent("s", "w1") is not None
    answer = client.post(f"{AGENTS}/w1/finish", json={"discard": True})
    assert answer.json()["result"].startswith('Finished worker "w1" (discarded)')


def test_finish_of_a_run_worker_closes_only_its_window(client, session):
    run = state.Run("s", "feature/x", "feature", "{}", {}, "do x", "design", "/w", "b")
    state.add_run(run, [("lado", state.FLOW_START, "at design")], None)
    state.add_agent(state.Agent("s", "dev", "developer", "/w", "b", "step", "idle", run=run.name))
    preview = client.get(f"{AGENTS}/dev/finish-preview").json()
    assert (preview["removes_worktree"], preview["refused"]) == (False, None)
    answer = client.post(f"{AGENTS}/dev/finish", json={"discard": False})
    assert answer.json()["result"] == 'Finished worker "dev" (closed): closed its window; ' + (
        "run feature/x keeps /w"
    )


def test_finish_in_a_stopped_session_is_refused(client, session):
    runtime.stop_session("s")
    assert client.post(f"{AGENTS}/w1/finish", json={"discard": True}).status_code == 400


def test_finish_needs_the_token_and_the_servers_own_origin(client, session):
    path = f"{AGENTS}/w1/finish"
    del client.headers["origin"]
    assert client.post(path, json={"discard": True}).status_code == 403
    client.headers["origin"] = "http://evil.example"
    assert client.post(path, json={"discard": True}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.post(path, json={"discard": True}).status_code == 401
    assert state.get_agent("s", "w1") is not None
