"""Gates in the UI server's API: the session's gates with the notes behind them, and the
human's answer. In process, with FastAPI's test client."""

import pytest
from agent_helpers import spoil_snapshot
from fastapi.testclient import TestClient

from lado import runs, runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8123
OWN = "http://testserver"  # the test client's Host
GATES = "/api/sessions/s/gates"

SHIP = """\
name: ship
description: plan, build and ship
start: plan
states:
  plan: {agent: supervisor, do: Plan it., outcomes: {ready: build}}
  build:
    agent: supervisor
    do: Build it.
    max_visits: 2
    outcomes: {done: check, polish: polish, again: build}
  polish: {agent: supervisor, do: Polish it., outcomes: {done: check}}
  check:
    gate: approval
    ask: Ship it?
    needs: [plan, polish]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def kit(repo):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    return kit


def at_gate(session="s"):
    """A run of `session` waiting at gate "check", with a note from plan and none from
    polish."""
    runs.start(session, "ship", "Add x", name="x")
    runs.advance(session, "supervisor", "ship/x", "ready", "the plan", "step 1\nstep 2")
    runs.advance(session, "supervisor", "ship/x", "done", "built it", "all\ntests pass")
    return state.open_gate(session, "ship/x")


@pytest.fixture
def session(repo, kit, fake_tmux):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    return "s"


def test_an_open_gate_comes_with_its_note_and_the_notes_it_needs(client, session):
    gate = at_gate()
    answer = client.get(GATES)
    assert answer.status_code == 200
    [listed] = answer.json()
    assert listed["created_at"].endswith("Z")
    plan = listed["needs"][0]["note"]
    assert plan["created_at"].endswith("Z") and plan["id"] > 0
    del listed["created_at"], plan["created_at"], plan["id"]
    assert listed == {
        "id": gate.id,
        "run": "ship/x",
        "state": "check",
        "kind": "approval",
        "question": "Ship it?",
        "options": ["approve", "reject"],
        "note": "built it",
        "note_body": "all\ntests pass",
        "needs": [
            {
                "state": "plan",
                "note": {
                    "run": "ship/x",
                    "state": "plan",
                    "kind": "report",
                    "actor": "supervisor",
                    "outcome": "ready",
                    "target": "build",
                    "summary": "the plan",
                    "body": "step 1\nstep 2",
                },
            },
            {"state": "polish", "note": None},
        ],
        "answer": None,
        "comment": "",
        "answered_by": None,
        "answered_at": None,
        "problem": None,
    }


def test_a_gate_whose_runs_flow_cannot_be_read_comes_without_its_needs(client, session):
    gate = at_gate()
    spoil_snapshot("s", "ship/x")
    answer = client.get(GATES)
    assert answer.status_code == 200
    [listed] = answer.json()
    assert listed["needs"] is None
    assert listed["problem"].startswith('run "ship/x": its flow snapshot is not JSON')
    assert (listed["id"], listed["question"], listed["options"], listed["note"]) == (
        gate.id,
        "Ship it?",
        ["approve", "reject"],
        "built it",
    )


def test_a_closed_gate_has_no_needs_even_after_newer_notes(client, session):
    at_gate()
    runs.answer("s", "1", "reject", "polish it")
    runs.advance("s", "supervisor", "ship/x", "polish", "polishing")
    runs.advance("s", "supervisor", "ship/x", "done", "polished")
    first, second = client.get(GATES).json()
    assert (first["id"], first["answer"], first["comment"], first["answered_by"]) == (
        1,
        "reject",
        "polish it",
        "human",
    )
    assert first["answered_at"].endswith("Z")
    assert first["needs"] is None
    assert second["answer"] is None
    assert [(n["state"], (n["note"] or {}).get("summary")) for n in second["needs"]] == [
        ("plan", "the plan"),
        ("polish", "polished"),
    ]


def test_a_loop_limit_needs_nothing(client, session):
    runs.start("s", "ship", "Add x", name="x")
    runs.advance("s", "supervisor", "ship/x", "ready", "the plan")
    runs.advance("s", "supervisor", "ship/x", "again", "once more")
    runs.advance("s", "supervisor", "ship/x", "again", "and again")
    [gate] = client.get(GATES).json()
    assert (gate["kind"], gate["options"], gate["needs"]) == ("loop", ["continue", "cancel"], [])


def test_the_gates_need_the_token_and_a_known_session(client, session):
    at_gate()
    assert client.get("/api/sessions/x/gates").status_code == 404
    client.cookies.clear()
    assert client.get(GATES).status_code == 401


def test_the_human_answers_a_gate_with_a_comment(client, session):
    at_gate()
    answer = client.post(f"{GATES}/1/answer", json={"option": "reject", "comment": "too big"})
    assert answer.status_code == 200
    assert answer.json() == {"result": "gate #1: reject. ship/x: check -> build (→ supervisor)"}
    run = state.get_run("s", "ship/x")
    assert (run.state, run.note) == ("build", "rejected: too big")
    assert state.get_gate(1).answered_by == "human"


def test_the_comment_is_optional(client, session):
    at_gate()
    assert client.post(f"{GATES}/1/answer", json={"option": "approve"}).status_code == 200
    assert state.get_gate(1).answer == "approve"


def test_an_answer_the_core_refuses_is_400_with_its_reason(client, session, repo):
    at_gate()
    answer = client.post(f"{GATES}/1/answer", json={"option": "maybe"})
    assert answer.status_code == 400
    assert answer.json()["detail"] == 'no option "maybe" for gate #1; options: approve, reject'
    runtime.start_session(str(repo), "t", None, kit_names=["default", "team"], provider="claude")
    at_gate("t")
    other = client.post(f"{GATES}/2/answer", json={"option": "approve"})
    assert (other.status_code, other.json()["detail"]) == (
        400,
        'gate #2 belongs to session "t", not "s"',
    )
    client.post(f"{GATES}/1/answer", json={"option": "reject"})
    again = client.post(f"{GATES}/1/answer", json={"option": "approve"})
    assert (again.status_code, again.json()["detail"]) == (
        400,
        "gate #1 is closed already: reject by human",
    )
    assert state.get_gate(2).answer is None


def test_a_gate_of_a_stopped_session_is_not_answered(client, session):
    at_gate()
    runtime.stop_session("s")
    answer = client.post(f"{GATES}/1/answer", json={"option": "approve"})
    assert answer.status_code == 400
    assert 'session "s" is stopped' in answer.json()["detail"]
    assert state.get_gate(1).answer is None


def test_an_answer_needs_the_servers_own_origin(client, session):
    at_gate()
    client.headers["origin"] = "http://evil.example"
    assert client.post(f"{GATES}/1/answer", json={"option": "approve"}).status_code == 403
    del client.headers["origin"]
    assert client.post(f"{GATES}/1/answer", json={"option": "approve"}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.post(f"{GATES}/1/answer", json={"option": "approve"}).status_code == 401
    assert state.get_gate(1).answer is None


def test_what_waits_for_the_human_is_one_list_counted_by_each_session(client, session):
    gate = at_gate()
    runtime.ask_human("s", "supervisor", "Ship?", "Tests pass.", ["yes"])
    state.add_agent(state.Agent("s", "w1", "worker", "/w", "b", "task", "idle", provider="claude"))
    state.set_status("s", "w1", state.WAITING)
    answer = client.get("/api/waiting")
    assert answer.status_code == 200
    waits, question, agent = answer.json()
    [asked] = [m for m in state.list_messages("s") if m.kind == state.QUESTION]
    assert (waits["key"], waits["session"], waits["kind"]) == (f"gate:{gate.id}", "s", "gate")
    assert waits["gate"] == client.get(GATES).json()[0]  # the gate as the session has it
    assert waits["since"] == waits["gate"]["created_at"]
    assert (waits["question"], waits["agent"]) == (None, None)
    assert (question["key"], question["kind"]) == (f"question:{asked.id}", "question")
    assert question["question"]["summary"] == "Ship?"
    assert question["since"] == question["question"]["created_at"]
    assert (agent["kind"], agent["agent"]["name"]) == ("agent", "w1")
    assert agent["key"] == f"agent:s/w1@{agent['since']}"
    assert agent["since"].endswith("Z")
    assert agent["agent"]["waiting_reason"] is None  # it waits in its terminal
    [sess] = client.get("/api/sessions").json()
    assert sum(sess["waiting"].values()) == len(answer.json()) == 3
