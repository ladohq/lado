"""Flow runs: one task going through the states of a flow (lado.flows).

The supervisor starts a run; LADO then tells the acting agent of each work state its step,
takes the outcome it reports with flow_advance and moves the run on. A run stops for the
human at a gate or when a state would be entered more often than its max_visits allow:
then it has an open gate (state.Gate), which only the human answers (`answer`, from
`lado answer`); no agent tool does. LADO opens a tmux popup with `lado answer` for it.

A run has one git worktree and branch; all its workers work in it. Supervisor steps are
done in the session's repo. When the run ends, its workers are finished and its worktree
and branch removed, if its branch is merged and nothing is left uncommitted.

LADO's messages come from "lado" and go only to the agent that acts next, and to the
supervisor when it acts, when a run waits for the human, ends or is cancelled, or needs a
worker.
"""

import dataclasses
from pathlib import Path

from lado import flows, kits, providers, runtime, state, tmux
from lado.runtime import SUPERVISOR, LadoError

LADO = state.LADO
HUMAN = "human"  # the actor of what the human does from the CLI
NOTE_LIMIT = state.SUMMARY_LIMIT
SLUG_WORDS = 4
SLUG_LENGTH = 30

# What the human can answer at a gate. An approval gate's options name its outcomes.
LOOP = "loop"  # the kind of gate a loop limit opens
APPROVE = dict(zip(("approve", "reject"), flows.APPROVAL, strict=True))  # option -> outcome
CONTINUE, CANCEL = "continue", "cancel"

Events = list[tuple[str, str, str]]  # (actor, kind, detail)


def start(session: str, flow_name: str, task: str, name: str | None = None) -> state.Run:
    """Start a run of flow `flow_name` on `task`, named <flow>/<slug of name or task>, in a
    worktree and branch of its own from the repo's HEAD. Enters the start state."""
    sess = _session(session)
    env = kits.resolve(sess.repo, sess.kits, sess.without)
    flow = env.flow(flow_name)
    task = task.strip()
    if not task:
        raise LadoError("task is empty; say what the run is for")
    if len(task) > runtime.MAX_MESSAGE:
        # It goes into every step's message.
        raise LadoError(
            f"task is {len(task)} characters, the limit is {runtime.MAX_MESSAGE}; "
            "write the details to a file and give its path"
        )
    run_name = _new_name(session, flow.name, name, task)
    folder = runtime.slug(run_name)
    kit = next(k for k in env.kits if k.name == flow.kit)
    run = state.Run(
        session=session,
        name=run_name,
        flow=flow.name,
        snapshot=flow.snapshot,
        kit={"name": kit.name, "version": kit.version, "source": kit.source},
        task=task,
        state=flow.start,
        worktree=str(Path(sess.repo) / ".lado" / "worktrees" / session / folder),
        branch=f"lado/{session}/{folder}",
    )
    started, events, gate = _enter(run, flow, flow.start)
    runtime.exclude_worktrees(sess.repo)
    runtime.git(sess.repo, "worktree", "add", "-b", run.branch, run.worktree, "HEAD")
    version = f" {kit.version}" if kit.version else ""
    detail = f"flow {flow.name} from kit {kit.name}{version}: {task.splitlines()[0][:100]}"
    state.add_run(started, [(SUPERVISOR, state.FLOW_START, detail), *events], gate)
    _arrived(started, flow, SUPERVISOR)
    return started


def advance(
    session: str,
    caller: str,
    run_name: str,
    outcome: str,
    note: str | None = None,
    note_body: str | None = None,
) -> state.Run:
    """Move the run on by `outcome` of its current step, reported by the agent acting in
    it. The note goes to the next step."""
    run = _run(session, run_name)
    if run.status == state.WAITING:
        gate = state.open_gate(session, run.name)
        if gate:
            raise LadoError(
                f'run "{run.name}" waits for the human (gate #{gate.id}): answer with lado answer'
            )
    if run.status != state.ACTIVE:
        raise LadoError(f'run "{run.name}" is {_status_text(run)}; it cannot be advanced now')
    flow = flow_of(run)
    current = flow.states[run.state]
    _check_actor(run, current, caller)
    if outcome not in current.outcomes:
        valid = ", ".join(current.outcomes)
        raise LadoError(f'unknown outcome "{outcome}" for step {run.state}; valid: {valid}')
    note = (note or "").strip()
    if "\n" in note or len(note) > NOTE_LIMIT:
        raise LadoError(
            f"note_summary must be one line of at most {NOTE_LIMIT} characters; "
            "put the details in note_body"
        )
    target = current.outcomes[outcome]
    noted = dataclasses.replace(run, note=note, note_body=note_body or "")
    after, events, gate = _enter(noted, flow, target)
    transition = (caller, state.FLOW, f"{run.state} -{outcome}-> {target}")
    return _commit(run, after, [transition, *events], flow, caller, gate)


def answer(
    session: str, gate: str, option: str, comment: str | None = None, by: str = HUMAN
) -> state.Run:
    """The human's answer to an open gate, given by its id or its run's name: moves the run
    on like flow_advance, with the answer and comment as the next step's note. At a loop
    limit, continue enters the state anyway and cancel cancels the run."""
    found = find_gate(session, gate)
    _check_running(session)
    run = _run(session, found.run)
    word = canonical_option(found, option)
    comment = (comment or "").strip()
    closes = (by, word, comment, found.id)  # nothing is written unless it is still open
    if found.kind == LOOP and word == CANCEL:
        _cancel(run, f"loop limit: {comment}" if comment else "loop limit", by, closes)
        _tell_supervisor(run, f"cancelled by the human at {found.state} (loop limit)", comment)
        return _run(session, run.name)
    flow = flow_of(run)
    if found.kind == LOOP:
        outcome, target = word, found.state
    else:
        outcome = APPROVE.get(word, word) if found.kind == "approval" else word
        target = flow.states[found.state].outcomes[outcome]
    note, note_body = _answer_note(outcome, comment, found)
    noted = dataclasses.replace(run, note=note, note_body=note_body)
    after, events, opens = _enter(noted, flow, target, limit=found.kind != LOOP)
    transition = (by, state.FLOW, f"{run.state} -{outcome}-> {target}")
    after = _commit(run, after, [transition, *events], flow, by, opens, closes)
    if after.status == state.ACTIVE:
        # A worker got the step; the supervisor only hears that the run moved on.
        if _acting_agent(after, flow.states[after.state]) not in (None, SUPERVISOR):
            _tell_supervisor(after, f"human answered {word} at {found.state}")
    return after


def find_gate(session: str, ref: str) -> state.Gate:
    """The open gate `ref` names: a gate id, or a run whose gate it is."""
    if ref.isdigit():
        gate = state.get_gate(int(ref))
        if gate is None:
            raise LadoError(f"no gate #{ref}")
        if gate.session != session:
            raise LadoError(f'gate #{ref} belongs to session "{gate.session}", not "{session}"')
    else:
        run = _run(session, ref)
        gate = state.open_gate(session, run.name)
        if gate is None:
            raise LadoError(f'run "{run.name}" has no open gate; it is {_status_text(run)}')
    if gate.answer is not None:
        raise LadoError(f"gate #{gate.id} is closed already: {gate.answer} by {gate.answered_by}")
    return gate


def canonical_option(gate: state.Gate, given: str) -> str:
    """The option `given` names, in any case; an approval also takes its outcome names."""
    names = {o.lower(): o for o in gate.options}
    if gate.kind == "approval":
        names.update({outcome: word for word, outcome in APPROVE.items()})
    wanted = given.strip()
    if wanted.lower() not in names:
        options = ", ".join(gate.options)
        raise LadoError(f'no option "{wanted}" for gate #{gate.id}; options: {options}')
    return names[wanted.lower()]


def _answer_note(outcome: str, comment: str, gate: state.Gate) -> tuple[str, str]:
    """The next step's note: "<outcome>: <comment>", and in the body the whole comment if
    the note could not hold it, and the note that led to the gate."""
    first = comment.splitlines()[0] if comment else ""
    note = f"{outcome}: {first}" if first else outcome
    body = []
    if len(note) > NOTE_LIMIT:
        note = note[: NOTE_LIMIT - 1] + "…"
        body.append(comment)
    elif comment != first:
        body.append(comment)
    if gate.note or gate.note_body:
        body.append(f"Note before the gate: {gate.note}\n{gate.note_body}".rstrip())
    return note, "\n\n".join(body)


def force(session: str, run_name: str, target: str, reason: str) -> state.Run:
    """The human puts an open run into state `target`, past any gate or loop limit."""
    _check_running(session)
    run = _run(session, run_name)
    if run.status not in state.OPEN:
        raise LadoError(f'run "{run.name}" is {run.status}')
    flow = flow_of(run)
    if target not in flow.states:
        raise LadoError(
            f'no state "{target}" in flow {flow.name}; states: {", ".join(flow.states)}'
        )
    reason = reason.strip()
    if not reason:
        raise LadoError("give a reason")
    noted = dataclasses.replace(run, note=f"set by the human: {reason}"[:NOTE_LIMIT], note_body="")
    after, events, gate = _enter(noted, flow, target, limit=False)
    forced = (HUMAN, state.FLOW_SET, f"{run.state} -> {target}: {reason}")
    closes = (HUMAN, "overridden", reason, None)
    return _commit(run, after, [forced, *events], flow, HUMAN, gate, closes)


def cancel(session: str, run_name: str, reason: str) -> list[runtime.Finished]:
    """The supervisor closes an open run: its workers are finished, its worktree and
    branch are kept. Returns the finished workers."""
    run = _run(session, run_name)
    if run.status not in state.OPEN:
        raise LadoError(f'run "{run.name}" is {run.status} already')
    reason = reason.strip() or "no reason given"
    return _cancel(run, reason, SUPERVISOR, (SUPERVISOR, "cancelled", reason, None))


def _cancel(run: state.Run, reason: str, by: str, closes: state.Close) -> list[runtime.Finished]:
    after = dataclasses.replace(run, status=state.CANCELLED, reason=reason)
    if not state.update_run(run, after, [(by, state.FLOW_CANCEL, reason)], closes=closes):
        raise _changed(run, closes)
    return [runtime.close_worker(run.session, w, "run cancelled") for w in _workers(after)]


def spawn_worker(
    session: str,
    run_name: str,
    role: str | None = None,
    task: str | None = None,
    name: str | None = None,
    provider: str | None = None,
    without: list[str] | None = None,
) -> state.Agent:
    """Start a worker for an open run, in the run's worktree. If the run's current step is
    for its role and no worker has it yet, the step is the worker's task (after `task`, if
    one is given). `role` defaults to the role of the current step."""
    run = _run(session, run_name)
    if run.status not in state.OPEN:
        raise LadoError(f'run "{run.name}" is {run.status}; start workers for open runs')
    flow = flow_of(run)
    current = flow.states[run.state]
    waiting_step = (
        run.status == state.ACTIVE
        and current.kind == flows.WORK
        and _acting_agent(run, current) is None
    )
    role = role or (current.agent if waiting_step else None)
    parts = [task.strip()] if task and task.strip() else []
    if waiting_step and role == current.agent:
        parts.append(step_text(run, flow))
    if not parts:
        raise LadoError(
            f'run "{run.name}" has no step for a {role or "worker"} now; give the worker a task'
        )
    _restore_worktree(_session(session).repo, run)
    return runtime.spawn_worker(session, "\n\n".join(parts), name, provider, role, without, run)


def _restore_worktree(repo: str, run: state.Run) -> None:
    """Make the run's worktree again from its branch if it is gone, e.g. removed by hand
    while the session was stopped."""
    if Path(run.worktree).exists():
        return
    if not runtime.git(repo, "branch", "--list", run.branch):
        raise LadoError(
            f'run "{run.name}" has neither its worktree {run.worktree} nor its branch '
            f"{run.branch}; cancel it with flow_cancel"
        )
    runtime.git(repo, "worktree", "prune")  # git still lists the removed folder
    runtime.git(repo, "worktree", "add", run.worktree, run.branch)


def resume(sess: state.Session, env: kits.Environment) -> list[str]:
    """Queue LADO's messages for the new supervisor of a resumed session: one about the
    open runs, then the steps of the runs at a supervisor state again. Returns a line for
    each run that needs a role the session has no more."""
    supervisor = env.supervisor().name
    lines, problems, steps = [], [], []
    open_runs = state.list_runs(sess.name, open_only=True)
    for run in open_runs:
        flow = flow_of(run)
        current = flow.states[run.state]
        gate = state.open_gate(sess.name, run.name) if run.status == state.WAITING else None
        if gate:
            what = (
                f"waits for the human at gate #{gate.id}: {gate.question} Only the human "
                f"answers it, with: lado answer {sess.name} {gate.id}. Nothing to do until then."
            )
        elif run.status == state.WAITING:
            what = f"waits for the human: {run.reason}"
        elif current.agent == supervisor:
            what = "your step; it follows as a message from lado."
            steps.append(run)
        else:
            what = (
                f'needs a {current.agent}. Start one with spawn_worker(role="{current.agent}", '
                f'run="{run.name}"); it works in the run\'s worktree and gets the step as its '
                "task."
            )
        lines.append(f"- {run.name} at {run.state}: {what}")
        roles = {s.agent for s in flow.states.values() if s.kind == flows.WORK}
        gone = sorted(roles - set(env.agents))
        if gone:
            problem = (
                f"role{'s' if len(gone) > 1 else ''} {', '.join(gone)} "
                f"{'are' if len(gone) > 1 else 'is'} not in the session now; cancel the run "
                "with flow_cancel, or move it on with lado flow-set"
            )
            problems.append(f"run {run.name}: {problem}")
            lines.append(f"  {problem[0].upper()}{problem[1:]}.")
    count = len(open_runs)
    summary = f"session resumed: {count} open run{'' if count == 1 else 's'}"
    state.queue_message(sess.name, LADO, SUPERVISOR, summary, "\n".join(lines))
    for run in steps:
        summary = f"flow {run.name}: step {run.state}"
        state.queue_message(sess.name, LADO, SUPERVISOR, summary, step_text(run, flow_of(run)))
    return problems


def flow_of(run: state.Run) -> flows.Flow:
    """The flow as it was when the run started."""
    return flows.from_snapshot(run.snapshot, run.kit.get("name", ""))


def acting(run: state.Run) -> str:
    """Who acts next: the supervisor, a worker's name, "<role> (not spawned)" or "human"."""
    if run.status == state.WAITING:
        return HUMAN
    if run.status != state.ACTIVE:
        return ""
    current = flow_of(run).states[run.state]
    who = _acting_agent(run, current)
    return who or f"{current.agent} (not spawned)"


def status(session: str, caller: str, run_name: str | None = None) -> list[dict]:
    """The runs `caller` can see: a worker its own run, the supervisor every open run (or
    `run_name`, open or not)."""
    me = state.get_agent(session, caller)
    if me is None:
        raise LadoError(f'no agent "{caller}"')
    if caller != SUPERVISOR:
        if run_name and run_name != me.run:
            raise LadoError(f'you work for run "{me.run}", not "{run_name}"')
        run_name = me.run
        if run_name is None:
            return []
    found = [_run(session, run_name)] if run_name else state.list_runs(session, open_only=True)
    return [describe(r) for r in found]


def step_text(run: state.Run, flow: flows.Flow) -> str:
    """What the acting agent of a work state is told: the task, the step, the previous
    step's note and how to report the outcome."""
    current = flow.states[run.state]
    parts = [
        f"Run {run.name} (flow {flow.name}), step {run.state}.",
        f"Task:\n{run.task}",
        f"Step:\n{current.do}",
    ]
    if run.note or run.note_body:
        parts.append(f"Note from the previous step: {run.note}\n{run.note_body}".rstrip())
    outcomes = "\n".join(f"- {o} -> {t}" for o, t in current.outcomes.items())
    parts.append(
        f'When the step is done, call flow_advance(run="{run.name}", outcome=...) with one '
        f"of these outcomes:\n{outcomes}\n"
        "Pass a note for the next step in note_summary (one line) and note_body."
    )
    return "\n\n".join(parts)


def _enter(
    run: state.Run, flow: flows.Flow, target: str, limit: bool = True
) -> tuple[state.Run, Events, state.Gate | None]:
    """The run after entering `target`, LADO's events about it and the gate it waits at,
    if it does. A state entered as often as its max_visits allow (and `limit`) is not
    entered: the run waits for the human instead."""
    entered = flow.states[target]
    visits = run.visits.get(target, 0)
    if limit and entered.max_visits is not None and visits >= entered.max_visits:
        reason = f"loop limit reached at {target}"
        after = dataclasses.replace(run, status=state.WAITING, reason=reason)
        question = f"{reason}: what next?"
        return after, [], _new_gate(after, target, LOOP, question, [CONTINUE, CANCEL])
    after = dataclasses.replace(
        run,
        state=target,
        visits={**run.visits, target: visits + 1},
        status=state.ACTIVE,
        reason="",
    )
    if entered.kind == flows.GATE:
        after.status, after.reason = state.WAITING, entered.ask
        options = list(APPROVE) if entered.gate == "approval" else list(entered.outcomes)
        return after, [], _new_gate(after, target, entered.gate, entered.ask, options)
    if entered.kind == flows.END:
        after.status = state.ENDED
        return after, [(LADO, state.FLOW_END, f"at {target}")], None
    return after, [], None


def _new_gate(run: state.Run, at: str, kind: str, question: str, options: list[str]) -> state.Gate:
    """A gate for the run, with the note of the step that led to it."""
    return state.Gate(run.session, run.name, at, kind, question, options, run.note, run.note_body)


def _commit(
    before: state.Run,
    after: state.Run,
    events: Events,
    flow: flows.Flow,
    caller: str,
    opens: state.Gate | None = None,
    closes: state.Close | None = None,
) -> state.Run:
    if not state.update_run(before, after, events, opens, closes):
        raise _changed(before, closes)
    _arrived(after, flow, caller)
    return after


def _changed(run: state.Run, closes: state.Close | None) -> LadoError:
    """Why a write was refused: the gate it answers was answered first, or the run moved."""
    gate = state.get_gate(closes[3]) if closes and closes[3] else None
    if gate and gate.answer is not None:
        return LadoError(f"gate #{gate.id} is closed already: {gate.answer} by {gate.answered_by}")
    return LadoError(f'run "{run.name}" changed meanwhile; see flow_status')


def _arrived(run: state.Run, flow: flows.Flow, caller: str) -> None:
    """Tell whoever acts now: the step's agent, or the supervisor; close an ended run.
    The transition is stored already, so an error says that the run did move on."""
    try:
        _act_on_arrival(run, flow, caller)
    except (LadoError, tmux.TmuxError) as exc:
        raise LadoError(
            f'run "{run.name}" moved on to {run.state} ({run.status}), but: {exc}'
        ) from exc


def _act_on_arrival(run: state.Run, flow: flows.Flow, caller: str) -> None:
    if run.status == state.WAITING:
        gate = state.open_gate(run.session, run.name)
        _tell_supervisor(
            run,
            f"waiting for the human at {gate.state} (gate #{gate.id})",
            f"{gate.question}\nOnly the human answers it: lado answer {run.session} {gate.id}",
        )
        _popup(run.session, gate)
    elif run.status == state.ENDED:
        _close(run, caller)
    else:
        _deliver_step(run, flow)


def _popup(session: str, gate: state.Gate) -> None:
    """Ask the human in a popup on the clients attached to the session. The popup's
    `lado answer` goes on with the session's other open gates, so one title fits all: a
    client that shows a popup already keeps it. The popup gets the tmux session's
    environment, which has the supervisor's LADO_AGENT: it is the human's, so without."""
    unset = ["env", "-u", "LADO_AGENT", "-u", "LADO_SESSION"]
    argv = unset + providers.lado_command("answer", session, str(gate.id))
    env = {"LADO_HOME": str(state.home()), "LADO_TMUX_SOCKET": tmux.socket()}
    tmux.popup(session, f"lado {session}: waiting for you", argv, env)


def _deliver_step(run: state.Run, flow: flows.Flow) -> None:
    current = flow.states[run.state]
    who = _acting_agent(run, current)
    if who is None:
        _tell_supervisor(
            run,
            f"step {run.state} needs a {current.agent}",
            f'Start one with spawn_worker(role="{current.agent}", run="{run.name}"); it gets '
            "the step as its task.",
        )
        return
    runtime.post(run.session, LADO, who, f"flow {run.name}: step {run.state}", step_text(run, flow))


def _close(run: state.Run, caller: str) -> None:
    """Finish an ended run's workers and remove its worktree and branch, if its branch is
    merged and its worktree clean. Otherwise keep them all and say why. `caller` is the
    agent (or the human) whose action ended the run."""
    repo = _session(run.session).repo
    workers = _workers(run)
    problem = _unfinished(repo, run)
    if problem:
        kept = ", ".join(w.name for w in workers) or "none"
        _tell_supervisor(
            run,
            f"ended at {run.state}; kept its worktree and branch",
            f"{problem}\nKept: worktree {run.worktree}, branch {run.branch}, workers: {kept}.\n"
            "Merge the branch, then finish_worker each worker: the last one removes the "
            "worktree and branch (with no workers left, remove them with git).",
        )
        return
    # Git first: if it fails, the workers keep running and nothing is half done.
    runtime.git(repo, "worktree", "remove", run.worktree)
    runtime.git(repo, "branch", "-d", run.branch)
    _tell_supervisor(run, f"ended at {run.state}; worktree and branch removed")
    # The caller last: this code runs in its MCP server, which goes with its window.
    for worker in sorted(workers, key=lambda w: w.name == caller):
        runtime.close_worker(run.session, worker, "run ended")


def _unfinished(repo: str, run: state.Run) -> str:
    """Why the run's work would be lost if its worktree went, or ""."""
    try:
        runtime.git(repo, "merge-base", "--is-ancestor", run.branch, "HEAD")
    except LadoError:
        head = runtime.git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        return f"Branch {run.branch} is not merged into {head}."
    if runtime.git(run.worktree, "status", "--porcelain"):
        return f"The worktree {run.worktree} has uncommitted changes."
    return ""


def _tell_supervisor(run: state.Run, what: str, body: str = "") -> None:
    summary = f"flow {run.name}: {what}"
    if len(summary) > state.SUMMARY_LIMIT:
        summary, body = summary[: state.SUMMARY_LIMIT - 1] + "…", f"{summary}\n{body}".strip()
    runtime.post(run.session, LADO, SUPERVISOR, summary, body)


def _acting_agent(run: state.Run, current: flows.State) -> str | None:
    """The agent that does a work state: the supervisor for the supervisor's role, else
    the run's first worker with the role; None if it has none."""
    supervisor = state.get_agent(run.session, SUPERVISOR)
    if supervisor and current.agent == supervisor.role:
        return SUPERVISOR
    for worker in _workers(run):
        if worker.role == current.agent:
            return worker.name
    return None


def _check_actor(run: state.Run, current: flows.State, caller: str) -> None:
    supervisor = state.get_agent(run.session, SUPERVISOR)
    if supervisor and current.agent == supervisor.role:
        allowed, who = caller == SUPERVISOR, "the supervisor"
    else:
        me = state.get_agent(run.session, caller)
        allowed = me is not None and me.run == run.name and me.role == current.agent
        who = f"the run's {current.agent}"
    if not allowed:
        raise LadoError(
            f'step {run.state} of run "{run.name}" is for {who}; "{caller}" cannot advance it'
        )


def _workers(run: state.Run) -> list[state.Agent]:
    return [a for a in state.list_agents(run.session) if a.run == run.name]


def describe(run: state.Run) -> dict:
    current = flow_of(run).states[run.state]
    gate = state.open_gate(run.session, run.name) if run.status == state.WAITING else None
    return {
        "run": run.name,
        "flow": run.flow,
        "task": run.task,
        "state": run.state,
        "status": run.status,
        "reason": run.reason,
        "acting": acting(run),
        "outcomes": current.outcomes if run.status == state.ACTIVE else {},
        "gate": gate and {"id": gate.id, "question": gate.question, "options": gate.options},
        "visits": run.visits,
        "note": run.note,
        "worktree": run.worktree,
        "branch": run.branch,
    }


def _status_text(run: state.Run) -> str:
    if run.status == state.WAITING:
        return f"waiting for the human: {run.reason}"
    if run.status == state.CANCELLED:
        return f"cancelled: {run.reason}"
    return run.status


def _new_name(session: str, flow: str, name: str | None, task: str) -> str:
    taken = {r.name for r in state.list_runs(session)}
    if name:
        wanted = f"{flow}/{runtime.slug(name)}"
        if wanted in taken:
            raise LadoError(f'a run "{wanted}" already exists in session "{session}"')
        return wanted
    words = " ".join(task.splitlines()[0].split()[:SLUG_WORDS])
    base = f"{flow}/{runtime.slug(words)[:SLUG_LENGTH].strip('-')}"
    wanted, n = base, 1
    while wanted in taken:
        n += 1
        wanted = f"{base}-{n}"
    return wanted


def _run(session: str, name: str) -> state.Run:
    run = state.get_run(session, name)
    if run is None:
        names = ", ".join(r.name for r in state.list_runs(session, open_only=True)) or "none"
        raise LadoError(f'no run "{name}"; open runs: {names}')
    return run


def _session(session: str) -> state.Session:
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    return sess


def _check_running(session: str) -> None:
    """Moving a run on tells its agents: a stopped session has none."""
    if _session(session).stopped_at:
        raise LadoError(
            f'session "{session}" is stopped; resume it with `lado start` first, its open '
            "runs and gates wait"
        )
