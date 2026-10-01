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
    assert "Note from the previous step: design agreed\na\nb" in first
    assert "- done -> review" in first
    assert runs.acting(state.get_run(session, "feature/login")) == "w1"
    # The step has its worker now: another one needs a task of its own.
    with pytest.raises(runtime.LadoError, match="has no step for a developer now"):
        runs.spawn_worker(session, "feature/login", role="developer")
    second = runs.spawn_worker(session, "feature/login", role="reviewer", task="Read the plan.")
    assert second.task == "Read the plan."


def advance_to_review(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")  # w1, developer
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait for the review.")
    return runs.advance(session, "w1", "feature/login", "done", "built")


def test_a_worker_step_goes_to_the_next_worker_only(session):
    run = advance_to_review(session)
    assert run.state == "review"
    [step] = messages("w2")
    assert (step.sender, step.summary) == ("lado", "flow feature/login: step review")
    assert "Note from the previous step: built" in step.body
    assert [m.summary for m in messages("supervisor")] == [
        "flow feature/login: step design",
        "flow feature/login: step implement needs a developer",
    ]


@pytest.mark.parametrize(
    ("caller", "outcome", "error"),
    [
        ("w1", "approved", 'step review of run "feature/login" is for the run\'s reviewer'),
        ("supervisor", "approved", "is for the run's reviewer"),
        ("w2", "lgtm", 'unknown outcome "lgtm" for step review; valid: approved, changes, again'),
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
        runs.advance(session, "w1", "feature/login", "ready")


def test_an_error_after_the_transition_says_the_run_moved_on(session):
    to_implement(session)
    runs.spawn_worker(session, "feature/login")  # w1, developer
    runs.spawn_worker(session, "feature/login", role="reviewer", task="Wait.")  # w2
    state.set_status(session, "w2", state.STOPPED)
    with pytest.raises(runtime.LadoError) as error:
        runs.advance(session, "w1", "feature/login", "done")
    assert str(error.value).startswith(
        'run "feature/login" moved on to review (active), but: no running agent "w2"'
    )
    assert state.get_run(session, "feature/login").state == "review"


def test_a_self_loop_enters_the_state_again(session):
    advance_to_review(session)
    run = runs.advance(session, "w2", "feature/login", "again")
    assert (run.state, run.visits["review"]) == ("review", 2)
    assert len(messages("w2")) == 2


def test_max_visits_stops_the_run_for_the_human(session):
    advance_to_review(session)
    runs.advance(session, "w2", "feature/login", "again")
    run = runs.advance(session, "w2", "feature/login", "again")
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
        runs.advance(session, "w2", "feature/login", "approved")


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
    assert messages("w1")[-1].summary == "flow feature/login: step implement"
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
    assert (where, title) == (session, f"lado {session}: waiting for you")
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
    step = messages("w1")[-1]
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
    runs.advance(session, "w2", "feature/login", "again")
    return runs.advance(session, "w2", "feature/login", "again", "still red")


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
    assert messages("w2")[-1].summary == "flow feature/login: step review"
    assert state.list_events(session)[-1].detail == "review -continue-> review"
    # The limit stops it again next time.
    run = runs.advance(session, "w2", "feature/login", "again")
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
    return runs.advance(session, "w2", "feature/login", "approved")


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
    assert ("kill_window", session, "w1") in fake_tmux
    assert not Path(run.worktree).exists()
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    assert messages("supervisor")[-1].summary == (
        "flow feature/login: ended at done; worktree and branch removed"
    )
    assert state.list_runs(session, open_only=True) == []


def test_a_worker_that_ends_the_run_is_closed_last(session, repo, team, fake_tmux):
    # Its own MCP server runs in its window: closing that window ends the call.
    write(
        team / "flows" / "quick.yaml",
        "name: quick\ndescription: d\nstart: build\nstates:\n"
        "  build: {agent: developer, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n",
    )
    runs.start(session, "quick", "x", name="x")
    runs.spawn_worker(session, "quick/x")  # w1, developer
    runs.spawn_worker(session, "quick/x", role="reviewer", task="Watch.")  # w2
    state.set_status(session, "supervisor", state.IDLE)
    runs.advance(session, "w1", "quick/x", "done")
    calls = [c[:3] for c in fake_tmux if c[0] in ("send_text", "kill_window")]
    assert calls[-3:] == [
        ("send_text", session, "supervisor"),
        ("kill_window", session, "w2"),
        ("kill_window", session, "w1"),
    ]


def test_end_keeps_an_unmerged_worktree_and_says_why(session, repo):
    run = to_merge(session)
    commit(run)
    run = runs.advance(session, "supervisor", "feature/login", "merged")
    assert run.status == state.ENDED
    assert [a.name for a in state.list_agents(session)] == ["supervisor", "w1", "w2"]
    assert Path(run.worktree).exists()
    told = messages("supervisor")[-1]
    assert told.summary == "flow feature/login: ended at done; kept its worktree and branch"
    assert f"Branch {run.branch} is not merged into main." in told.body
    assert "workers: w1, w2" in told.body
    # Once merged, the last worker finished takes the worktree and branch with it.
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    assert runtime.finish_worker(session, "w1").how == runtime.CLOSED
    assert Path(run.worktree).exists()
    assert runtime.finish_worker(session, "w2").how == "merged"
    assert not Path(run.worktree).exists()


def test_end_keeps_a_worktree_with_uncommitted_changes(session, repo):
    run = to_merge(session)
    Path(run.worktree, "draft.txt").write_text("x")
    runs.advance(session, "supervisor", "feature/login", "merged")
    assert "has uncommitted changes" in messages("supervisor")[-1].body
    assert Path(run.worktree, "draft.txt").exists()


def test_finishing_a_worker_of_an_open_run_closes_only_its_window(session):
    run = advance_to_review(session)
    finished = runtime.finish_worker(session, "w1")
    assert (finished.how, finished.removed_worktree) == (runtime.CLOSED, False)
    assert Path(run.worktree).exists()
    assert state.get_agent(session, "w1") is None
    finished = runtime.finish_worker(session, "w2", discard=True)
    assert finished.detail() == (
        "closed; discard does not apply: the run keeps its worktree; 1 message dropped"
    )
    assert Path(run.worktree).exists()


def test_cancel_finishes_the_workers_and_keeps_the_worktree(session, repo, fake_tmux):
    run = advance_to_review(session)
    finished = runs.cancel(session, "feature/login", "not needed")
    assert [f.worker.name for f in finished] == ["w1", "w2"]
    assert state.list_agents(session)[-1].name == "supervisor"
    run = state.get_run(session, "feature/login")
    assert (run.status, run.reason) == (state.CANCELLED, "not needed")
    assert Path(run.worktree).exists()
    runtime.git(str(repo), "rev-parse", "--verify", run.branch)
    with pytest.raises(runtime.LadoError, match="cancelled: not needed"):
        runs.advance(session, "w2", "feature/login", "approved")
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
    [mine] = runs.status(session, "w2")
    assert (mine["run"], mine["state"], mine["acting"]) == ("feature/login", "review", "w2")
    assert mine["outcomes"] == {"approved": "merge", "changes": "implement", "again": "review"}
    assert mine["visits"] == {"design": 1, "implement": 1, "review": 1}
    with pytest.raises(runtime.LadoError, match='you work for run "feature/login"'):
        runs.status(session, "w2", "feature/other")
    assert [r["run"] for r in runs.status(session, "supervisor")] == [
        "feature/login",
        "feature/other",
    ]


def test_the_supervisor_is_told_the_flows_and_a_run_worker_how_to_report(session, fake_tmux):
    supervisor = fake_tmux[0][-1]
    prompt = supervisor[supervisor.index("--append-system-prompt") + 1]
    assert "  - feature: New feature, reviewed." in prompt
    assert "Flows are optional" in prompt and "flow_start" in prompt
    to_implement(session)
    runs.spawn_worker(session, "feature/login")
    worker = fake_tmux[-1][-1]
    prompt = worker[worker.index("--append-system-prompt") + 1]
    assert 'flow_advance(run="feature/login", outcome=...)' in prompt


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
