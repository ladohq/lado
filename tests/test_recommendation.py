"""The lead's recommendation on each question to the human: the request for another
agent's question, the tool's checks (runtime.recommend), the lead's turn end and its
instructions. The gates' requests are in test_runs.py, the state in test_state.py."""

import json
import re

import agent_helpers
import pytest

from lado import hooks, providers, runtime, state


def _hook(event, agent, payload=None):
    """Run a Claude Code hook of agent `agent` in session "s"; returns its decoded output."""
    if event == "SessionStart":
        state.add_event("s", agent, state.MCP_READY, state.get_agent("s", agent).instance)
    claude = providers.get("claude")
    neutral = claude.parse_event(event, json.dumps(payload or {}))
    output = hooks.handle(claude, neutral, "s", agent) if neutral else None
    return json.loads(output) if output else None


@pytest.fixture
def session(repo, fake_tmux):
    """Session s with its lead, idle, and a worker w1."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    state.set_status("s", "supervisor", state.IDLE)
    return "s"


def _requests():
    return [m for m in state.list_messages("s") if m.summary.startswith("recommend on ")]


def _question(sender="w1", choices=("yes", "later"), free=False) -> int:
    runtime.ask_human("s", sender, "Merge now?", "Tests pass.", list(choices or []), free)
    return next(m.id for m in reversed(state.list_messages("s")) if m.kind == state.QUESTION)


def _gate(kind="approval", options=("approve", "reject"), run="f/x") -> state.Gate:
    """An open gate of a run of session s, made in the state alone."""
    gate = state.Gate("s", run, "check", kind, "Ship it?", list(options), "built", "", note_id=None)
    run_row = state.Run("s", run, "f", "{}", {}, "t", "check", "/w", "b", status=state.WAITING)
    state.add_run(run_row, [], opens=gate)
    return gate


def test_a_workers_question_asks_the_lead(session, fake_tmux):
    question = _question()
    [request] = _requests()
    assert (request.sender, request.recipient, request.summary) == (
        "lado",
        "supervisor",
        f"recommend on question #{question} of w1",
    )
    assert request.body == (
        "Merge now?\nTests pass.\nChoices: yes, later\n"
        f"Only the human answers it. Give your own view with recommend(question={question}, "
        "text=..., choice=..., disagrees=...): what you would choose and why, the risks, "
        "what to check; short, no retelling. Write no separate message to the human about it."
    )
    # The lead was idle: it has it now.
    assert request.state == state.SENT
    assert fake_tmux[-1][:3] == ("send_text", "s", "supervisor")
    asked = state.get_message("s", question)
    assert (asked.recommendation_state, asked.recommendation_request) == (
        state.REC_ASKED,
        request.id,
    )


def test_a_question_without_choices_says_so(session):
    question = _question(choices=None, free=True)
    [request] = _requests()
    assert "\nNo choices: the human answers in their own words.\n" in request.body
    assert state.get_message("s", question).recommendation_state == state.REC_ASKED


def test_the_leads_own_question_asks_nothing(session):
    question = _question(sender="supervisor")
    assert _requests() == []
    assert state.get_message("s", question).recommendation_state is None


def test_a_question_while_the_lead_is_stopped_is_asked_without_a_request(session):
    state.set_status("s", "supervisor", state.STOPPED)
    result = runtime.ask_human("s", "w1", "Merge now?")
    assert result.startswith("question #")
    assert _requests() == []
    [question] = [m for m in state.list_messages("s") if m.kind == state.QUESTION]
    assert (question.question_state, question.recommendation_state) == (state.OPEN_QUESTION, None)


def test_recommend_stores_on_a_question(session):
    question = _question()
    result = runtime.recommend(
        "s", "supervisor", " Later: CI is red ", question=question, choice="later"
    )
    assert result == (
        f"recommendation on question #{question} stored; the human sees it on the question's card"
    )
    stored = state.get_message("s", question)
    assert (stored.recommendation_state, stored.recommendation, stored.recommended_choice) == (
        state.REC_GIVEN,
        "Later: CI is red",
        "later",
    )


@pytest.mark.parametrize(
    ("kind", "options", "given", "stored"),
    [
        ("approval", ["approve", "reject"], "Reject", "reject"),
        ("approval", ["approve", "reject"], "approved", "approve"),
        ("choice", ["Left", "right"], "left", "Left"),
        ("loop", ["continue", "cancel"], "continue", "continue"),
        ("approval", ["approve", "reject"], None, None),
    ],
)
def test_recommend_takes_a_gates_option_as_lado_answer_does(session, kind, options, given, stored):
    gate = _gate(kind, options)
    runtime.recommend("s", "supervisor", "My view", gate=gate.id, choice=given)
    assert state.get_gate(gate.id).recommended_choice == stored


def _refused(reason, **kwargs):
    args = {"text": "My view", **kwargs}
    with pytest.raises(runtime.LadoError, match=re.escape(reason)):
        runtime.recommend("s", args.pop("agent", "supervisor"), **args)


def test_recommend_refuses_what_it_cannot_store(session, repo):
    gate = _gate()
    question = _question()
    own = _question(sender="supervisor")
    free = _question(choices=None, free=True)
    _refused("give gate or question, not both", gate=gate.id, question=question)
    _refused("give gate or question")
    _refused("the recommendation is empty", gate=gate.id, text="  ")
    _refused(
        f"the recommendation is {runtime.MAX_MESSAGE + 1} characters, the limit is "
        f"{runtime.MAX_MESSAGE}",
        gate=gate.id,
        text="x" * (runtime.MAX_MESSAGE + 1),
    )
    _refused(f"no gate #{gate.id + 5}", gate=gate.id + 5)
    _refused(
        f'no option "maybe" for gate #{gate.id}; options: approve, reject',
        gate=gate.id,
        choice="maybe",
    )
    _refused(f"no question #{gate.id + 99} in session s", question=gate.id + 99)
    _refused(f"question #{own} is your own", question=own)
    _refused(f"question #{free} has no choices", question=free, choice="yes")
    _refused(
        f'question #{question} has no choice "maybe"; its choices: yes, later',
        question=question,
        choice="maybe",
    )
    _refused("only the supervisor recommends", gate=gate.id, agent="w1")
    for item in (state.get_gate(gate.id), state.get_message("s", question)):
        assert item.recommendation_state != state.REC_GIVEN


def test_recommend_refuses_another_sessions_gate(session, repo):
    gate = _gate()
    with state.connect() as db:
        db.execute("INSERT INTO sessions (name, repo) VALUES ('t', '/t')")
        db.execute("UPDATE gates SET session = 't' WHERE id = ?", (gate.id,))
    _refused(f"no gate #{gate.id}", gate=gate.id)


def test_recommend_refuses_a_closed_gate_or_question(session):
    gate = _gate()
    run = state.get_run("s", "f/x")
    after = state.Run(**{**run.__dict__, "status": state.ACTIVE})
    assert state.update_run(run, after, [], closes=("human", "approve", "", gate.id))
    _refused(f"gate #{gate.id} is closed already: approve by human", gate=gate.id)
    question = _question()
    runtime.dismiss_question("s", question)
    _refused(f"question #{question} is dismissed", question=question)


def test_a_recommendation_replaces_the_earlier_one(session):
    gate = _gate()
    runtime.recommend("s", "supervisor", "Reject", gate=gate.id, choice="reject", disagrees=True)
    runtime.recommend("s", "supervisor", "Approve", gate=gate.id, choice="approve")
    stored = state.get_gate(gate.id)
    assert (stored.recommendation, stored.recommended_choice, stored.recommendation_disagrees) == (
        "Approve",
        "approve",
        False,
    )


def _lead_got_a_request(session):
    """The lead, busy in a turn, got the request for w1's question and confirmed it."""
    _hook("SessionStart", "supervisor")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
    question = _question()
    [request] = _requests()
    state.set_status("s", "supervisor", state.BUSY)
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (state.DELIVERED, request.id))
    return question


def test_a_turn_end_marks_a_request_the_lead_got_missing(session):
    question = _lead_got_a_request(session)
    _hook("Stop", "supervisor")
    assert state.get_message("s", question).recommendation_state == state.REC_MISSING
    # Given later, it replaces "missing".
    runtime.recommend("s", "supervisor", "Later", question=question, choice="later")
    assert state.get_message("s", question).recommendation_state == state.REC_GIVEN


def test_a_workers_turn_end_marks_nothing(session):
    question = _lead_got_a_request(session)
    _hook("SessionStart", "w1")
    _hook("Stop", "w1")
    assert state.get_message("s", question).recommendation_state == state.REC_ASKED


def test_a_turn_end_with_a_planned_resume_keeps_asked(session, monkeypatch):
    monkeypatch.setattr(runtime, "RESUME_DELAYS", (30.0,))
    question = _lead_got_a_request(session)
    _hook("StopFailure", "supervisor", {"error": "overloaded"})
    assert state.get_agent("s", "supervisor").resume_at is not None
    assert state.get_message("s", question).recommendation_state == state.REC_ASKED


def test_a_request_handed_over_in_the_hook_output_is_not_marked_by_that_turn_end(session):
    _hook("SessionStart", "supervisor")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
    question = _question()  # the lead is busy: the request waits in its queue
    [request] = _requests()
    assert request.state == state.PENDING
    output = _hook("Stop", "supervisor")
    assert f"recommend on question #{question}" in json.dumps(output)
    assert state.get_message("s", request.id).channel == state.HOOK_OUTPUT
    assert state.get_message("s", question).recommendation_state == state.REC_ASKED
    # The turn that goes on from that output ends: the lead had it.
    _hook("Stop", "supervisor", {"stop_hook_active": True})
    assert state.get_message("s", question).recommendation_state == state.REC_MISSING


def test_a_request_still_in_the_queue_stays_asked_at_the_turn_end(session, monkeypatch):
    _hook("SessionStart", "supervisor")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
    question = _question()
    # The hand-over at the turn's end is not reached yet when the check runs.
    monkeypatch.setattr(runtime, "hand_over", lambda *args, **kwargs: "")
    _hook("Stop", "supervisor")
    assert state.get_message("s", question).recommendation_state == state.REC_ASKED


def test_the_instructions_name_recommend_and_forbid_a_separate_message():
    text = " ".join(runtime.SUPERVISOR_INSTRUCTIONS.split())
    assert "- recommend(text, gate | question, choice, disagrees):" in text
    assert "answer only with recommend" in text
    assert "never a separate message to the human about it" in text
    assert "set disagrees" in text
    assert "not a retelling" in text
    flows_text = " ".join(runtime.FLOW_INSTRUCTIONS.split())
    assert "LADO asks you for your recommendation on it; give it with recommend." in flows_text
