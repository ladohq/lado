"""A session's page in the UI server's API: its run events, all its messages, what waits for
the human in it, and what its agents work on. In process, with FastAPI's test client."""

import pytest
from fastapi.testclient import TestClient

from lado import runtime, state
from lado.server import app as server_app
from lado.server import auth

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
    }
    assert (moved["kind"], moved["actor"], moved["detail"]) == (
        "flow",
        "w1",
        "design -done-> review",
    )
    assert moved["id"] > started["id"]


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

    monkeypatch.setattr(runtime, "waiting_reason", reason)
    supervisor, worker = client.get("/api/sessions/s/agents").json()
    assert (supervisor["waiting_reason"], worker["waiting_reason"]) == (
        None,
        "did not take 1 message",
    )
    assert asked == ["w1"]


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
