"""A session's page in the UI server's API: its run events, all its messages, what waits for
the human in it, and what its agents work on. In process, with FastAPI's test client."""

import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from lado import doctor, providers, runtime, state
from lado.server import app as server_app
from lado.server import auth, models

PORT = 8123


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    return client


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    return "s"


def add_run(name: str = "feature/x", gate: bool = False) -> None:
    run = state.Run("s", name, "feature", "{}", {}, "do x", "design", "/w", "b")
    opens = state.Gate("s", name, "approve", "approval", "OK?", ["approved", "rejected"])
    state.add_run(run, [("lado", state.FLOW_START, "at design")], opens if gate else None)


def test_events_are_the_run_events_oldest_first(client, session):
    state.add_event("s", "supervisor", state.STATUS, "busy")
    add_run()
    state.add_event("s", "w1", state.FLOW, "design -done-> review", run="feature/x")
    answer = client.get("/api/sessions/s/events")
    assert answer.status_code == 200
    started, moved = answer.json()
    assert started["created_at"].endswith("Z") and "T" in started["created_at"]
    del started["created_at"], moved["created_at"]
    assert started == {
        "id": started["id"],
        "run": "feature/x",
        "kind": "flow_start",
        "actor": "lado",
        "detail": "at design",
        "transition": None,
    }
    assert (moved["kind"], moved["actor"], moved["detail"]) == (
        "flow",
        "w1",
        "design -done-> review",
    )
    assert moved["transition"] == {"from_state": "design", "outcome": "done", "to_state": "review"}
    assert moved["id"] > started["id"]


def test_a_flow_event_whose_detail_is_no_transition_has_none(client, session):
    add_run()
    state.add_event("s", "w1", state.FLOW, "moved somehow", run="feature/x")
    state.add_event("s", "lado", state.FLOW_END, "a -b-> c", run="feature/x")
    _, odd, end = client.get("/api/sessions/s/events").json()
    assert (odd["detail"], odd["transition"]) == ("moved somehow", None)
    # Only a FLOW event is read as a transition, whatever another one's detail says.
    assert (end["kind"], end["transition"]) == ("flow_end", None)


def test_the_events_of_an_unknown_session_are_404(client, session):
    assert client.get("/api/sessions/x/events").status_code == 404


def test_messages_without_with_are_all_the_sessions_messages(client, session):
    runtime.send_message("s", "supervisor", "human", "to the human")
    state.queue_message("s", "w1", "supervisor", "between agents", "")
    every = client.get("/api/sessions/s/messages").json()["items"]
    assert [m["summary"] for m in every] == ["to the human", "between agents"]
    chat = client.get("/api/sessions/s/messages", params={"with": "human"}).json()["items"]
    assert [m["summary"] for m in chat] == ["to the human"]


def waiting(client) -> dict:
    [sess] = client.get("/api/sessions").json()
    return sess["waiting"]


def test_a_session_counts_what_waits_for_the_human(client, session):
    assert waiting(client) == {"gates": 0, "questions": 0, "agents": 0}
    add_run(gate=True)
    add_run("feature/y", gate=True)
    runtime.ask_human("s", "supervisor", "Ship?", None, ["yes"])
    runtime.ask_human("s", "supervisor", "Really?", None, ["yes"])
    [first, _] = [m for m in state.list_messages("s") if m.kind == state.QUESTION]
    runtime.answer_question("s", first.id, "yes")
    state.set_status("s", "supervisor", state.WAITING)
    assert waiting(client) == {"gates": 2, "questions": 1, "agents": 1}


def test_nothing_waits_in_a_stopped_session(client, session):
    add_run(gate=True)
    runtime.ask_human("s", "supervisor", "Ship?", None, ["yes"])
    runtime.stop_session("s")
    assert waiting(client) == {"gates": 0, "questions": 0, "agents": 0}
    assert client.get("/api/waiting").json() == []


def test_what_waits_is_for_the_token_holder_only(session):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    assert client.get("/api/waiting").status_code == 401


def test_an_agent_says_why_it_waits_only_while_it_waits(client, session, monkeypatch):
    state.add_agent(state.Agent("s", "w1", "worker", "/w", "b", "task", "idle", provider="claude"))
    state.set_status("s", "w1", state.WAITING)
    asked = []

    def reason(sess, name):
        asked.append(name)
        return "did not take 1 message"

    monkeypatch.setattr(runtime, "status_reason", reason)
    supervisor, worker = client.get("/api/sessions/s/agents").json()
    assert (supervisor["status_reason"], worker["status_reason"]) == (
        None,
        "did not take 1 message",
    )
    assert asked == ["w1"]


def test_a_stopped_agent_says_why_it_stopped(client, session):
    state.add_agent(state.Agent("s", "w1", "worker", "/w", "b", "task", "busy", provider="claude"))
    state.agent_ended("s", "w1", "its window closed without a session-end hook")
    supervisor, worker = client.get("/api/sessions/s/agents").json()
    assert worker["status"] == "stopped"
    assert worker["status_reason"] == "its window closed without a session-end hook"
    assert supervisor["status_reason"] is None


def test_an_agent_says_its_run_and_the_first_line_of_its_task(client, session):
    task = "\nBuild the layout\nwith three columns"
    state.add_agent(
        state.Agent(
            "s", "w1", "worker", "/w", "b", task, "idle", run="feature/x", provider="claude"
        )
    )
    supervisor, worker = client.get("/api/sessions/s/agents").json()
    assert (supervisor["run"], supervisor["task"]) == (None, None)
    assert (worker["run"], worker["task"]) == ("feature/x", "Build the layout")


# What the session's head shows besides its settings: GET /api/sessions/{name}/about


@pytest.fixture
def statuses(monkeypatch):
    """The provider's state as doctor.provider_status would give it, by provider name."""
    found = {
        "claude": doctor.ProviderStatus(
            True, "2.1.300", "2.1.300 (Claude Code)", "2.1.291", "untested"
        )
    }
    monkeypatch.setattr(doctor, "provider_status", lambda p, which: found[p.name])
    return found


def about(client, name: str = "s") -> dict:
    answer = client.get(f"/api/sessions/{name}/about")
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_about_gives_the_repository_without_the_token_in_its_remote(
    client, repo, session, statuses
):
    url = "https://user:ghp_secret@github.com/ladohq/lado.git"
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    assert about(client)["repos"] == [
        {"path": str(repo), "remote": "https://github.com/ladohq/lado.git", "branch": "main"}
    ]


def test_about_a_session_whose_folder_is_gone_has_no_remote_or_branch(
    client, repo, session, statuses
):
    shutil.rmtree(repo)
    assert about(client)["repos"] == [{"path": str(repo), "remote": None, "branch": None}]


def test_about_gives_each_kit_in_the_sessions_order_with_its_version_and_source(
    client, repo, fake_tmux, statuses
):
    kits_dir = repo / ".lado" / "kits"
    for name in ("team", "broken", "gone"):
        (kits_dir / name).mkdir(parents=True)
        (kits_dir / name / "kit.yaml").write_text(f"name: {name}\nversion: 1.2.0\n")
    runtime.start_session(
        str(repo), "s", None, kit_names=["team", "default", "broken", "gone"], provider="claude"
    )
    (kits_dir / "broken" / "kit.yaml").write_text("name: broken\nnope: 1\n")
    shutil.rmtree(kits_dir / "gone")
    team, default, broken, gone = about(client)["kits"]
    assert team == {
        "name": "team",
        "version": "1.2.0",
        "source": f"project: {kits_dir / 'team'}",
        "valid": True,
        "problem": None,
    }
    assert (default["name"], default["valid"]) == ("default", True)
    assert default["source"].startswith("built-in: ")
    assert (broken["valid"], broken["version"]) == (False, "")
    assert broken["source"] == f"project: {kits_dir / 'broken'}"
    assert "nope" in broken["problem"]
    assert (gone["valid"], gone["version"], gone["source"]) == (False, "", "")
    assert gone["problem"].startswith('kit "gone" not found')


def test_about_gives_the_sessions_provider_with_its_version_and_warning(client, session, statuses):
    provider = about(client)["provider"]
    assert provider == {
        "name": "claude",
        "title": "Claude Code",
        "permission_modes": list(providers.get("claude").permission_modes),
        "install_hint": providers.get("claude").install_hint,
        "installed": True,
        "version": "2.1.300",
        "detail": "2.1.300 (Claude Code)",
        "tested_version": "2.1.291",
        "warning": "untested",
    }


def test_about_an_unknown_session_is_404(client, session):
    assert client.get("/api/sessions/x/about").status_code == 404


@pytest.mark.parametrize("working", [state.BUSY, state.BACKGROUND])
@pytest.mark.parametrize("status", list(runtime.SessionStatus))
def test_a_session_says_how_many_agents_work_only_while_it_runs(
    client, session, monkeypatch, status, working
):
    state.set_status("s", "supervisor", working)
    monkeypatch.setattr(runtime, "session_status", lambda sess: status)
    [sess] = client.get("/api/sessions").json()
    if status == runtime.SessionStatus.RUNNING:
        since = state.status_since("s")["supervisor"]
        assert (sess["busy"], sess["activity_since"]) == (1, models._iso(since))
    else:  # the agents of a dead session may keep their last statuses
        assert (sess["busy"], sess["activity_since"]) == (0, None)
