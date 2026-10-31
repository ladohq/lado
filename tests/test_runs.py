import dataclasses
import re
import shutil
from pathlib import Path

import pytest
from agent_helpers import claude_prompt, install_kit, spoil_snapshot

from lado import artifacts, kits, runs, runtime, state, tmux

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
    outcomes: {done: review}
  review:
    agent: reviewer
    do: Review it.
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
    """An installed kit with a developer, a reviewer and the feature flow."""
    kit = repo.parent / "kits" / "team"
    write(kit / "kit.yaml", "name: team\nversion: 1.2.0\n")
    install_kit(kit)
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
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    return "s"


def messages(recipient):
    return [m for m in state.list_messages("s") if m.recipient == recipient]


def first_input(worker):
    """The text of the worker's first message from LADO: its task or step."""
    first = messages(worker)[0]
    assert (first.sender, first.state) == ("lado", state.PENDING)
    return first.body


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
        "source": f"user: {team.resolve()}",
    }
    # Later edits of the kit do not change a running run.
    (team / "flows" / "feature.yaml").write_text("broken")
    assert runs.flow_of(state.get_run(session, run.name)).states["design"].do == (
        "Design it with the human."
    )
    start, *_ = [e for e in state.list_events(session) if e.run == run.name]
    assert (start.agent, start.kind) == ("supervisor", state.FLOW_START)
    assert "team 1.2.0" in start.detail


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("{not json", "not JSON"),
        ("[]", "not a mapping"),
        ('{"name": "feature", "start": "design"}', "states must map state names"),
    ],
)
def test_a_snapshot_that_cannot_be_read_is_one_named_error(session, text, why):
    run = runs.start(session, "feature", "Add x", name="x")
    spoil_snapshot(session, run.name, text)
    spoilt = state.get_run(session, run.name)  # the run itself still reads
    with pytest.raises(runs.SnapshotError, match=why) as error:
        runs.flow_of(spoilt)
    assert isinstance(error.value, runtime.LadoError)
    assert 'run "feature/x"' in str(error.value)


def test_who_acts_in_a_run_whose_flow_cannot_be_read(session):
    run = runs.start(session, "feature", "Add x", name="x")
    spoil_snapshot(session, run.name, "{not json")
    with pytest.raises(runs.SnapshotError):  # an active run's actor is in its flow
        runs.acting(state.get_run(session, run.name))
    waiting = dataclasses.replace(state.get_run(session, run.name), status=state.WAITING)
    assert runs.acting(waiting) == runs.HUMAN


def test_what_is_known_of_who_acts_without_the_flow(session):
    run = runs.start(session, "feature", "Add x", name="x")
    assert runs.acting_or_problem(run) == ("supervisor", None)
    spoil_snapshot(session, run.name, "{not json")
    spoilt = state.get_run(session, run.name)
    acting, problem = runs.acting_or_problem(spoilt)
    assert acting == ""  # an active run's actor is its state's agent, named only in its flow
    assert isinstance(problem, runs.SnapshotError)
    assert str(problem).startswith('run "feature/x": its flow snapshot is not JSON')
    waiting = dataclasses.replace(spoilt, status=state.WAITING)
    assert runs.acting_or_problem(waiting) == (runs.HUMAN, None)
    closed = dataclasses.replace(spoilt, status=state.CANCELLED)
    assert runs.acting_or_problem(closed) == ("", None)


def test_where_a_run_whose_flow_cannot_be_read_is_now(session):
    run = runs.start(session, "feature", "Add x", name="x")
    spoil_snapshot(session, run.name, '{"name": "feature", "start": "design", "states": {}}')
    now = runs.now(state.get_run(session, run.name))
    # One line, for lado ls, though the validator gives one error per line.
    assert now == (
        "its flow cannot be read: snapshot: description is missing; "
        "snapshot: states must map state names to states"
    )


def test_a_run_whose_flow_cannot_be_read_is_only_cancelled(session):
    run = to_implement(session)
    runs.spawn_worker(session, run.name)
    spoil_snapshot(session, run.name, "{not json")
    for move in (
        lambda: runs.advance(session, "developer", run.name, "done"),
        lambda: runs.force(session, run.name, "review", "by hand"),
    ):
        with pytest.raises(runs.SnapshotError, match="its flow snapshot is not JSON"):
            move()
    assert state.get_run(session, run.name).state == "implement"
    [finished] = runs.cancel(session, run.name, "broken")
    assert finished.worker.name == "developer"
    cancelled = state.get_run(session, run.name)
    assert (cancelled.status, cancelled.reason) == (state.CANCELLED, "broken")


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
        runs.start(session, "feature", "x", language="r" * (runs.LANGUAGE_LIMIT + 1))
    assert state.list_runs(session) == []


@pytest.mark.parametrize(
    ("language", "named"),
    [
        ("ru\nen", "U+000A"),
        ("ru\N{RIGHT-TO-LEFT OVERRIDE}", "U+202E RIGHT-TO-LEFT OVERRIDE"),
        ("r\N{ZERO WIDTH SPACE}u", "U+200B ZERO WIDTH SPACE"),
    ],
)
def test_a_language_with_a_hidden_character_is_refused(session, language, named):
    reason = f"human_language is one line of visible text: {named} is not allowed"
    with pytest.raises(runtime.LadoError, match=f"^{re.escape(reason)}$"):
        runs.start(session, "feature", "x", language=language)
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


def test_a_run_worker_that_ended_by_itself_is_finished_and_its_step_given_to_another(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    runtime.agent_ended(session, "developer", "its CLI exited")
    assert messages("supervisor")[-1].summary == (
        'developer stopped (its CLI exited): end it with finish_worker(name="developer"), '
        'then spawn_worker(run="feature/login")'
    )
    # The way out works: the run keeps its worktree, and its step gets a new developer.
    runtime.finish_worker(session, "developer")
    assert runs.spawn_worker(session, "feature/login").name == "developer"
    assert "Build it." in state.get_agent(session, "developer").task


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
    first = first_input("developer")
    assert first.startswith("Run feature/login (flow feature), step implement.")
    assert "Build it." in first
    assert "Note from the previous step: design agreed\na\nb" in first
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


def test_a_spawn_refused_for_the_login_leaves_the_step_waiting(session, fake_tmux, cli_logins):
    run = to_implement(session)
    cli_logins.logged_out()
    with pytest.raises(runtime.NotLoggedIn, match="so the worker was not started"):
        runs.spawn_worker(session, "feature/login")
    assert state.get_agent(session, "developer") is None
    assert runs.acting(state.get_run(session, "feature/login")) == "developer (not spawned)"
    assert messages("developer") == []
    ask = messages("supervisor")[-1]
    assert (ask.summary, ask.state) == (
        "flow feature/login: step implement needs a developer",
        state.PENDING,
    )
    assert Path(run.worktree).exists()  # the run's own, kept for its next worker
    worker = runs.spawn_worker(session, "feature/login", provider="kilo")
    assert worker.provider == "kilo"
    assert runs.acting(state.get_run(session, "feature/login")) == "developer"


def advance_to_review(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait for the review.")
    return runs.advance(session, "developer", "feature/login", "done", "built")


def test_a_step_gets_the_previous_steps_note_after_the_step(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    step = state.get_agent(session, "developer").task
    assert step.count("design agreed") == 1
    assert "Note from the previous step: design agreed\na\nb" in step
    assert step.index("Build it.") < step.index("Note from the previous step")


def test_flow_set_gives_its_reason_as_the_previous_steps_note(session):
    advance_to_review(session)
    runs.force(session, "feature/login", "implement", "rework the form")
    step = messages("developer")[-1]
    assert step.summary == "flow feature/login: step implement"
    assert "Note from the previous step: set by the human: rework the form" in step.body
    assert "built" not in step.body


def test_a_loop_limit_answer_or_flow_set_is_kept_as_an_override(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again", "first look")
    runs.advance(session, "reviewer", "feature/login", "again", "second look")
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "continue", "one more")
    runs.advance(session, "reviewer", "feature/login", "again", "third look")
    runs.force(session, "feature/login", "implement", "enough looking")  # from the loop gate
    assert [(n.state, n.kind, n.summary) for n in state.run_notes(session)][-4:] == [
        ("review", state.REPORT, "second look"),
        ("review", state.OVERRIDE, "continue: one more"),
        ("review", state.REPORT, "third look"),
        ("review", state.OVERRIDE, "set by the human: enough looking"),
    ]


def test_a_gate_answer_is_kept_as_the_gates_note(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "reject", "the form is too big")
    *_, merge, gated = state.run_notes(session, "feature/login")
    assert (gated.state, gated.summary) == ("gated", "rejected: the form is too big")
    assert (merge.state, merge.summary) == ("merge", "ready to ship")
    step = messages("developer")[-1]
    assert step.summary == "flow feature/login: step implement"
    assert "Note from the previous step: rejected: the form is too big" in step.body


def test_a_worker_step_goes_to_the_next_worker_only(session):
    run = advance_to_review(session)
    assert run.state == "review"
    task, step = messages("reviewer")
    assert task.summary == "your task"  # given at its spawn
    assert (step.sender, step.summary) == ("lado", "flow feature/login: step review")
    assert "Note from the previous step: built" in step.body
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
    runtime.spawn_worker(session, "task", role="developer")
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
    assert len(messages("reviewer")) == 3  # its task, then the step twice


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
    assert told.summary == f"recommend on gate #{gate.id}: feature/login at review"
    assert "Only the human answers it." in told.body
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
        f"recommend on gate #{gate.id}: feature/login at gated"
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
        f"recommend on gate #{gate.id}: feature/login at gated"
    )
    assert runs.describe(run)["gate"] == {
        "id": gate.id,
        "question": "Ship it?",
        "options": ["approve", "reject"],
    }


def test_a_gate_keeps_the_id_of_the_note_that_led_to_it(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    note = state.last_note(session, "feature/login")
    assert (gate.note_id, note.summary, note.state) == (note.id, "ready to ship", "merge")


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


def _answer_files(gate_id: int) -> list[str]:
    return [a.artifact.full_name for a in runs.gate_answer_attachments(state.get_gate(gate_id))]


def test_a_gates_answer_gives_its_files_to_the_next_steps_note(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    shot = artifacts.upload(session, "shot.png", b"png").full_name
    log = artifacts.upload(session, "server.log", b"boom").full_name
    run = runs.answer(session, str(gate.id), "reject", "the form is too big", attached=[shot, log])
    assert run.note == "rejected: the form is too big"
    step = messages("developer")[-1]
    assert "Note from the previous step: rejected: the form is too big" in step.body
    assert f"Artifacts: /{shot}, /{log}" in step.body
    closed = state.get_gate(gate.id)
    assert closed.answer_note == state.last_note(session, "feature/login").id
    assert _answer_files(gate.id) == [shot, log]


def test_a_gate_answered_with_files_only_has_the_outcome_as_its_note(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    log = artifacts.upload(session, "server.log", b"boom").full_name
    assert runs.answer_text(session, str(gate.id), "reject", attached=[log]) == (
        f"gate #{gate.id}: reject. feature/login: gated -> implement (→ developer)"
    )
    run = state.get_run(session, "feature/login")
    assert (run.note, run.note_body) == ("rejected", "Note before the gate: ready to ship\na\nb")
    assert f"Artifacts: /{log}" in messages("developer")[-1].body
    assert _answer_files(gate.id) == [log]


def test_a_gate_answer_without_files_keeps_none(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "reject", "too big")
    assert state.get_gate(gate.id).answer_note is not None
    assert _answer_files(gate.id) == []
    assert "Artifacts:" not in messages("developer")[-1].body


@pytest.mark.parametrize(
    ("names", "error", "reason"),
    [
        (["nope.txt"], artifacts.ArtifactError, 'no artifact "nope.txt" in session s'),
        ([f"{n}.txt" for n in range(11)], runtime.LadoError, "11 files, the limit is 10"),
    ],
    ids=["missing", "eleven"],
)
def test_a_gates_answer_with_files_it_cannot_take_leaves_it_open(session, names, error, reason):
    to_gate(session)
    [gate] = state.open_gates(session)
    if len(names) > 1:
        names = [artifacts.upload(session, n, n.encode()).full_name for n in names]
    before = state.get_run(session, "feature/login")
    with pytest.raises(error, match=f"^{re.escape(reason)}$"):
        runs.answer(session, str(gate.id), "reject", "x", attached=names)
    assert state.get_run(session, "feature/login") == before
    assert state.get_gate(gate.id).answer is None


def test_cancel_at_a_loop_limit_sends_the_files_to_the_supervisor(session):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    log = artifacts.upload(session, "server.log", b"boom").full_name
    runs.answer(session, str(gate.id), "cancel", "not worth it", attached=[log])
    told = messages("supervisor")[-1]
    assert told.summary == "flow feature/login: cancelled by the human at review (loop limit)"
    assert [
        a.artifact.full_name for a in artifacts.attached(state.message_attachments(told.id))
    ] == [log]
    assert state.get_gate(gate.id).answer_note is None


def test_a_gate_closed_by_a_cancel_has_no_answer_files(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.cancel(session, "feature/login", "dropped")
    closed = state.get_gate(gate.id)
    assert (closed.answer, closed.answer_note) == ("cancelled", None)
    assert runs.gate_answer_attachments(closed) == []


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
        "recommend on gate #1: pick/x at which",
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


def closing_event(session, gate_id):
    """The run's event the gate keeps as the one that closed it."""
    gate = state.get_gate(gate_id)
    [event] = [e for e in state.list_events(session) if e.id == gate.closed_event]
    assert event.run == gate.run
    return event.agent, event.kind, event.detail


@pytest.mark.parametrize(
    ("option", "detail"),
    [("approve", "gated -approved-> done"), ("reject", "gated -rejected-> implement")],
)
def test_a_gate_keeps_the_move_its_answer_made(session, option, detail):
    to_gate(session)
    [gate] = state.open_gates(session)
    assert gate.closed_event is None
    runs.answer(session, str(gate.id), option, "a comment")
    assert closing_event(session, gate.id) == ("human", state.FLOW, detail)


def test_a_choice_gate_keeps_the_move_of_its_choice(session, team):
    flow = FEATURE.replace(
        "gate: approval\n    ask: Ship it?\n    outcomes: {approved: done, rejected: implement}",
        "gate: choice\n    ask: Where to?\n    outcomes: {ship: done, rework: implement}",
    ).replace("{merged: done}", "{merged: done, hold: gated}")
    write(team / "flows" / "feature.yaml", flow)
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "rework")
    assert closing_event(session, gate.id) == ("human", state.FLOW, "gated -rework-> implement")


@pytest.mark.parametrize(
    ("option", "kind", "detail"),
    [
        ("continue", state.FLOW, "review -continue-> review"),
        ("cancel", state.FLOW_CANCEL, "loop limit: enough"),
    ],
)
def test_a_loop_limit_keeps_the_event_of_its_answer(session, option, kind, detail):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), option, "enough")
    assert closing_event(session, gate.id) == ("human", kind, detail)


def test_a_gate_closed_by_flow_set_or_a_cancel_keeps_that_event(session):
    to_gate(session)
    runs.force(session, "feature/login", "implement", "rework the form")
    assert closing_event(session, 1) == (
        "human",
        state.FLOW_SET,
        "gated -> implement: rework the form",
    )
    runs.force(session, "feature/login", "gated", "hold it")
    [gate] = state.open_gates(session)
    runs.cancel(session, "feature/login", "dropped")
    assert closing_event(session, gate.id) == ("supervisor", state.FLOW_CANCEL, "dropped")


def test_a_gate_state_answered_twice_keeps_each_gates_own_move(session):
    to_gate(session)
    runs.answer(session, "1", "reject", "first")
    runs.force(session, "feature/login", "gated", "again")
    [second] = state.open_gates(session)
    runs.answer(session, str(second.id), "approve", "second")
    first, again = state.session_gates(session)
    assert closing_event(session, first.id)[2] == "gated -rejected-> implement"
    assert closing_event(session, again.id)[2] == "gated -approved-> done"
    assert first.closed_event < again.closed_event


def test_two_runs_closing_their_gates_in_turn_keep_their_own_events(session):
    to_gate(session)
    runs.start(session, "feature", "Add y", name="y")
    runs.force(session, "feature/y", "gated", "hold y")
    login, y = state.open_gates(session)
    runs.answer(session, str(y.id), "reject")
    runs.answer(session, str(login.id), "approve")
    assert closing_event(session, y.id)[2] == "gated -rejected-> implement"
    assert closing_event(session, login.id)[2] == "gated -approved-> done"


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


def test_end_removes_a_merged_branch_whose_upstream_is_behind(session, repo, fake_tmux):
    # git branch -d checks a branch with an upstream against it, not against HEAD.
    run = to_merge(session)
    commit(run, "one.txt")
    origin = repo.parent / "origin.git"
    runtime.git(str(repo), "init", "-q", "--bare", str(origin))
    runtime.git(str(repo), "remote", "add", "origin", str(origin))
    runtime.git(run.worktree, "push", "-q", "-u", "origin", run.branch)
    commit(run, "two.txt")
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    notices = []
    run = runs.advance(session, "supervisor", "feature/login", "merged", notices=notices)
    assert (run.state, run.status) == ("done", state.ENDED)
    assert notices == ["flow feature/login: ended at done; worktree and branch removed"]
    assert [a.name for a in state.list_agents(session)] == ["supervisor"]
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""


@pytest.mark.parametrize("gone", ["worktree", "branch", "both"])
def test_end_closes_the_workers_when_the_worktree_or_branch_is_gone(session, repo, fake_tmux, gone):
    run = to_merge(session)
    commit(run)
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    if gone in ("worktree", "both"):
        shutil.rmtree(run.worktree)  # by hand: git still has it as a worktree
    if gone == "branch":
        runtime.git(run.worktree, "checkout", "-q", "--detach")
    if gone in ("branch", "both"):
        runtime.git(str(repo), "worktree", "prune")
        runtime.git(str(repo), "branch", "-D", run.branch)
    notices = []
    run = runs.advance(session, "supervisor", "feature/login", "merged", notices=notices)
    assert run.status == state.ENDED
    assert [a.name for a in state.list_agents(session)] == ["supervisor"]
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    body = {
        "worktree": f"Removed: branch {run.branch}. Already gone: worktree {run.worktree}.",
        "branch": f"Removed: worktree {run.worktree}. Already gone: branch {run.branch}.",
        "both": f"Already gone: worktree {run.worktree}, branch {run.branch}.",
    }[gone]
    assert notices == [f"flow feature/login: ended at done; worktree and branch gone\n{body}"]


def test_end_keeps_a_run_whose_branch_is_gone_with_unmerged_commits(session, repo):
    run = to_merge(session)
    commit(run)
    runtime.git(run.worktree, "checkout", "-q", "--detach")
    runtime.git(str(repo), "branch", "-D", run.branch)
    runs.advance(session, "supervisor", "feature/login", "merged")
    told = messages("supervisor")[-1]
    assert told.summary == "flow feature/login: ended at done; kept its worktree and branch"
    assert (
        f"Branch {run.branch} is gone, but its worktree holds commits not merged into main."
        in told.body
    )
    assert Path(run.worktree).exists()
    assert [a.name for a in state.list_agents(session)] == ["supervisor", "developer", "reviewer"]


def test_end_keeps_a_run_whose_branch_is_gone_with_uncommitted_changes(session, repo):
    run = to_merge(session)
    runtime.git(run.worktree, "checkout", "-q", "--detach")
    runtime.git(str(repo), "branch", "-D", run.branch)
    Path(run.worktree, "draft.txt").write_text("x")
    runs.advance(session, "supervisor", "feature/login", "merged")
    assert "has uncommitted changes" in messages("supervisor")[-1].body
    assert Path(run.worktree, "draft.txt").exists()
    assert [a.name for a in state.list_agents(session)] == ["supervisor", "developer", "reviewer"]


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


def test_finish_preview_of_a_run_worker_says_what_finishing_it_would_do(session, repo):
    run = advance_to_review(session)
    commit(run)
    # An open run keeps its worktree: finishing a worker only closes its window.
    preview = runtime.finish_preview(session, "developer")
    assert (preview.removes_worktree, preview.refused) == (False, None)
    assert (preview.work.branch, preview.work.ahead) == (run.branch, 1)
    run = runs.advance(session, "reviewer", "feature/login", "approved")
    run = runs.advance(session, "supervisor", "feature/login", "merged")
    assert run.status == state.ENDED
    # Ended, the other worker still there: still only the window.
    assert runtime.finish_preview(session, "developer").removes_worktree is False
    runtime.finish_worker(session, "developer")
    # The last worker of an ended run takes the worktree, and is refused while unmerged.
    preview = runtime.finish_preview(session, "reviewer")
    assert preview.removes_worktree is True
    assert preview.refused.startswith(f"branch {run.branch} is not merged into main")
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    preview = runtime.finish_preview(session, "reviewer")
    assert (preview.removes_worktree, preview.refused, preview.work.ahead) == (True, None, 0)


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
        "closed; discard does not apply: the run keeps its worktree; 2 messages dropped"
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


def test_status_shows_a_run_whose_flow_cannot_be_read_with_its_problem(session):
    to_gate(session)  # feature/login, waiting at the gate
    runs.start(session, "feature", "other", name="other")
    runs.start(session, "feature", "fine", name="fine")
    for name in ("feature/login", "feature/other"):
        spoil_snapshot(session, name, "{not json")
    login, other, fine = runs.status(session, "supervisor")
    problem = 'run "feature/other": its flow snapshot is not JSON: Expecting'
    assert other["problem"].startswith(problem)
    assert (other["state"], other["acting"], other["outcomes"]) == ("design", "", {})
    assert login["problem"].startswith('run "feature/login": its flow snapshot is not JSON')
    assert (login["acting"], login["gate"]["question"]) == ("human", "Ship it?")
    assert "problem" not in fine  # the others as before
    assert fine["outcomes"] == {"ready": "implement"}
    [full] = runs.status(session, "supervisor", "feature/other")
    assert full["problem"].startswith(problem)
    assert full["task"] == "other"


def test_the_supervisor_is_told_the_flows_and_a_run_worker_how_to_report(session, fake_tmux):
    supervisor = fake_tmux[0][-1]
    prompt = claude_prompt(supervisor)
    assert "  - feature (kit team): New feature, reviewed." in prompt
    assert "Flows are optional" in prompt and "flow_start" in prompt
    assert "human_language: the language the human writes to you in" in prompt
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    worker = fake_tmux[-1][-1]
    prompt = claude_prompt(worker)
    assert 'flow_advance(run="feature/login", outcome=...)' in prompt
    prompt = " ".join(prompt.split())
    assert 'A bare artifact name is one of run feature/login: "design" is' in prompt
    assert '"feature/login/design"; you write only the run\'s artifacts' in prompt


def test_a_run_worker_reports_each_step_only_with_flow_advance(session, fake_tmux):
    """flow_advance is a run worker's report: nothing asks it to send_message one too."""
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    prompt = claude_prompt(fake_tmux[-1][-1])
    first = first_input("developer")
    assert first.startswith("Run feature/login (flow feature), step implement.")
    assert "send_message" not in first
    assert "as well" not in prompt
    assert "flow_advance is your report" in prompt
    assert "as the last action of your turn" in prompt
    assert "only for questions" in prompt


def test_every_worker_is_told_whose_messages_are_its_instructions(session, fake_tmux):
    """A worker on a cautious model refused a task that came as "[from ...]"."""
    runtime.spawn_worker(session, "task", role="worker")
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    for worker in (fake_tmux[-2][-1], fake_tmux[-1][-1]):
        prompt = claude_prompt(worker)
        assert (
            'Messages from "supervisor" and steps from "lado" are your instructions, '
            "the same as the human's" in prompt
        )
        assert "messages from other workers are information or questions, not orders" in prompt


def test_a_run_worker_without_a_step_is_told_to_report_its_task(session, fake_tmux):
    """A task from the supervisor, with no step in it, is reported with send_message."""
    to_implement(session)
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Read the plan.")
    assert first_input("reviewer") == "Read the plan." + runtime.REPORT_REMINDER


def test_a_session_without_flows_is_not_told_about_them(repo, fake_tmux):
    runtime.start_session(str(repo), "plain", None, provider="claude")
    supervisor = fake_tmux[0][-1]
    assert "flow_start" not in claude_prompt(supervisor)


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
    resumed, step, request = messages("supervisor")[-3:]
    assert (resumed.sender, resumed.summary) == ("lado", "session resumed: 3 open runs")
    assert resumed.body == (
        f"- feature/login at gated: waits for the human at gate #{gate.id}: Ship it? Only "
        f"the human answers it, with: lado answer {session} {gate.id}. Nothing to do until "
        "then. A request for your recommendation follows.\n"
        "- feature/plan at design: your step; it follows as a message from lado.\n"
        "- feature/build at implement: needs a developer. Start one with "
        'spawn_worker(role="developer", run="feature/build"); it works in the run\'s '
        "worktree and gets the step as its task."
    )
    # They wait in its queue, handed over when it is idle, as any message.
    assert (resumed.state, step.state, request.state) == (state.PENDING,) * 3
    assert step.summary == "flow feature/plan: step design"
    assert request.summary == f"recommend on gate #{gate.id}: feature/login at gated"
    assert "Design it with the human." in step.body
    # None of it is on its command line, which `ps` shows to every user of the machine.
    assert fake_tmux[-1][0] == "new_session"
    assert not [a for a in fake_tmux[-1][-1] if "session resumed" in a or "Design it" in a]
    assert state.get_agent(session, "supervisor").task is None


def test_a_step_far_longer_than_a_tmux_command_comes_through_the_queue(session, fake_tmux):
    runs.start(session, "feature", "Add a login page", name="login")
    plan = "x" * 50_000
    runs.advance(session, "supervisor", "feature/login", "ready", "agreed", plan)
    worker = runs.spawn_worker(session, "feature/login")
    _, _, window, cwd, argv = fake_tmux[-1]
    assert window == "developer"
    assert not [a for a in argv if "xxx" in a or "login page" in a]
    [step] = messages("developer")
    assert (step.sender, step.summary, step.state) == (
        "lado",
        "flow feature/login: step implement",
        state.PENDING,  # handed over when the worker is idle
    )
    assert plan in step.body
    assert f"Note from the previous step: agreed\n{plan}" in step.body
    assert step.body.count(plan) == 1
    assert worker.task == step.body  # the task in full: lado ls, list_agents


@pytest.mark.parametrize("kit_names", [["solo"], ["default", "solo"]])
def test_a_step_of_a_kits_supervisor_is_the_sessions_lead(repo, fake_tmux, kit_names):
    """Kit solo's supervisor is named lead; it leads alone, or LADO's built-in one leads."""
    kit = repo.parent / "kits" / "solo"
    write(kit / "kit.yaml", "name: solo\nversion: 1.0.0\nsupervisor: lead\n")
    install_kit(kit)
    for role in ("lead", "developer", "reviewer"):
        write(kit / "agents" / f"{role}.md", f"---\nname: {role}\ndescription: d\n---\nx\n")
    flow = FEATURE.replace("agent: supervisor", "agent: lead")
    write(kit / "flows" / "feature.yaml", flow.replace("{merged: done}", "{merged: gated}"))
    runtime.start_session(str(repo), "s", None, kit_names=kit_names, provider="claude")
    run = runs.start("s", "feature", "Plan it", name="plan")
    assert runs.acting(run) == "supervisor"
    step = messages("supervisor")[-1]
    assert step.summary == "flow feature/plan: step design"
    with pytest.raises(runtime.LadoError, match="has no step for a lead now"):
        runs.spawn_worker("s", run.name, role="lead")
    started = restart("s", repo)
    assert started.problems == []
    resumed = messages("supervisor")[-2]
    assert "- feature/plan at design: your step; it follows as a message from lado." in (
        resumed.body
    )
    runs.advance("s", "supervisor", run.name, "ready")
    assert runs.acting(state.get_run("s", run.name)) == "developer (not spawned)"


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


def test_resume_reports_runs_whose_flow_cannot_be_read_and_resumes_the_others(
    session, repo, fake_tmux
):
    to_gate(session)  # feature/login, waiting at the gate
    runs.start(session, "feature", "Plan it", name="plan")  # the supervisor's step
    runs.start(session, "feature", "Build it", name="build")
    for name in ("feature/login", "feature/build"):
        spoil_snapshot(session, name, "{not json")
    why = "its flow snapshot is not JSON: Expecting property name enclosed in double quotes"
    started = restart(session, repo)
    assert [p.split(": ", 1)[0] for p in started.problems] == [
        "run feature/login",
        "run feature/build",
    ]
    for problem in started.problems:
        assert why in problem
        assert problem.endswith("; it cannot go on: cancel the run with flow_cancel")
    resumed, step = messages("supervisor")[-2:]
    assert resumed.summary == "session resumed: 3 open runs"
    login, plan, build = resumed.body.splitlines()
    assert login.startswith(f"- feature/login at gated: {why}")
    assert login.endswith("; it cannot go on: cancel the run with flow_cancel.")
    assert plan == "- feature/plan at design: your step; it follows as a message from lado."
    assert build.startswith(f"- feature/build at design: {why}")
    assert step.summary == "flow feature/plan: step design"


def test_a_worker_after_resume_takes_over_the_runs_worktree(session, repo, fake_tmux):
    run = to_implement(session)
    runs.spawn_worker(session, "feature/login")
    commit(run)
    restart(session, repo)
    worker = runs.spawn_worker(session, "feature/login")
    assert (worker.name, worker.cwd, worker.branch) == ("developer", run.worktree, run.branch)
    assert Path(run.worktree, "login.txt").exists()
    step = messages("developer")[-1]
    assert step.body.startswith("Run feature/login (flow feature), step implement.")
    assert step.state == state.PENDING


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
    # The stop marks the recommendation the lead did not give; nothing else changed.
    stopped_gate = state.open_gate(session, "feature/login")
    assert stopped_gate.recommendation_state == state.REC_MISSING
    assert dataclasses.replace(stopped_gate, recommendation_state=state.REC_ASKED) == gate
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
    worker = runtime.spawn_worker(session, "task", name="w1", role="worker")
    runtime.send_message(session, "supervisor", "w1", "hi")  # w1 is starting: queued
    preview = runtime.stop_preview(session)
    assert preview.agents == ["supervisor", "w1"]
    # And w1's task, and the run's first step, to the starting supervisor.
    assert preview.dropped == 3
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


def steps(session):
    """Each kept note as (state, kind, actor, outcome, target, summary)."""
    return [
        (n.state, n.kind, n.actor, n.outcome, n.target, n.summary)
        for n in state.run_notes(session, "feature/login")
    ]


def test_each_advance_keeps_its_step_who_reported_the_outcome_and_where_it_leads(session):
    advance_to_review(session)
    assert steps(session) == [
        ("design", state.REPORT, "supervisor", "ready", "implement", "design agreed"),
        ("implement", state.REPORT, "developer", "done", "review", "built"),
    ]


def test_a_gate_answer_is_a_step_of_the_human(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "approve", "ship it")
    assert steps(session)[-1] == (
        "gated",
        state.REPORT,
        "human",
        "approved",
        "done",
        "approved: ship it",
    )


def test_a_choice_gate_answer_keeps_the_chosen_outcome(session, team):
    flow = FEATURE.replace(
        "gate: approval\n    ask: Ship it?\n    outcomes: {approved: done, rejected: implement}",
        "gate: choice\n    ask: Where to?\n    outcomes: {ship: done, rework: implement}",
    ).replace("{merged: done}", "{merged: done, hold: gated}")
    write(team / "flows" / "feature.yaml", flow)
    to_gate(session)
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "rework")
    assert steps(session)[-1][:5] == ("gated", state.REPORT, "human", "rework", "implement")


def test_a_step_into_a_loop_limit_names_the_state_it_was_kept_out_of(session):
    advance_to_review(session)
    runs.advance(session, "reviewer", "feature/login", "again", "first look")
    runs.advance(session, "reviewer", "feature/login", "again", "second look")
    [gate] = state.open_gates(session)
    runs.answer(session, str(gate.id), "continue", "one more")
    assert steps(session)[-2:] == [
        ("review", state.REPORT, "reviewer", "again", "review", "second look"),
        ("review", state.OVERRIDE, "human", "continue", "review", "continue: one more"),
    ]


def test_flow_set_is_a_step_of_the_human_with_no_outcome(session):
    advance_to_review(session)
    runs.force(session, "feature/login", "implement", "rework the form")
    assert steps(session)[-1] == (
        "review",
        state.OVERRIDE,
        "human",
        "",
        "implement",
        "set by the human: rework the form",
    )


@pytest.fixture
def read_only_lead(repo, fake_tmux):
    """Session s led by kit watch's read-only supervisor, with the feature flow."""
    kit = repo.parent / "kits" / "watch"
    write(kit / "kit.yaml", "name: watch\nversion: 1.0.0\nsupervisor: lead\n")
    install_kit(kit)
    write(kit / "agents" / "lead.md", "---\nname: lead\ndescription: d\nread_only: true\n---\nx\n")
    for role in ("developer", "reviewer"):
        write(kit / "agents" / f"{role}.md", f"---\nname: {role}\ndescription: d\n---\nx\n")
    flow = FEATURE.replace("agent: supervisor", "agent: lead")
    write(
        kit / "flows" / "feature.yaml",
        flow.replace("{merged: done}", "{merged: done, hold: gated}"),
    )
    runtime.start_session(str(repo), "s", None, kit_names=["watch"], provider="claude")
    assert state.get_agent("s", "supervisor").read_only
    return "s"


COMMANDS = ("spawn_worker", "finish_worker", "flow_cancel", "flow_start", "Merge the branch")


def orders_nothing(text):
    return not [c for c in COMMANDS if c in text]


WAITS_FOR_A_DEVELOPER = (
    "Your role is read-only: you cannot start a worker. The run waits at implement until "
    "the human moves it on with `lado flow-set s feature/login <state> --reason ...`; "
    "`lado stop s` halts the session, and the run stays open."
)


def test_a_read_only_lead_is_told_that_the_step_waits_for_the_human(read_only_lead):
    run = to_implement(read_only_lead)
    ask = messages("supervisor")[-1]
    # The same line as for any lead: a worker spawned for the step drops it.
    assert ask.summary == "flow feature/login: step implement needs a developer"
    assert ask.body == WAITS_FOR_A_DEVELOPER
    runs.spawn_worker(read_only_lead, run.name)
    assert messages("supervisor")[-1].state == state.DROPPED


def test_a_read_only_leads_own_advance_gets_the_same_text_as_a_notice(read_only_lead):
    runs.start(read_only_lead, "feature", "Add a login page", name="login")
    notices = []
    runs.advance(read_only_lead, "supervisor", "feature/login", "ready", notices=notices)
    assert notices == [
        f"flow feature/login: step implement needs a developer\n{WAITS_FOR_A_DEVELOPER}"
    ]


def test_a_read_only_lead_is_told_the_humans_way_to_merge_and_finish(read_only_lead, repo):
    run = to_merge(read_only_lead)
    commit(run)
    runs.advance(read_only_lead, "supervisor", "feature/login", "merged")
    told = messages("supervisor")[-1]
    assert told.summary == "flow feature/login: ended at done; kept its worktree and branch"
    assert orders_nothing(told.body)
    assert told.body.endswith(
        "Your role is read-only: you cannot merge the branch or finish the workers. The "
        f"human does: `git merge {run.branch}` in {repo}, then `lado finish s <worker>` for "
        "each worker: the last one removes the worktree and branch (with no workers left, "
        "remove them with git)."
    )
    assert "workers: developer, reviewer" in told.body
    # The way works: merged, the last worker finished takes the worktree and branch.
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    runtime.finish_worker(read_only_lead, "developer")
    assert runtime.finish_worker(read_only_lead, "reviewer").how == "merged"
    assert not Path(run.worktree).exists()


def test_a_read_only_lead_is_told_the_human_ends_a_stopped_worker(read_only_lead):
    to_implement(read_only_lead)
    runs.spawn_worker(read_only_lead, "feature/login")
    runtime.agent_ended(read_only_lead, "developer", "its CLI exited")
    told = messages("supervisor")[-1]
    assert told.summary == (
        "developer stopped (its CLI exited): the human ends it with `lado finish s developer`"
    )
    assert orders_nothing(told.summary + told.body)
    assert told.body == (
        "Your role is read-only: you cannot end it. Once it is ended, run feature/login "
        "waits for a worker until the human moves it on with `lado flow-set s feature/login "
        "<state> --reason ...`."
    )


def test_resume_tells_a_read_only_lead_what_waits_without_orders(read_only_lead, repo):
    runs.start(read_only_lead, "feature", "Build it", name="build")
    runs.advance(read_only_lead, "supervisor", "feature/build", "ready")  # needs a developer
    runs.start(read_only_lead, "feature", "Bad", name="bad")
    spoil_snapshot(read_only_lead, "feature/bad", "{not json")
    started = restart(read_only_lead, repo, without=["agent:reviewer"])
    resumed = messages("supervisor")[-1]
    assert resumed.summary == "session resumed: 2 open runs"
    assert orders_nothing(resumed.body)
    assert orders_nothing("\n".join(started.problems))
    build, gone, bad = resumed.body.splitlines()
    assert build == (
        "- feature/build at implement: needs a developer. Your role is read-only: you cannot "
        "start a worker. The run waits at implement until the human moves it on with "
        "`lado flow-set s feature/build <state> --reason ...`; `lado stop s` halts the "
        "session, and the run stays open."
    )
    assert gone == (
        "  Role reviewer is not in the session now; the human moves the run on with lado flow-set."
    )
    assert bad.endswith(
        "; it cannot go on: neither you (read-only) nor lado flow-set can move it; "
        "`lado stop s` halts the session, and the run stays open."
    )


# The lead's recommendation on each gate.

SHIP = """\
name: ship
description: Built, then shipped by the human.
start: build
states:
  build:
    agent: developer
    do: Build it.
    produces: [design]
    outcomes: {done: check}
  check:
    gate: approval
    ask: Ship it?
    reads: [design]
    outcomes: {approved: end, rejected: build}
  end:
    end: true
"""


@pytest.fixture
def shipping(session, team):
    """Run ship/x in step build, with its developer, which wrote the design."""
    write(team / "flows" / "ship.yaml", SHIP)
    runs.start(session, "ship", "Ship x", name="x")
    runs.spawn_worker(session, "ship/x")
    artifacts.write(session, "developer", "design", "the design", summary="v1", title="Design")
    return "ship/x"


def requests(session):
    return [m for m in messages("supervisor") if m.summary.startswith("recommend on ")]


def test_a_gate_asks_the_lead_for_a_recommendation(session, shipping):
    runs.advance(session, "developer", shipping, "done", "built it", "all green")
    [gate] = state.open_gates(session)
    [request] = requests(session)
    assert (request.sender, request.summary) == (
        "lado",
        f"recommend on gate #{gate.id}: ship/x at check",
    )
    assert request.body == (
        "Ship it?\n"
        "Options: approve, reject\n"
        "Note of developer at build: built it\n"
        "all green\n"
        f"Only the human answers it. Give your own view with recommend(gate={gate.id}, "
        "text=..., choice=..., disagrees=...): what you would choose and why, the risks, "
        "what to check; short, no retelling. Write no separate message to the human about it."
    )
    # The note's artifacts go with it; the gate reads no other.
    assert state.message_attachments(request.id) == state.note_attachments(gate.note_id)
    assert len(state.message_attachments(request.id)) == 1
    assert not [m for m in messages("supervisor") if "waiting for the human at" in m.summary]
    stored = state.get_gate(gate.id)
    assert (stored.recommendation_state, stored.recommendation_request) == (
        state.REC_ASKED,
        request.id,
    )


def test_a_gate_entered_by_flow_set_names_what_it_reads(session, shipping):
    runs.force(session, shipping, "check", "ready")
    [gate] = state.open_gates(session)
    [request] = requests(session)
    assert "Note of human at build: set by the human: ready\n" in request.body
    assert "Artifacts it reads:\n- ship/x/design: Design — v1\n" in request.body


def test_a_loop_limit_asks_too(session):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    [request] = requests(session)
    assert request.summary == f"recommend on gate #{gate.id}: feature/login at review"
    assert "Options: continue, cancel\n" in request.body
    assert state.get_gate(gate.id).recommendation_state == state.REC_ASKED


def test_the_leads_own_advance_gets_the_request_as_a_notice(session):
    to_merge(session)
    notices = []
    runs.advance(session, "supervisor", "feature/login", "hold", "ready", notices=notices)
    [gate] = state.open_gates(session)
    [notice] = notices
    assert notice.startswith(
        f"flow feature/login: recommend on gate #{gate.id}: feature/login at gated\nShip it?\n"
    )
    assert f"recommend(gate={gate.id}," in notice
    assert requests(session) == []
    stored = state.get_gate(gate.id)
    assert (stored.recommendation_state, stored.recommendation_request) == (state.REC_ASKED, None)


def test_a_gate_opens_when_the_lead_does_not_run(session, shipping, fake_tmux):
    state.set_status(session, "supervisor", state.STOPPED)
    run = runs.advance(session, "developer", shipping, "done", "built it")
    assert run.status == state.WAITING
    [gate] = state.open_gates(session)
    assert gate.recommendation_state is None
    assert requests(session) == []
    assert [c for c in fake_tmux if c[0] == "popup"]


def test_a_resume_asks_again_for_gates_without_a_given_recommendation(session, repo, team):
    to_gate(session)  # feature/login at gated: the lead's own move, asked by a message
    write(team / "flows" / "ship.yaml", SHIP)
    runs.start(session, "ship", "Ship x", name="x")
    runs.force(session, "ship/x", "check", "ready")
    given = state.open_gate(session, "ship/x")
    runtime.recommend(session, "supervisor", "Ship it", gate=given.id, choice="approve")
    missed = state.open_gate(session, "feature/login")
    restart(session, repo)
    resumed = next(m for m in messages("supervisor") if m.summary.startswith("session resumed"))
    assert (
        f"waits for the human at gate #{missed.id}: Ship it? Only the human answers it, with: "
        f"lado answer {session} {missed.id}. Nothing to do until then. A request for your "
        "recommendation follows."
    ) in resumed.body
    [given_line] = [line for line in resumed.body.splitlines() if f"gate #{given.id}:" in line]
    assert given_line.endswith("Nothing to do until then.")
    asked = [m for m in requests(session) if m.id > resumed.id]
    assert [m.summary for m in asked] == [f"recommend on gate #{missed.id}: feature/login at gated"]
    assert asked[0].state == state.PENDING
    assert state.get_gate(missed.id).recommendation_state == state.REC_ASKED
    assert state.get_gate(given.id).recommendation_state == state.REC_GIVEN


@pytest.mark.parametrize(
    ("note", "named"),
    [
        ("built\N{ZERO WIDTH SPACE}", "U+200B ZERO WIDTH SPACE"),
        ("built\nand tested", "U+000A"),
        ("built\N{RIGHT-TO-LEFT OVERRIDE}", "U+202E RIGHT-TO-LEFT OVERRIDE"),
    ],
)
def test_a_note_summary_with_a_hidden_character_is_refused(session, note, named):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    before = state.get_run(session, "feature/login")
    reason = (
        f"note_summary must be one line of visible text: {named} is not allowed; "
        "put the details in note_body"
    )
    with pytest.raises(runtime.LadoError, match=f"^{re.escape(reason)}$"):
        runs.advance(session, "developer", "feature/login", "done", note)
    assert state.get_run(session, "feature/login") == before


def test_a_gate_comment_is_cleaned_for_the_note_and_kept_in_its_body(session):
    to_gate(session)
    [gate] = state.open_gates(session)
    comment = "too\N{LINE SEPARATOR}big \N{RIGHT-TO-LEFT OVERRIDE}form"
    run = runs.answer(session, str(gate.id), "reject", comment)
    assert run.note == "rejected: too big form"
    assert run.note_body == f"{comment}\n\nNote before the gate: ready to ship\na\nb"


def test_a_flow_set_reason_is_cleaned_for_the_note_and_kept_in_its_body(session):
    advance_to_review(session)
    reason = "rework\N{ZERO WIDTH SPACE} the form"
    run = runs.force(session, "feature/login", "implement", reason)
    assert (run.note, run.note_body) == ("set by the human: rework the form", reason)
    long = "x" * 300
    run = runs.force(session, "feature/login", "review", long)
    assert (run.note, run.note_body) == (f"set by the human: {long}"[: runs.NOTE_LIMIT], long)
    run = runs.force(session, "feature/login", "implement", "plain")
    assert (run.note, run.note_body) == ("set by the human: plain", "")


def test_a_loop_limit_cancel_keeps_a_cleaned_reason(session):
    to_loop_limit(session)
    [gate] = state.open_gates(session)
    runs.answer(
        session,
        str(gate.id),
        "cancel",
        "not\N{PARAGRAPH SEPARATOR}worth\N{LEFT-TO-RIGHT ISOLATE} it",
    )
    run = state.get_run(session, "feature/login")
    assert run.reason == "loop limit: not worth it"
    assert (
        state.get_gate(gate.id).comment
        == "not\N{PARAGRAPH SEPARATOR}worth\N{LEFT-TO-RIGHT ISOLATE} it"
    )
