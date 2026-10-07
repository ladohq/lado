"""Artifacts attached to messages, questions and flow notes (docs/design/artifacts.md,
Attachments)."""

import asyncio
import json
import os
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from lado import artifacts, artifacts_local, mcp_server, runs, runtime, state


def _call(session, agent, tool, args=None):
    result = asyncio.run(mcp_server.build(session, agent).call_tool(tool, args or {}))
    if result.structured_content is None:  # a dict comes as JSON text
        return json.loads(result.content[0].text)
    return result.structured_content["result"]


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    for agent in ("supervisor", "w1"):
        state.set_status("s", agent, state.BUSY)  # nothing is typed: the line is read below
    return "s"


def _delivered(session, message_id):
    """Hand the message over as a hook would, so read_messages gets it."""
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (state.DELIVERED, message_id))
    return state.get_message(session, message_id)


def _last_message(session):
    return state.list_messages(session)[-1]


def test_a_message_carries_its_artifacts_and_its_line_counts_them(session):
    artifacts.write(session, "w1", "report", content="v1", title="The report")
    artifacts.write(session, "w1", "notes", content="n1")
    _call(
        session,
        "w1",
        "send_message",
        {
            "to": "supervisor",
            "summary": "done",
            "body": "see\nthem",
            "artifacts": ["report", "notes"],
        },
    )
    message = _delivered(session, _last_message(session).id)
    assert runtime.format_message(message) == (
        f"[from w1] done (#{message.id}, 2 lines, 2 artifacts: call read_messages)"
    )
    artifacts.write(session, "w1", "notes", content="n2")  # changed since
    artifacts.write(session, "w1", "report", content="v1")  # rewritten, the same content
    [read] = _call(session, "supervisor", "read_messages")
    assert read["artifacts"] == [
        {
            "name": "report",
            "title": "The report",
            "media_type": "text/markdown",
            "size": 2,
            "changed": False,
        },
        {"name": "notes", "title": None, "media_type": "text/markdown", "size": 2, "changed": True},
    ]


def test_a_message_with_artifacts_and_no_body_is_read_and_its_line_says_so(session):
    artifacts.write(session, "w1", "report", content="v1")
    _call(
        session,
        "w1",
        "send_message",
        {"to": "supervisor", "summary": "done", "artifacts": ["report"]},
    )
    message = _delivered(session, _last_message(session).id)
    assert runtime.format_message(message) == (
        f"[from w1] done (#{message.id}, 1 artifact: call read_messages)"
    )
    [read] = _call(session, "supervisor", "read_messages")
    assert (read["body"], [a["name"] for a in read["artifacts"]]) == ("", ["report"])
    assert state.get_message(session, message.id).state == state.READ
    assert _call(session, "supervisor", "read_messages") == []


def test_a_name_not_found_refuses_the_whole_message(session):
    artifacts.write(session, "w1", "report", content="v1")
    before = state.list_messages(session)
    with pytest.raises(ToolError, match='no artifact "nothing" in session s'):
        _call(
            session,
            "supervisor",
            "send_message",
            {"to": "w1", "summary": "look", "artifacts": ["report", "nothing"]},
        )
    with pytest.raises(ToolError, match='no artifact "nothing"'):
        _call(session, "supervisor", "ask_human", {"question": "ok?", "artifacts": ["nothing"]})
    assert state.list_messages(session) == before


def test_an_attachment_keeps_the_record_of_the_call(session):
    first = artifacts.write(session, "supervisor", "plan", content="v1")
    _call(
        session,
        "supervisor",
        "send_message",
        {"to": "human", "summary": "the plan", "artifacts": ["plan"]},
    )
    artifacts.write(session, "supervisor", "plan", content="v2")
    message = _last_message(session)
    assert state.message_attachments(message.id) == [(first.artifact.id, first.record.id)]


def test_attached_gives_each_record_with_its_artifact_and_looks_for_changes_only_if_asked(
    session, monkeypatch
):
    first = artifacts.write(session, "supervisor", "plan", content="v1", title="Plan")
    artifacts.write(session, "supervisor", "plan", content="v2")
    rows = [(first.artifact.id, first.record.id)]
    [changed] = artifacts.attached(rows, with_changed=True)
    assert (changed.artifact.full_name, changed.artifact.title) == ("plan", "Plan")
    assert (changed.record, changed.changed) == (first.record, True)

    def no_latest(*args):
        raise AssertionError("the latest record was looked up")

    monkeypatch.setattr(artifacts_local.LocalStore, "latest", no_latest)
    [plain] = artifacts.attached(rows)
    assert (plain.record, plain.changed) == (first.record, None)


def test_a_question_to_the_human_carries_artifacts(session):
    written = artifacts.write(session, "supervisor", "mockup.html", content="<p>hi</p>")
    _call(
        session, "supervisor", "ask_human", {"question": "Ship it?", "artifacts": ["mockup.html"]}
    )
    question = _last_message(session)
    assert question.kind == state.QUESTION
    assert state.message_attachments(question.id) == [(written.artifact.id, written.record.id)]


@pytest.mark.parametrize("end", ["stop", "finish"])
def test_an_unread_message_with_only_artifacts_is_dropped_and_counted(session, end):
    artifacts.write(session, "supervisor", "plan", content="v1")
    _call(
        session,
        "supervisor",
        "send_message",
        {"to": "w1", "summary": "plan", "artifacts": ["plan"]},
    )
    message = _delivered(session, _last_message(session).id)
    if end == "stop":
        assert state.unreceived(session) == 1
        assert runtime.stop_session(session).dropped == 1
    else:
        assert runtime.finish_worker(session, "w1", discard=True).dropped == 1
    assert state.get_message(session, message.id).state == state.DROPPED


SHIP = """\
name: ship
description: build, check and review it, then the human approves
start: build
states:
  build: {agent: worker, do: Build it., outcomes: {done: check}}
  check: {agent: worker, do: Check it., outcomes: {ok: review}}
  review: {agent: worker, do: Review it., outcomes: {ok: approve}}
  approve: {gate: approval, ask: "Ship it?", outcomes: {approved: end, rejected: build}}
  end: {end: true}
"""


@pytest.fixture
def run(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
    _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
    _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    return state.get_run("s", "ship/x")


def test_a_flow_note_carries_artifacts_and_the_next_step_names_them(run):
    artifacts.write("s", "worker", "design", content="v1")
    artifacts.write("s", "worker", "plan", content="p1")
    args = {
        "run": "ship/x",
        "outcome": "done",
        "note_summary": "built",
        "artifacts": ["design", "plan"],
    }
    _call("s", "worker", "flow_advance", args)
    note = state.last_note("s", "ship/x")
    assert [a for a, _ in state.note_attachments(note.id)] == [
        artifacts.find("s", "ship/x/design")[0].id,
        artifacts.find("s", "ship/x/plan")[0].id,
    ]
    artifacts.write("s", "worker", "plan", content="p2")
    listed = "Artifacts: ship/x/design, ship/x/plan (changed since)"
    check = state.get_run("s", "ship/x")
    assert f"Note from the previous step: built\n{listed}" in runs.step_text(
        check, runs.flow_of(check)
    )
    _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "ok", "note_summary": "ok"})
    review = state.get_run("s", "ship/x")
    assert "Artifacts:" not in runs.step_text(review, runs.flow_of(review))  # check's has none


def test_a_flow_advance_with_a_name_not_found_moves_nothing(run):
    with pytest.raises(ToolError, match='no artifact "ship/x/design"'):
        _call(
            "s",
            "worker",
            "flow_advance",
            {"run": "ship/x", "outcome": "done", "artifacts": ["design"]},
        )
    assert state.get_run("s", "ship/x").state == "build"
    assert state.run_notes("s", "ship/x") == []


def test_the_previous_steps_note_names_its_artifacts(run):
    artifacts.write("s", "worker", "design", content="v1")
    args = {"run": "ship/x", "outcome": "done", "note_summary": "built", "artifacts": ["design"]}
    _call("s", "worker", "flow_advance", args)
    _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "ok"})
    args = {"run": "ship/x", "outcome": "ok", "note_summary": "fine", "artifacts": ["design"]}
    _call("s", "worker", "flow_advance", args)
    gate = state.open_gate("s", "ship/x")
    assert runs.gate_artifacts(gate) == "Artifacts: ship/x/design"
    runs.answer("s", str(gate.id), "reject", "again")
    after = state.get_run("s", "ship/x")
    assert after.state == "build"
    # The answer's note has no artifacts: the step shows none for it.
    assert "Artifacts:" not in runs.step_text(after, runs.flow_of(after))


def test_a_closed_gate_keeps_the_artifacts_of_its_note_after_the_run_moved_on(run):
    artifacts.write("s", "worker", "design", content="v1")
    _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "done"})
    _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "ok"})
    args = {"run": "ship/x", "outcome": "ok", "note_summary": "fine", "artifacts": ["design"]}
    _call("s", "worker", "flow_advance", args)
    gate = state.open_gate("s", "ship/x")
    runs.answer("s", str(gate.id), "reject", "again")
    artifacts.write("s", "worker", "plan", content="p1")
    args = {"run": "ship/x", "outcome": "done", "note_summary": "rebuilt", "artifacts": ["plan"]}
    _call("s", "worker", "flow_advance", args)
    closed = state.get_gate(gate.id)
    assert runs.gate_artifacts(closed) == "Artifacts: ship/x/design"
    assert [a.artifact.name for a in runs.gate_attachments(closed)] == ["design"]


def test_a_gate_without_a_note_kept_has_no_artifacts(run):
    gate = state.Gate("s", "ship/x", "approve", "approval", "Ship it?", ["approve", "reject"])
    assert (runs.gate_artifacts(gate), runs.gate_attachments(gate)) == ("", [])


def test_forget_removes_the_sessions_artifacts_records_attachments_and_content(
    session, repo, lado_home
):
    other = state.Session("t", str(repo), None, provider="claude")
    state.add_session(other)
    state.add_agent(state.Agent("t", "supervisor", "x", str(repo), None, None, "idle", "claude"))
    artifacts.write("t", "supervisor", "shared", content="the same")
    artifacts.write(session, "supervisor", "shared", content="the same")
    mine = artifacts.write(session, "supervisor", "mine", content="only s")
    _call(
        session, "supervisor", "send_message", {"to": "w1", "summary": "x", "artifacts": ["mine"]}
    )
    content = lado_home / "artifacts" / mine.record.hash[:2] / mine.record.hash
    then = time.time() - 2 * artifacts_local.ORPHAN_AGE
    os.utime(content, (then, then))
    runtime.stop_session(session)
    forgotten = runtime.forget_session(session)
    assert forgotten.artifacts == 2
    with state.connect() as db:
        left = [tuple(r) for r in db.execute("SELECT session, name FROM artifacts")]
        records = db.execute("SELECT DISTINCT session FROM artifact_records").fetchall()
        attachments = db.execute("SELECT count(*) FROM attachments").fetchone()[0]
        deleted = {
            (r["kind"], r["op"])
            for r in db.execute("SELECT kind, op FROM changes WHERE session = ?", (session,))
        }
    assert left == [("t", "shared")] and [tuple(r) for r in records] == [("t",)]
    assert attachments == 0
    assert {("artifacts", "delete"), ("artifact_records", "delete")} <= deleted
    assert not content.exists()
    [(_, shared)] = artifacts.store().list("t")
    assert artifacts.store().content(shared.id) == b"the same"
