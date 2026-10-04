"""Flow runs and their steps' notes in the UI server's API (the Flows tab). In process,
with FastAPI's test client."""

import pytest
from agent_helpers import previous_schema, spoil_snapshot
from fastapi.testclient import TestClient

from lado import runs, runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8124
RUNS = "/api/sessions/s/runs"
NOTES = "/api/sessions/s/notes"

SHIP = """\
name: ship
description: plan, build and ship
start: plan
states:
  plan: {agent: supervisor, do: Plan it., outcomes: {ready: build}}
  build:
    agent: developer
    do: Build it.
    needs: [plan]
    max_visits: 2
    outcomes: {done: check, again: build}
  check:
    gate: approval
    ask: Ship it?
    needs: [plan]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    return client


@pytest.fixture
def session(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "agents").mkdir()
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\ninclude: [default]\n")
    (kit / "agents" / "developer.md").write_text(
        "---\nname: developer\ndescription: d\n---\nYou build.\n"
    )
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["team"])
    return "s"


def at_build(name="x"):
    runs.start("s", "ship", f"Add {name}", name=name)
    return runs.advance("s", "supervisor", f"ship/{name}", "ready", "the plan", "step 1")


def test_a_run_comes_with_its_flow_in_the_order_of_the_snapshot(client, session):
    run = at_build()
    answer = client.get(RUNS)
    assert answer.status_code == 200
    [item] = answer.json()
    assert item["created_at"].endswith("Z") and item["since"].endswith("Z")
    del item["created_at"], item["since"]
    assert item == {
        "name": "ship/x",
        "flow": "ship",
        "kit": {"name": "team", "version": "1.0.0", "source": run.kit["source"]},
        "task": "Add x",
        "state": "build",
        "status": "active",
        "reason": "",
        "acting": "developer (not spawned)",
        "visits": {"plan": 1, "build": 1},
        "gate": None,
        "worktree": run.worktree,
        "branch": run.branch,
        "language": "",
        "ended_at": None,
        "problem": None,
        "states": [
            {
                "name": "plan",
                "kind": "work",
                "agent": "supervisor",
                "gate": None,
                "ask": None,
                "outcomes": {"ready": "build"},
                "max_visits": None,
                "needs": [],
            },
            {
                "name": "build",
                "kind": "work",
                "agent": "developer",
                "gate": None,
                "ask": None,
                "outcomes": {"done": "check", "again": "build"},
                "max_visits": 2,
                "needs": ["plan"],
            },
            {
                "name": "check",
                "kind": "gate",
                "agent": None,
                "gate": "approval",
                "ask": "Ship it?",
                "outcomes": {"approved": "end", "rejected": "build"},
                "max_visits": None,
                "needs": ["plan"],
            },
            {
                "name": "end",
                "kind": "end",
                "agent": None,
                "gate": None,
                "ask": None,
                "outcomes": {},
                "max_visits": None,
                "needs": [],
            },
        ],
    }


def test_acting_is_the_cores_who_acts(client, session):
    at_build()
    runs.spawn_worker("s", "ship/x")
    [item] = client.get(RUNS).json()
    assert item["acting"] == "developer"


def test_a_waiting_run_names_its_open_gate_and_its_time_in_the_state(client, session):
    at_build()
    runs.spawn_worker("s", "ship/x")
    runs.advance("s", "developer", "ship/x", "done", "built")
    gate = state.open_gate("s", "ship/x")
    [item] = client.get(RUNS).json()
    assert (item["status"], item["acting"], item["gate"], item["reason"]) == (
        "waiting",
        "human",
        gate.id,
        "Ship it?",
    )
    last = state.run_events("s")[-1]
    assert item["since"] == last.created_at.replace(" ", "T") + "Z"
    assert item["ended_at"] is None


def test_a_run_whose_flow_cannot_be_read_is_listed_without_it(client, session):
    at_build("bad")
    at_build("good")
    spoil_snapshot("s", "ship/bad")
    answer = client.get(RUNS)
    assert answer.status_code == 200
    listed = {r["name"]: r for r in answer.json()}
    bad = listed["ship/bad"]
    assert bad["states"] == []
    assert bad["problem"].startswith('run "ship/bad": its flow snapshot is not JSON')
    # An active run's actor is its state's agent, which only the flow names.
    assert bad["acting"] == ""
    assert (bad["state"], bad["status"], bad["task"]) == ("build", "active", "Add bad")
    assert listed["ship/good"]["problem"] is None
    assert len(listed["ship/good"]["states"]) == 4


def test_a_waiting_run_whose_flow_cannot_be_read_still_waits_for_the_human(client, session):
    at_build()
    runs.spawn_worker("s", "ship/x")
    runs.advance("s", "developer", "ship/x", "done", "built")
    spoil_snapshot("s", "ship/x")
    [item] = client.get(RUNS).json()
    assert (item["status"], item["acting"], item["states"]) == ("waiting", "human", [])
    assert item["problem"]


def test_ended_and_cancelled_runs_say_when_they_closed_newest_first(client, session):
    at_build("old")
    runs.cancel("s", "ship/old", "not needed")
    at_build("new")
    runs.spawn_worker("s", "ship/new")
    runs.advance("s", "developer", "ship/new", "done", "built")
    runs.answer("s", "ship/new", "approve")
    old, new = state.list_runs("s")
    listed = client.get(RUNS).json()
    assert [r["name"] for r in listed] == ["ship/new", "ship/old"]
    ended = {r["name"]: r for r in listed}
    cancel = [e for e in state.run_events("s") if e.kind == state.FLOW_CANCEL][-1]
    end = [e for e in state.run_events("s") if e.kind == state.FLOW_END][-1]
    assert ended["ship/old"]["ended_at"] == cancel.created_at.replace(" ", "T") + "Z"
    assert ended["ship/new"]["ended_at"] == end.created_at.replace(" ", "T") + "Z"
    assert (ended["ship/old"]["status"], ended["ship/old"]["reason"]) == (
        "cancelled",
        "not needed",
    )
    assert (ended["ship/new"]["status"], ended["ship/new"]["acting"]) == ("ended", "")


def test_the_notes_are_the_steps_of_all_runs_oldest_first(client, session):
    at_build("x")
    at_build("y")
    runs.force("s", "ship/x", "check", "skip the build")
    answer = client.get(NOTES)
    assert answer.status_code == 200
    notes = answer.json()
    assert all(n["created_at"].endswith("Z") for n in notes)
    assert [n["id"] for n in notes] == sorted(n["id"] for n in notes)
    for n in notes:
        del n["created_at"], n["id"]
    assert notes == [
        {
            "run": "ship/x",
            "state": "plan",
            "kind": "report",
            "actor": "supervisor",
            "outcome": "ready",
            "target": "build",
            "summary": "the plan",
            "body": "step 1",
        },
        {
            "run": "ship/y",
            "state": "plan",
            "kind": "report",
            "actor": "supervisor",
            "outcome": "ready",
            "target": "build",
            "summary": "the plan",
            "body": "step 1",
        },
        {
            "run": "ship/x",
            "state": "build",
            "kind": "override",
            "actor": "human",
            "outcome": "",
            "target": "check",
            "summary": "set by the human: skip the build",
            "body": "",
        },
    ]


@pytest.mark.parametrize("path", ["runs", "notes"])
def test_runs_and_notes_need_the_token_and_a_known_session(client, session, path):
    assert client.get(f"/api/sessions/x/{path}").status_code == 404
    client.cookies.clear()
    assert client.get(f"/api/sessions/s/{path}").status_code == 401


@pytest.mark.parametrize("path", ["runs", "notes"])
def test_runs_and_notes_of_another_schema_answer_503(client, session, path):
    previous_schema()
    answer = client.get(f"/api/sessions/s/{path}")
    assert answer.status_code == 503
    assert "lado server" in answer.json()["detail"]
