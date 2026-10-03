import re
import shutil
from pathlib import Path

import pytest

from lado import kits, runs, runtime, state, tmux

FEATURE = """\
name: feature
description: New feature, reviewed.
start: design
states:
  design:
    agent: supervisor
    do: Design it with the human.
    outcomes: {ready: implement}
  implement:
    agent: developer
    do: Build it.
    needs: [design]
    outcomes: {done: review}
  review:
    agent: reviewer
    do: Review it.
    needs: [implement]
    max_visits: 2
    outcomes: {approved: merge, changes: implement, again: review}
  merge:
    agent: supervisor
    do: Merge it.
    outcomes: {merged: done}
  gated:
    gate: approval
    ask: Ship it?
    outcomes: {approved: done, rejected: implement}
  done:
    end: true
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def team(repo):
    """A project kit with a developer, a reviewer and the feature flow."""
    kit = repo / ".lado" / "kits" / "team"
    write(kit / "kit.yaml", "name: team\nversion: 1.2.0\ninclude: [default]\n")
    for role in ("developer", "reviewer"):
        write(
            kit / "agents" / f"{role}.md", f"---\nname: {role}\ndescription: d\n---\nYou {role}.\n"
        )
    # "gated" is only reached by flow-set: give it a way in, so the flow is valid.
    write(
        kit / "flows" / "feature.yaml",
        FEATURE.replace("{merged: done}", "{merged: done, hold: gated}"),
    )
    return kit


@pytest.fixture
def session(repo, team, fake_tmux):
    runtime.start_session(str(repo), "s", None, kit_names=["team"])
    return "s"


def messages(recipient):
    return [m for m in state.list_messages("s") if m.recipient == recipient]


def test_start_creates_the_run_with_its_own_worktree_and_snapshot(session, repo, team):
    run = runs.start(session, "feature", "Add a login page. It needs a form.")
    assert run.name == "feature/add-a-login-page"
    assert (run.state, run.status, run.visits) == ("design", state.ACTIVE, {"design": 1})
    assert run.branch == "lado/s/feature-add-a-login-page"
    assert run.worktree == str(repo / ".lado" / "worktrees" / "s" / "feature-add-a-login-page")
    assert Path(run.worktree, ".git").exists()
    assert run.kit == {
        "name": "team",
        "version": "1.2.0",
        "source": f"project: {team.resolve()}",
    }
    # Later edits of the kit do not change a running run.
    (team / "flows" / "feature.yaml").write_text("broken")
    assert runs.flow_of(state.get_run(session, run.name)).states["design"].do == (
        "Design it with the human."
    )
    start, *_ = [e for e in state.list_events(session) if e.run == run.name]
    assert (start.agent, start.kind) == ("supervisor", state.FLOW_START)
    assert "team 1.2.0" in start.detail


def test_a_supervisor_step_is_sent_to_the_supervisor(session):
    runs.start(session, "feature", "Add a login page", name="login")
    [step] = messages("supervisor")
    assert (step.sender, step.summary) == ("lado", "flow feature/login: step design")
    assert "Add a login page" in step.body
    assert "Design it with the human." in step.body
    assert 'flow_advance(run="feature/login", outcome=...)' in step.body
    assert "ready -> implement" in step.body


def test_every_step_asks_for_notes_in_the_humans_language(session):
    runs.start(session, "feature", "Add a login page", name="login", language="ru")
    runs.advance(session, "supervisor", "feature/login", "ready", "agreed")
    runs.spawn_worker(session, "feature/login")
    asked = "Write note_summary and note_body in ru: the human reads them at gates."
    assert asked in messages("supervisor")[0].body
    assert asked in state.get_agent(session, "developer").task
    runs.start(session, "feature", "Other", name="other")
    assert "note_summary and note_body in" not in messages("supervisor")[-1].body


def test_a_language_is_one_short_line(session):
    with pytest.raises(runtime.LadoError, match="human_language is a language name or code"):
        runs.start(session, "feature", "x", language="ru\nen")
    assert state.list_runs(session) == []


def test_a_task_longer_than_a_message_is_refused(session):
    with pytest.raises(runtime.LadoError, match="write the details to a file"):
        runs.start(session, "feature", "x" * (runtime.MAX_MESSAGE + 1))
    assert state.list_runs(session) == []


def test_run_names_are_unique(session):
    assert runs.start(session, "feature", "x", name="login").name == "feature/login"
    with pytest.raises(runtime.LadoError, match='a run "feature/login" already exists'):
        runs.start(session, "feature", "x", name="login")
    assert runs.start(session, "feature", "Login").name == "feature/login-2"


def to_implement(session):
    """A run in step implement, with no developer yet."""
    runs.start(session, "feature", "Add a login page", name="login")
    return runs.advance(session, "supervisor", "feature/login", "ready", "design agreed", "a\nb")


def test_a_step_without_its_worker_asks_the_supervisor_for_one(session):
    run = to_implement(session)
    assert (run.state, run.note, run.note_body) == ("implement", "design agreed", "a\nb")
    ask = messages("supervisor")[-1]
    assert ask.summary == "flow feature/login: step implement needs a developer"
    assert 'spawn_worker(role="developer", run="feature/login")' in ask.body
    assert runs.acting(run) == "developer (not spawned)"
    [transition] = [e for e in state.list_events(session) if e.kind == state.FLOW]
    assert (transition.agent, transition.detail) == ("supervisor", "design -ready-> implement")


def test_the_supervisor_gets_what_its_own_advance_caused_as_notices(session):
    runs.start(session, "feature", "Add a login page", name="login")
    notices = []
    runs.advance(session, "supervisor", "feature/login", "ready", "agreed", notices=notices)
    assert notices == [
        "flow feature/login: step implement needs a developer\n"
        'Start one with spawn_worker(role="developer", run="feature/login"); it gets the '
        "step as its task."
    ]
    assert [m.summary for m in messages("supervisor")] == ["flow feature/login: step design"]


def test_the_supervisor_gets_what_its_own_start_caused_as_notices(session, team):
    write(
        team / "flows" / "quick.yaml",
        "name: quick\ndescription: d\nstart: build\nstates:\n"
        "  build: {agent: developer, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n",
    )
    notices = []
    runs.start(session, "quick", "x", name="x", notices=notices)
    assert notices[0].startswith("flow quick/x: step build needs a developer\n")
    assert messages("supervisor") == []


def test_what_a_worker_caused_still_goes_to_the_supervisor(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    notices = []
    runs.advance(session, "developer", "feature/login", "done", "built", notices=notices)
    assert notices == []
    assert messages("supervisor")[-1].summary == "flow feature/login: step review needs a reviewer"


def test_a_worker_spawned_for_the_step_drops_the_pending_request_for_it(session):
    def asks():
        return [(m.summary, m.state) for m in messages("supervisor") if "needs a" in m.summary]

    to_implement(session)
    runs.start(session, "feature", "other", name="other")
    runs.advance(session, "supervisor", "feature/other", "ready")  # needs a developer too
    runs.spawn_worker(session, "feature/login")
    assert asks() == [
        ("flow feature/login: step implement needs a developer", state.DROPPED),
        ("flow feature/other: step implement needs a developer", state.PENDING),
    ]
    runs.advance(session, "developer", "feature/login", "done", "built")
    assert asks()[-1] == ("flow feature/login: step review needs a reviewer", state.PENDING)
    runs.spawn_worker(session, "feature/login")
    assert asks()[-1] == ("flow feature/login: step review needs a reviewer", state.DROPPED)
    assert asks()[1][1] == state.PENDING


def test_a_worker_for_a_run_works_in_its_worktree_and_gets_the_step(session, fake_tmux):
    run = to_implement(session)
    worker = runs.spawn_worker(session, "feature/login")
    assert (worker.role, worker.run, worker.cwd, worker.branch) == (
        "developer",
        "feature/login",
        run.worktree,
        run.branch,
    )
    first = fake_tmux[-1][-1][-1]
    assert first.startswith("Run feature/login (flow feature), step implement.")
    assert "Build it." in first
    assert "Note from design (also the previous step's note): design agreed\na\nb" in first
    assert "- done -> review" in first
    assert runs.acting(state.get_run(session, "feature/login")) == "developer"
    # The step has its worker now: another one needs a task of its own.
    with pytest.raises(runtime.LadoError, match="has no step for a developer now"):
        runs.spawn_worker(session, "feature/login", role="developer")
    second = runs.spawn_worker(session, "feature/login", role="reviewer", task="Read the plan.")
    assert second.task == "Read the plan."


def fail_launch(monkeypatch, what="new_window"):
    def launch(*args):
        raise tmux.TmuxError("command too long")

    monkeypatch.setattr(tmux, what, launch)


def test_a_failed_spawn_for_a_run_leaves_no_ghost_worker(session, fake_tmux, monkeypatch):
    to_implement(session)
    monkeypatch.setattr(runtime, "FIRST_INPUT_LIMIT", 100)  # the step comes as a message
    fail_launch(monkeypatch)
    with pytest.raises(tmux.TmuxError, match="command too long"):
        runs.spawn_worker(session, "feature/login")
    assert state.get_agent(session, "developer") is None
    assert runs.acting(state.get_run(session, "feature/login")) == "developer (not spawned)"
    assert [m.state for m in messages("developer")] == [state.DROPPED]
    assert not (state.home() / "agents" / session / "developer").exists()
    # The request for a developer still waits for the supervisor.
    ask = messages("supervisor")[-1]
    assert (ask.summary, ask.state) == (
        "flow feature/login: step implement needs a developer",
        state.PENDING,
    )
    monkeypatch.setattr(tmux, "new_window", lambda *a: fake_tmux.append(("new_window", *a)))
    worker = runs.spawn_worker(session, "feature/login")
    assert (worker.name, worker.role) == ("developer", "developer")
    assert runs.acting(state.get_run(session, "feature/login")) == "developer"


def advance_to_review(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait for the review.")
    return runs.advance(session, "developer", "feature/login", "done", "built")


def test_a_step_gets_the_latest_notes_of_the_states_it_needs(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "changes", "fix the form")
    step = messages("developer")[-1].body
    needed = "Note from design: design agreed\na\nb"
    assert needed in step
    # After the task and the step, before the previous step's note.
    assert step.index("Build it.") < step.index(needed)
    assert step.index(needed) < step.index("Note from the previous step: fix the form")


def test_a_needed_note_that_is_the_previous_steps_note_comes_once(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    step = state.get_agent(session, "developer").task
    assert step.count("design agreed") == 1
    assert "Note from design (also the previous step's note): design agreed\na\nb" in step
    assert "Note from the previous step" not in step


def test_a_needed_note_with_the_same_text_as_the_previous_note_is_another_note(session):
    advance_to_review(session)
    # The reviewer's note has the design note's text, but it is a note of its own.
    runs.advance(session, "reviewer", "feature/login", "changes", "design agreed", "a\nb")
    step = messages("developer")[-1].body
    assert "Note from design: design agreed\na\nb" in step
    assert "Note from the previous step: design agreed\na\nb" in step


def test_a_needed_state_with_no_note_yet_is_named(session):
    runs.start(session, "feature", "Add a login page", name="login")
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait for the review.")
    runs.force(session, "feature/login", "review", "the code is there already")
    step = messages("reviewer")[-1]
    assert step.summary == "flow feature/login: step review"
    assert "Note from implement: no note yet" in step.body


def test_flow_set_keeps_the_notes_a_step_needs(session):
    advance_to_review(session)
    runs.force(session, "feature/login", "implement", "rework the form")
    step = messages("developer")[-1]
    assert step.summary == "flow feature/login: step implement"
    assert "Note from design: design agreed\na\nb" in step.body
    assert "Note from the previous step: set by the human: rework the form" in step.body


def test_flow_set_from_a_needed_state_keeps_its_report(session):
    advance_to_review(session)  # implement reported "built"
    runs.advance(session, "reviewer", "feature/login", "changes", "fix the form")
    # The run is at implement again; the human skips it before the developer reports.
    runs.force(session, "feature/login", "review", "the form is fine")
    step = messages("reviewer")[-1]
    assert step.summary == "flow feature/login: step review"
    assert "Note from implement: built" in step.body
    assert "Note from the previous step: set by the human: the form is fine" in step.body


def test_a_loop_limit_answer_or_flow_set_keeps_the_states_report(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again", "first look")
    runs.advance(session, "reviewer", "feature/login", "again", "second look")
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "continue", "one more")
    assert state.latest_notes(session, "feature/login")["review"].summary == "second look"
    runs.advance(session, "reviewer", "feature/login", "again", "third look")
    runs.force(session, "feature/login", "implement", "enough looking")  # from the loop gate
    assert state.latest_notes(session, "feature/login")["review"].summary == "third look"


def test_a_loop_limit_shows_no_needed_notes(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again", "first look")
    runs.advance(session, "reviewer", "feature/login", "again", "second look")
    [gate] = state.open_gates(session)
    assert gate.kind == runs.LOOP  # kept out of review, which needs implement
    assert runs.gate_notes(gate) == []


def test_a_gate_answer_is_kept_as_the_gates_note(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "reject", "the form is too big")
    notes = state.latest_notes(session, "feature/login")
    assert notes["gated"].summary == "rejected: the form is too big"
    assert notes["merge"].summary == "ready to ship"
    step = messages("developer")[-1]
    assert step.summary == "flow feature/login: step implement"
    assert "Note from design: design agreed\na\nb" in step.body


def test_a_worker_step_goes_to_the_next_worker_only(session):
    run = advance_to_review(session)
    assert run.state == "review"
    [step] = messages("reviewer")
    assert (step.sender, step.summary) == ("lado", "flow feature/login: step review")
    assert "Note from implement (also the previous step's note): built" in step.body
    assert [m.summary for m in messages("supervisor")] == [
        "flow feature/login: step design",
        "flow feature/login: step implement needs a developer",
    ]


@pytest.mark.parametrize(
    ("caller", "outcome", "error"),
    [
        ("developer", "approved", 'step review of run "feature/login" is for the run\'s reviewer'),
        ("supervisor", "approved", "is for the run's reviewer"),
        (
            "reviewer",
            "lgtm",
            'unknown outcome "lgtm" for step review; valid: approved, changes, again',
        ),
    ],
)
def test_advance_refuses_other_agents_and_unknown_outcomes(session, caller, outcome, error):
    advance_to_review(session)
    with pytest.raises(runtime.LadoError, match=error):
        runs.advance(session, caller, "feature/login", outcome)
    assert state.get_run(session, "feature/login").state == "review"


def test_a_supervisor_step_is_only_for_the_supervisor(session):
    runs.start(session, "feature", "x", name="login")
    runtime.spawn_worker(session, "task")
    with pytest.raises(runtime.LadoError, match="is for the supervisor"):
        runs.advance(session, "developer", "feature/login", "ready")


def test_an_error_after_the_transition_says_the_run_moved_on(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait.")
    state.set_status(session, "reviewer", state.STOPPED)
    with pytest.raises(runtime.LadoError) as error:
        runs.advance(session, "developer", "feature/login", "done")
    assert str(error.value).startswith(
        'run "feature/login" moved on to review (active), but: no running agent "reviewer"'
    )
    assert state.get_run(session, "feature/login").state == "review"


def test_a_self_loop_enters_the_state_again(session):
    advance_to_review(session)
    run = runs.advance(session, "reviewer", "feature/login", "again")
    assert (run.state, run.visits["review"]) == ("review", 2)
    assert len(messages("reviewer")) == 2


def test_max_visits_stops_the_run_for_the_human(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again")
    run = runs.advance(session, "reviewer", "feature/login", "again")
    assert (run.state, run.status, run.reason) == (
        "review",
        state.WAITING,
        "loop limit reached at review",
    )
    assert run.visits["review"] == 2
    assert runs.acting(run) == "human"
    [gate] = state.open_gates(session)
    assert (gate.run, gate.state, gate.kind, gate.options) == (
        "feature/login",
        "review",
        "loop",
        ["continue", "cancel"],
    )
    assert gate.question == "loop limit reached at review: what next?"
    told = messages("supervisor")[-1]
    assert told.summary == f"flow feature/login: waiting for the human at review (gate #{gate.id})"
    assert f"lado answer {session} {gate.id}" in told.body
    error = (
        f'run "feature/login" waits for the human \\(gate #{gate.id}\\): answer with lado answer'
    )
    with pytest.raises(runtime.LadoError, match=error):
        runs.advance(session, "reviewer", "feature/login", "approved")


def test_the_human_moves_a_run_past_a_stop(session):
    advance_to_review(session)
    run = runs.force(session, "feature/login", "gated", "try the gate")
    assert (run.state, run.status, run.reason) == ("gated", state.WAITING, "Ship it?")
    [gate] = state.open_gates(session)
    assert messages("supervisor")[-1].summary == (
        f"flow feature/login: waiting for the human at gated (gate #{gate.id})"
    )
    run = runs.force(session, "feature/login", "implement", "rework the form")
    assert (run.state, run.status, run.note) == (
        "implement",
        state.ACTIVE,
        "set by the human: rework the form",
    )
    assert messages("developer")[-1].summary == "flow feature/login: step implement"
    forced = [e for e in state.list_events(session) if e.kind == state.FLOW_SET]
    assert [(e.agent, e.detail) for e in forced] == [
        ("human", "review -> gated: try the gate"),
        ("human", "gated -> implement: rework the form"),
    ]
    # No stale gate is left behind.
    assert state.open_gates(session) == []
    closed = state.get_gate(gate.id)
    assert (closed.answer, closed.comment, closed.answered_by) == (
        "overridden",
        "rework the form",
        "human",
    )
    with pytest.raises(runtime.LadoError, match='no state "nope" in flow feature'):
        runs.force(session, "feature/login", "nope", "x")


def to_gate(session):
    """A run waiting at gate "gated", led there by the supervisor's note."""
    to_merge(session)
    return runs.advance(session, "supervisor", "feature/login", "hold", "ready to ship", "a\nb")


def test_a_gate_opens_with_the_note_that_led_to_it_and_a_popup(session, fake_tmux):
    run = to_gate(session)
    assert (run.state, run.status) == ("gated", state.WAITING)
    [gate] = state.open_gates(session)
    assert (gate.kind, gate.question, gate.options) == (
        "approval",
        "Ship it?",
        ["approve", "reject"],
    )
    assert (gate.note, gate.note_body) == ("ready to ship", "a\nb")
    [popup] = [c for c in fake_tmux if c[0] == "popup"]
    _, where, title, argv, env = popup
    # One title for all gates: tmux keeps an open popup and only gives it the new title.
    assert (where, title) == (session, f"LADO: waiting for you (session {session})")
    assert argv[-3:] == ["answer", session, str(gate.id)]
    # The tmux session's environment has the supervisor's LADO_AGENT: not the popup's.
    assert argv[:5] == ["env", "-u", "LADO_AGENT", "-u", "LADO_SESSION"]
    assert env == {"LADO_HOME": str(state.home()), "LADO_TMUX_SOCKET": tmux.socket()}
    assert [m.summary for m in messages("supervisor")][-1] == (
        f"flow feature/login: waiting for the human at gated (gate #{gate.id})"
    )
    assert runs.describe(run)["gate"] == {
        "id": gate.id,
        "question": "Ship it?",
        "options": ["approve", "reject"],
    }


def test_rejecting_sends_the_answer_and_the_earlier_note_to_the_next_step(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    run = runs.answer(session, str(gate.id), "reject", "the form is too big")
    assert (run.state, run.status, run.note) == (
        "implement",
        state.ACTIVE,
        "rejected: the form is too big",
    )
    assert run.note_body == "Note before the gate: ready to ship\na\nb"
    step = messages("developer")[-1]
    assert step.summary == "flow feature/login: step implement"
    assert "Note from the previous step: rejected: the form is too big" in step.body
    # The step went to a worker: the supervisor hears what the human answered.
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: human answered reject at gated"
    )
    closed = state.get_gate(gate.id)
    assert (closed.answer, closed.comment, closed.answered_by) == (
        "reject",
        "the form is too big",
        "human",
    )
    kinds = [(e.agent, e.kind) for e in state.list_events(session)][-2:]
    assert kinds == [("human", state.GATE_ANSWER), ("human", state.FLOW)]
    assert state.list_events(session)[-1].detail == "gated -rejected-> implement"


def test_the_answers_text_says_where_the_run_went(session):
    """One text for every surface of the human: `lado answer`, the popup, the UI."""
    to_gate(session)
    assert runs.answer_text(session, "1", "reject", "too big") == (
        "gate #1: reject. feature/login: gated -> implement (→ developer)"
    )
    to_merge_again = runs.force(session, "feature/login", "gated", "again")
    assert runs.now(to_merge_again) == "waiting for human: gate #2"
    assert runs.answer_text(session, "2", "approved") == (
        "gate #2: approve. feature/login: gated -> done (ended)"
    )


@pytest.mark.parametrize("option", ["approve", "approved", " Approve "])
def test_approving_takes_the_approved_outcome(session, repo, option):
    run = to_gate(session)
    commit(run)
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    run = runs.answer(session, "feature/login", option)
    assert (run.state, run.status, run.note) == ("done", state.ENDED, "approved")
    # Ending tells the supervisor already; no second line about the answer.
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: ended at done; worktree and branch removed"
    )


def test_a_choice_gate_offers_its_outcomes(session, team):
    write(
        team / "flows" / "pick.yaml",
        "name: pick\ndescription: d\nstart: which\nstates:\n"
        "  which: {gate: choice, ask: 'Which way?', outcomes: {left: build, right: end}}\n"
        "  build: {agent: supervisor, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n",
    )
    runs.start(session, "pick", "x", name="x")
    [gate] = state.open_gates(session)
    assert (gate.kind, gate.options, gate.note) == ("choice", ["left", "right"], "")
    with pytest.raises(runtime.LadoError, match='no option "up" for gate #1; options: left, right'):
        runs.answer(session, "1", "up")
    run = runs.answer(session, "1", "left", "go\nslowly")
    assert (run.state, run.note, run.note_body) == ("build", "left: go", "go\nslowly")
    # The supervisor's own step says it all.
    assert [m.summary for m in messages("supervisor")][-2:] == [
        "flow pick/x: waiting for the human at which (gate #1)",
        "flow pick/x: step build",
    ]


def to_loop_limit(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again")
    return runs.advance(session, "reviewer", "feature/login", "again", "still red")


def test_continue_at_a_loop_limit_enters_the_state_anyway(session):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    assert gate.note == "still red"
    run = runs.answer(session, "feature/login", "continue", "one more try")
    assert (run.state, run.status, run.visits["review"]) == ("review", state.ACTIVE, 3)
    assert (run.note, run.note_body) == (
        "continue: one more try",
        "Note before the gate: still red",
    )
    assert messages("reviewer")[-1].summary == "flow feature/login: step review"
    assert state.list_events(session)[-1].detail == "review -continue-> review"
    # The limit stops it again next time.
    run = runs.advance(session, "reviewer", "feature/login", "again")
    assert run.status == state.WAITING


def test_cancel_at_a_loop_limit_cancels_the_run(session):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "cancel", "not worth it")
    run = state.get_run(session, "feature/login")
    assert (run.status, run.reason) == (state.CANCELLED, "loop limit: not worth it")
    assert [a.name for a in state.list_agents(session)] == ["supervisor"]
    assert state.get_gate(gate.id).answer == "cancel"
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: cancelled by the human at review (loop limit)"
    )
    cancelled = [e for e in state.list_events(session) if e.kind == state.FLOW_CANCEL]
    assert [(e.agent, e.detail) for e in cancelled] == [("human", "loop limit: not worth it")]


def test_answer_errors(session):
    to_gate(session)
    with pytest.raises(runtime.LadoError, match="no gate #99"):
        runs.answer(session, "99", "approve")
    with pytest.raises(
        runtime.LadoError, match='no option "ok" for gate #1; options: approve, reject'
    ):
        runs.answer(session, "1", "ok")
    with pytest.raises(runtime.LadoError, match='gate #1 belongs to session "s", not "other"'):
        runs.answer("other", "1", "approve")
    runs.answer(session, "1", "reject")
    with pytest.raises(runtime.LadoError, match="gate #1 is closed already: reject by human"):
        runs.answer(session, "1", "approve")
    with pytest.raises(runtime.LadoError, match='run "feature/login" has no open gate'):
        runs.answer(session, "feature/login", "approve")


@pytest.mark.parametrize("answers", [("reject", "approve"), ("continue", "cancel")])
def test_an_answer_that_lost_a_race_is_refused(session, monkeypatch, answers):
    """Two popups, or a popup and the CLI: the second answer was read before the first
    one moved the run on."""
    first, second = answers
    to_gate(session) if first == "reject" else to_loop_limit(session)
    find_gate = runs.find_gate

    def answered_meanwhile(session, ref):
        gate = find_gate(session, ref)
        monkeypatch.setattr(runs, "find_gate", find_gate)
        runs.answer(session, ref, first)
        return gate

    monkeypatch.setattr(runs, "find_gate", answered_meanwhile)
    moved = state.get_run(session, "feature/login")
    with pytest.raises(runtime.LadoError, match=f"gate #1 is closed already: {first} by human"):
        runs.answer(session, "1", second)
    run = state.get_run(session, "feature/login")
    assert (run.state, run.status, run.visits) != (moved.state, moved.status, moved.visits)
    flow = [
        e.detail for e in state.list_events(session) if e.kind in (state.FLOW, state.FLOW_CANCEL)
    ]
    assert flow[-1] == (
        "gated -rejected-> implement" if first == "reject" else "review -continue-> review"
    )
    assert state.get_gate(1).answer == first


def test_cancelling_a_waiting_run_closes_its_gate(session):
    to_gate(session)
    runs.cancel(session, "feature/login", "dropped")
    assert state.open_gates() == []
    assert state.get_gate(1).answer == "cancelled"


def to_merge(session):
    advance_to_review(session)
    return runs.advance(session, "reviewer", "feature/login", "approved")


def commit(run, name="login.txt"):
    Path(run.worktree, name).write_text("form\n")
    runtime.git(run.worktree, "add", name)
    runtime.git(run.worktree, "commit", "-q", "-m", "login")


def test_end_finishes_the_workers_and_removes_a_merged_worktree(session, repo, fake_tmux):
    run = to_merge(session)
    assert messages("supervisor")[-1].summary == "flow feature/login: step merge"
    commit(run)
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    run = runs.advance(session, "supervisor", "feature/login", "merged")
    assert (run.state, run.status) == ("done", state.ENDED)
    assert [a.name for a in state.list_agents(session)] == ["supervisor"]
    assert ("kill_window", session, "developer") in fake_tmux
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: ended at done; worktree and branch removed"
    )
    assert state.list_runs(session, open_only=True) == []


def test_the_supervisor_that_ends_the_run_gets_the_end_as_a_notice(session, repo):
    run = to_merge(session)
    commit(run)
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    notices = []
    runs.advance(session, "supervisor", "feature/login", "merged", notices=notices)
    assert notices == ["flow feature/login: ended at done; worktree and branch removed"]
    assert messages("supervisor")[-1].summary == "flow feature/login: step merge"


def test_the_supervisor_gets_a_message_when_a_worker_ends_the_run(session, team):
    write(
        team / "flows" / "quick.yaml",
        "name: quick\ndescription: d\nstart: build\nstates:\n"
        "  build: {agent: developer, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n",
    )
    commit(runs.start(session, "quick", "x", name="x", notices=[]))
    runs.spawn_worker(session, "quick/x")
    notices = []
    runs.advance(session, "developer", "quick/x", "done", notices=notices)
    assert notices == []
    assert [m.summary for m in messages("supervisor")] == [
        "flow quick/x: ended at end; kept its worktree and branch"
    ]


def test_a_worker_that_ends_the_run_is_closed_last(session, repo, team, fake_tmux):
    # Its own MCP server runs in its window: closing that window ends the call.
    write(
        team / "flows" / "quick.yaml",
        "name: quick\ndescription: d\nstart: build\nstates:\n"
        "  build: {agent: developer, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n",
    )
    runs.start(session, "quick", "x", name="x")
    runs.spawn_worker(session, "quick/x")
    runs.spawn_worker(session, "quick/x", role="reviewer", task="Watch.")
    state.set_status(session, "supervisor", state.IDLE)
    runs.advance(session, "developer", "quick/x", "done")
    calls = [c[:3] for c in fake_tmux if c[0] in ("send_text", "kill_window")]
    assert calls[-3:] == [
        ("send_text", session, "supervisor"),
        ("kill_window", session, "reviewer"),
        ("kill_window", session, "developer"),
    ]


def test_end_keeps_an_unmerged_worktree_and_says_why(session, repo):
    run = to_merge(session)
    commit(run)
    run = runs.advance(session, "supervisor", "feature/login", "merged")
    assert run.status == state.ENDED
    assert [a.name for a in state.list_agents(session)] == ["supervisor", "developer", "reviewer"]
    assert Path(run.worktree).exists()
    told = messages("supervisor")[-1]
    assert told.summary == "flow feature/login: ended at done; kept its worktree and branch"
    assert f"Branch {run.branch} is not merged into main." in told.body
    assert "workers: developer, reviewer" in told.body
    # Once merged, the last worker finished takes the worktree and branch with it.
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    assert runtime.finish_worker(session, "developer").how == runtime.CLOSED
    assert Path(run.worktree).exists()
    assert runtime.finish_worker(session, "reviewer").how == "merged"
    assert not Path(run.worktree).exists()


def test_end_keeps_a_worktree_with_uncommitted_changes(session, repo):
    run = to_merge(session)
    Path(run.worktree, "draft.txt").write_text("x")
    runs.advance(session, "supervisor", "feature/login", "merged")
    assert "has uncommitted changes" in messages("supervisor")[-1].body
    assert Path(run.worktree, "draft.txt").exists()


def test_finishing_a_worker_of_an_open_run_closes_only_its_window(session):
    run = advance_to_review(session)
    finished = runtime.finish_worker(session, "developer")
    assert (finished.how, finished.removed_worktree) == (runtime.CLOSED, False)
    assert Path(run.worktree).exists()
    assert state.get_agent(session, "developer") is None
    finished = runtime.finish_worker(session, "reviewer", discard=True)
    assert finished.detail() == (
        "closed; discard does not apply: the run keeps its worktree; 1 message dropped"
    )
    assert Path(run.worktree).exists()


def test_cancel_finishes_the_workers_and_keeps_the_worktree(session, repo, fake_tmux):
    run = advance_to_review(session)
    finished = runs.cancel(session, "feature/login", "not needed")
    assert [f.worker.name for f in finished] == ["developer", "reviewer"]
    assert state.list_agents(session)[-1].name == "supervisor"
    run = state.get_run(session, "feature/login")
    assert (run.status, run.reason) == (state.CANCELLED, "not needed")
    assert Path(run.worktree).exists()
    runtime.git(str(repo), "rev-parse", "--verify", run.branch)
    with pytest.raises(runtime.LadoError, match="cancelled: not needed"):
        runs.advance(session, "reviewer", "feature/login", "approved")
    with pytest.raises(runtime.LadoError, match="is cancelled already"):
        runs.cancel(session, "feature/login", "again")


def test_a_run_can_start_at_a_gate(session, team):
    write(
        team / "flows" / "ship.yaml",
        "name: ship\ndescription: d\nstart: gated\nstates:\n"
        "  gated: {gate: approval, ask: 'Ship it?', outcomes: {approved: done, rejected: done}}\n"
        "  done: {end: true}\n",
    )
    run = runs.start(session, "ship", "x")
    assert (run.state, run.status, run.reason) == ("gated", state.WAITING, "Ship it?")
    kinds = [e.kind for e in state.list_events(session) if e.run == run.name]
    assert kinds == [state.FLOW_START, state.GATE_OPEN]
    assert state.open_gate(session, run.name).question == "Ship it?"


def test_status_shows_a_worker_its_own_run(session):
    advance_to_review(session)
    runs.start(session, "feature", "other", name="other")
    [mine] = runs.status(session, "reviewer")
    assert (mine["run"], mine["state"], mine["acting"]) == ("feature/login", "review", "reviewer")
    assert mine["outcomes"] == {"approved": "merge", "changes": "implement", "again": "review"}
    assert mine["visits"] == {"design": 1, "implement": 1, "review": 1}
    with pytest.raises(runtime.LadoError, match='you work for run "feature/login"'):
        runs.status(session, "reviewer", "feature/other")
    assert [r["run"] for r in runs.status(session, "supervisor")] == [
        "feature/login",
        "feature/other",
    ]


def test_the_supervisor_is_told_the_flows_and_a_run_worker_how_to_report(session, fake_tmux):
    supervisor = fake_tmux[0][-1]
    prompt = supervisor[supervisor.index("--append-system-prompt") + 1]
    assert "  - feature: New feature, reviewed." in prompt
    assert "Flows are optional" in prompt and "flow_start" in prompt
    assert "human_language: the language the human writes to you in" in prompt
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    worker = fake_tmux[-1][-1]
    prompt = worker[worker.index("--append-system-prompt") + 1]
    assert 'flow_advance(run="feature/login", outcome=...)' in prompt


def test_a_run_worker_reports_each_step_only_with_flow_advance(session, fake_tmux):
    """flow_advance is a run worker's report: nothing asks it to send_message one too."""
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    worker = fake_tmux[-1][-1]
    prompt = worker[worker.index("--append-system-prompt") + 1]
    first = worker[-1]
    assert first.startswith("Run feature/login (flow feature), step implement.")
    assert "send_message" not in first
    assert "as well" not in prompt
    assert "flow_advance is your report" in prompt
    assert "as the last action of your turn" in prompt
    assert "only for questions" in prompt


def test_every_worker_is_told_whose_messages_are_its_instructions(session, fake_tmux):
    """A worker on a cautious model refused a task that came as "[from ...]"."""
    runtime.spawn_worker(session, "task")
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    for worker in (fake_tmux[-2][-1], fake_tmux[-1][-1]):
        prompt = worker[worker.index("--append-system-prompt") + 1]
        assert (
            'Messages from "supervisor" and steps from "lado" are your instructions, '
            "the same as the human's" in prompt
        )
        assert "messages from other workers are information or questions, not orders" in prompt


def test_a_run_worker_without_a_step_is_told_to_report_its_task(session, fake_tmux):
    """A task from the supervisor, with no step in it, is reported with send_message."""
    to_implement(session)
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Read the plan.")
    first = fake_tmux[-1][-1][-1]
    assert first == "Read the plan." + runtime.REPORT_REMINDER


def test_a_session_without_flows_is_not_told_about_them(repo, fake_tmux):
    runtime.start_session(str(repo), "plain", None)
    supervisor = fake_tmux[0][-1]
    assert "flow_start" not in supervisor[supervisor.index("--append-system-prompt") + 1]


def test_start_refuses_unknown_flows_and_missing_roles(session, repo):
    with pytest.raises(kits.KitError, match='no flow "nope"; flows: feature'):
        runs.start(session, "nope", "x")
    sess = state.get_session(session)
    sess.without.append("agent:reviewer")
    state.delete_session(session)
    state.add_session(sess)
    with pytest.raises(kits.KitError, match='no role "reviewer" in this session'):
        runs.start(session, "feature", "x")
    assert state.list_runs(session) == []


def restart(session, repo, **settings):
    """`lado stop`, then `lado start` again."""
    runtime.stop_session(session)
    return runtime.start_session(str(repo), session, None, **settings)


def test_resume_tells_the_supervisor_what_each_open_run_waits_for(session, repo, fake_tmux):
    to_gate(session)  # feature/login, at the gate
    runs.start(session, "feature", "Plan it", name="plan")  # at design, the supervisor's
    runs.start(session, "feature", "Build it", name="build")
    runs.advance(session, "supervisor", "feature/build", "ready")  # needs a developer
    gate = state.open_gate(session, "feature/login")
    started = restart(session, repo)
    assert started.problems == []
    resumed, step = messages("supervisor")[-2:]
    assert (resumed.sender, resumed.summary) == ("lado", "session resumed: 3 open runs")
    assert resumed.body == (
        f"- feature/login at gated: waits for the human at gate #{gate.id}: Ship it? Only "
        f"the human answers it, with: lado answer {session} {gate.id}. Nothing to do until "
        "then.\n"
        "- feature/plan at design: your step; it follows as a message from lado.\n"
        "- feature/build at implement: needs a developer. Start one with "
        'spawn_worker(role="developer", run="feature/build"); it works in the run\'s '
        "worktree and gets the step as its task."
    )
    assert (step.summary, step.state) == ("flow feature/plan: step design", state.DELIVERED)
    assert "Design it with the human." in step.body
    first = fake_tmux[-1][-1][-1]
    assert first == (
        f"[from lado] session resumed: 3 open runs (#{resumed.id}, 3 lines: call "
        f"read_messages)\n[from lado] flow feature/plan: step design (#{step.id}, "
        f"{len(step.body.splitlines())} lines: call read_messages)"
    )
    assert state.get_agent(session, "supervisor").task == first


def test_a_step_far_longer_than_a_tmux_command_comes_as_a_message(session, fake_tmux):
    runs.start(session, "feature", "Add a login page", name="login")
    plan = "x" * 50_000
    runs.advance(session, "supervisor", "feature/login", "ready", "agreed", plan)
    worker = runs.spawn_worker(session, "feature/login")
    _, _, window, cwd, argv = fake_tmux[-1]
    assert window == "developer"
    # tmux refuses a command over about 16 KB.
    assert sum(len(a) + 1 for a in argv) < 16_000
    [step] = messages("developer")
    assert (step.sender, step.summary, step.state) == (
        "lado",
        "flow feature/login: step implement",
        state.DELIVERED,  # its line is the first input
    )
    assert argv[-1] == (
        f"[from lado] flow feature/login: step implement (#{step.id}, "
        f"{len(step.body.splitlines())} lines: call read_messages)"
    )
    assert plan in step.body
    # implement needs design, whose note is the previous step's: it comes once.
    assert f"Note from design (also the previous step's note): agreed\n{plan}" in step.body
    assert step.body.count(plan) == 1
    assert worker.task == step.body  # the task in full: lado ls, list_agents
    assert state.read_messages(session, "developer")[0].body == step.body


def test_a_long_first_input_of_a_resumed_supervisor_comes_as_a_message(
    session, repo, fake_tmux, monkeypatch
):
    runs.start(session, "feature", "Plan it", name="plan")
    monkeypatch.setattr(runtime, "FIRST_INPUT_LIMIT", 100)
    restart(session, repo)
    *_, first = messages("supervisor")
    assert (first.summary, first.state) == ("your first messages", state.DELIVERED)
    assert first.body.startswith("[from lado] session resumed: 1 open run (#")
    argv = fake_tmux[-1][-1]
    assert argv[-1] == (
        f"[from lado] your first messages (#{first.id}, 2 lines: call read_messages)"
    )


def test_resume_reports_runs_whose_roles_are_gone(session, repo):
    to_implement(session)
    started = restart(session, repo, without=["agent:reviewer"])
    assert started.problems == [
        "run feature/login: role reviewer is not in the session now; cancel the run with "
        "flow_cancel, or move it on with lado flow-set"
    ]
    resumed = messages("supervisor")[-1]
    assert resumed.body.endswith(
        "\n  Role reviewer is not in the session now; cancel the run with flow_cancel, "
        "or move it on with lado flow-set."
    )
    assert state.get_agent(session, "supervisor")  # the session started anyway


def test_a_worker_after_resume_takes_over_the_runs_worktree(session, repo, fake_tmux):
    run = to_implement(session)
    runs.spawn_worker(session, "feature/login")
    commit(run)
    restart(session, repo)
    worker = runs.spawn_worker(session, "feature/login")
    assert (worker.name, worker.cwd, worker.branch) == ("developer", run.worktree, run.branch)
    assert Path(run.worktree, "login.txt").exists()
    assert fake_tmux[-1][-1][-1].startswith("Run feature/login (flow feature), step implement.")


def test_a_missing_run_worktree_is_made_again_from_its_branch(session, repo):
    run = to_implement(session)
    commit(run)
    restart(session, repo)
    shutil.rmtree(run.worktree)
    worker = runs.spawn_worker(session, "feature/login")
    assert worker.cwd == run.worktree
    assert Path(run.worktree, "login.txt").exists()
    assert runtime.git(run.worktree, "rev-parse", "--abbrev-ref", "HEAD") == run.branch


def test_a_run_without_worktree_and_branch_cannot_get_a_worker(session, repo):
    run = to_implement(session)
    restart(session, repo)
    runtime.git(str(repo), "worktree", "remove", "--force", run.worktree)
    runtime.git(str(repo), "branch", "-D", run.branch)
    with pytest.raises(runtime.LadoError, match=f"neither its worktree {run.worktree} nor"):
        runs.spawn_worker(session, "feature/login")
    assert [a.name for a in state.list_agents(session)] == ["supervisor"]


def test_nothing_starts_or_moves_in_a_stopped_session(session):
    run = to_implement(session)
    runtime.stop_session(session)
    stopped = f'session "{session}" is stopped; resume it with `lado start`'
    for call in (
        lambda: runtime.spawn_worker(session, "task"),
        lambda: runs.spawn_worker(session, run.name),
        lambda: runs.start(session, "feature", "x"),
        lambda: runs.advance(session, "supervisor", run.name, "done"),
        lambda: runs.cancel(session, run.name, "x"),
    ):
        with pytest.raises(runtime.LadoError, match=re.escape(stopped)):
            call()
    assert state.get_run(session, run.name) == run
    assert len(state.list_runs(session)) == 1


def test_a_gate_is_answered_after_resume_but_not_while_stopped(session, repo):
    to_gate(session)
    gate = state.open_gate(session, "feature/login")
    runtime.stop_session(session)
    with pytest.raises(runtime.LadoError, match=f'session "{session}" is stopped'):
        runs.answer(session, str(gate.id), "reject")
    with pytest.raises(runtime.LadoError, match=f'session "{session}" is stopped'):
        runs.force(session, "feature/login", "implement", "x")
    assert state.open_gate(session, "feature/login") == gate
    runtime.start_session(str(repo), session, None)
    run = runs.answer(session, str(gate.id), "reject", "one more test")
    assert (run.state, runs.acting(run)) == ("implement", "developer (not spawned)")
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: step implement needs a developer"
    )


def _question_states(session):
    return [m.question_state for m in state.list_messages(session) if m.kind == state.QUESTION]


def test_cancelling_a_run_closes_its_workers_questions(session):
    advance_to_review(session)
    runtime.ask_human(session, "developer", "which form?")
    runs.cancel(session, "feature/login", "not needed")
    assert _question_states(session) == [state.CLOSED]


def test_the_end_of_a_run_closes_its_workers_questions(session, repo):
    run = to_merge(session)
    runtime.ask_human(session, "developer", "which form?")
    commit(run)
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    runs.advance(session, "supervisor", "feature/login", "merged")
    assert _question_states(session) == [state.CLOSED]


def test_stop_preview_tells_what_a_stop_closes_drops_and_keeps(session, repo):
    run = runs.start(session, "feature", "Add a login page.", name="login")
    worker = runtime.spawn_worker(session, "task", name="w1")
    runtime.send_message(session, "supervisor", "w1", "hi")  # w1 is starting: queued
    preview = runtime.stop_preview(session)
    assert preview.agents == ["supervisor", "w1"]
    assert preview.dropped == 2  # and the run's first step, to the starting supervisor
    assert preview.open_runs == ["feature/login"]
    assert preview.worktrees == {run.worktree: run.branch, worker.cwd: worker.branch}
    assert state.get_session(session).stopped_at is None  # a preview changes nothing
    assert runtime.stop_session(session).dropped == preview.dropped
    with pytest.raises(runtime.LadoError, match="is stopped already"):
        runtime.stop_preview(session)
    with pytest.raises(runtime.LadoError, match='unknown session "nope"'):
        runtime.stop_preview("nope")


def test_forget_preview_tells_what_a_forget_drops_and_leaves_on_disk(session):
    run = runs.start(session, "feature", "Add a login page.", name="login")
    with pytest.raises(runtime.LadoError, match="is not stopped"):
        runtime.forget_preview(session)
    runtime.stop_session(session)
    preview = runtime.forget_preview(session)
    assert (preview.runs, preview.worktrees) == (["feature/login"], {run.worktree: run.branch})
    assert state.get_session(session) is not None  # a preview changes nothing
    forgotten = runtime.forget_session(session, force=True)
    assert (forgotten.runs, forgotten.worktrees) == (preview.runs, preview.worktrees)
