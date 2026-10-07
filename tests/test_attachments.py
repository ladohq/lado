"""Artifacts attached to messages, questions and flow notes (docs/design/artifacts.md,
Attachments)."""

import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from lado import artifacts, mcp_server, runs, runtime, state


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
  review: {agent: worker, do: Review it., needs: [build], outcomes: {ok: approve}}
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
    text = runs.step_text(review, runs.flow_of(review))
    assert f"Note from build: built\n{listed}" in text
    assert text.count("Artifacts:") == 1  # the check's note has none


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
