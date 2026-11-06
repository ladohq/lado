"""The refusals the UI's Retry takes as closed (web/src/attempts.ts): each row of the table
web/src/closedRefusals.cases.json marked closed is made here by the core itself, so a change
of its words fails a test instead of showing the human an error."""

import dataclasses
import json
import re
from pathlib import Path

import pytest

from lado import runs, runtime, state

TABLE = Path(__file__).parent.parent / "web" / "src" / "closedRefusals.cases.json"
CLOSED = {
    (row["kind"], row["text"]) for row in json.loads(TABLE.read_text())["refusals"] if row["closed"]
}
SESSION = "ship"  # S in the table


def _pinned(kind: str, refusal: Exception) -> None:
    assert (kind, re.sub(r"#\d+", "#N", str(refusal)).replace(SESSION, "S")) in CLOSED


def _session() -> None:
    state.add_session(state.Session(SESSION, "/r", None, provider="claude"))
    state.add_agent(
        state.Agent(SESSION, "w1", "worker", "/r", None, None, state.IDLE, provider="claude")
    )


def _closed_gate() -> int:
    run = state.Run(
        session=SESSION,
        name="feature/x",
        flow="feature",
        snapshot='{"name": "feature"}',
        kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
        task="add x",
        state="design",
        worktree="/r/.lado/worktrees/S/feature-x",
        branch="lado/S/feature-x",
    )
    state.add_run(run, [("supervisor", state.FLOW_START, "started")])
    before = state.get_run(SESSION, run.name)
    waiting = dataclasses.replace(before, state="design_ok", status=state.WAITING)
    gate = state.Gate(
        session=SESSION,
        run=run.name,
        state="design_ok",
        kind="approval",
        question="Approve the design?",
        options=["approve", "reject"],
        note="",
        note_body="",
    )
    assert state.update_run(before, waiting, [], opens=gate)
    [opened] = state.open_gates(SESSION)
    now = state.get_run(SESSION, run.name)
    after = dataclasses.replace(now, state="build", status=state.ACTIVE)
    assert state.update_run(now, after, [], closes=("human", "approve", "", opened.id))
    return opened.id


def test_a_gate_closed_already(lado_home):
    _session()
    gate = _closed_gate()
    with pytest.raises(runtime.LadoError) as refused:
        runs.answer(SESSION, str(gate), "approve")
    _pinned("gate", refused.value)


def _reply(question: int) -> state.Reply:
    return state.Reply(question, f"Answer to #{question}: yes", "", "yes", state.ANSWERED)


@pytest.mark.parametrize("closed", ["answered", "dismissed", "closed", "stopped"])
def test_a_question_not_open(lado_home, closed):
    _session()
    question = state.add_question(SESSION, "w1", "Merge?", "", ["yes"], True)
    with state.connect() as db:
        db.execute("UPDATE messages SET question_state = ? WHERE id = ?", (closed, question))
    with pytest.raises(state.QuestionClosed) as refused:
        state.reply_to_questions(SESSION, [_reply(question)])
    _pinned("questions", refused.value)


def test_a_question_gone(lado_home):
    _session()
    with pytest.raises(state.QuestionClosed) as refused:
        state.reply_to_questions(SESSION, [_reply(999)])
    _pinned("questions", refused.value)


def test_a_session_stopped_already(lado_home):
    _session()
    state.stop_session(SESSION)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.stop_session(SESSION)
    _pinned("stop", refused.value)


def test_a_session_already_running(repo, fake_tmux):
    runtime.start_session(str(repo), SESSION, None, provider="claude")
    with pytest.raises(runtime.LadoError) as refused:
        runtime.start_session(str(repo), SESSION, None, provider="claude", resume=True)
    _pinned("resume", refused.value)


def test_every_closed_row_is_made_here():
    assert {kind for kind, _ in CLOSED} == {"gate", "questions", "stop", "resume"}
    assert len(CLOSED) == 8  # a row added above needs its test
