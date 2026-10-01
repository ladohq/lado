"""Flow runs: one task going through the states of a flow (lado.flows).

The supervisor starts a run; LADO then tells the acting agent of each work state its step,
takes the outcome it reports with flow_advance and moves the run on. A run stops for the
human at a gate or when a state would be entered more often than its max_visits allow.

A run has one git worktree and branch; all its workers work in it. Supervisor steps are
done in the session's repo. When the run ends, its workers are finished and its worktree
and branch removed, if its branch is merged and nothing is left uncommitted.

LADO's messages come from "lado" and go only to the agent that acts next, and to the
supervisor when it acts, when a run waits for the human, ends or is cancelled, or needs a
worker.
"""

import dataclasses
from pathlib import Path

from lado import flows, kits, runtime, state
from lado.runtime import SUPERVISOR, LadoError

LADO = "lado"  # the sender of LADO's own messages
HUMAN = "human"  # the actor of what the human does from the CLI
NOTE_LIMIT = state.SUMMARY_LIMIT
SLUG_WORDS = 4
SLUG_LENGTH = 30

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
    started, events = _enter(run, flow, flow.start)
    runtime.exclude_worktrees(sess.repo)
    runtime.git(sess.repo, "worktree", "add", "-b", run.branch, run.worktree, "HEAD")
    version = f" {kit.version}" if kit.version else ""
    detail = f"flow {flow.name} from kit {kit.name}{version}: {task.splitlines()[0][:100]}"
    state.add_run(started, [(SUPERVISOR, state.FLOW_START, detail), *events])
    _arrived(started, flow)
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
    after, events = _enter(noted, flow, target)
    transition = (caller, state.FLOW, f"{run.state} -{outcome}-> {target}")
    return _commit(run, after, [transition, *events], flow)


def force(session: str, run_name: str, target: str, reason: str) -> state.Run:
    """The human puts an open run into state `target`, past any gate or loop limit."""
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
    after, events = _enter(noted, flow, target, limit=False)
    forced = (HUMAN, state.FLOW_SET, f"{run.state} -> {target}: {reason}")
    return _commit(run, after, [forced, *events], flow)


def cancel(session: str, run_name: str, reason: str) -> list[runtime.Finished]:
    """The supervisor closes an open run: its workers are finished, its worktree and
    branch are kept. Returns the finished workers."""
    run = _run(session, run_name)
    if run.status not in state.OPEN:
        raise LadoError(f'run "{run.name}" is {run.status} already')
    reason = reason.strip() or "no reason given"
    after = dataclasses.replace(run, status=state.CANCELLED, reason=reason)
    if not state.update_run(run, after, [(SUPERVISOR, state.FLOW_CANCEL, reason)]):
        raise LadoError(f'run "{run.name}" changed meanwhile; see flow_status')
    return [runtime.close_worker(session, w, "run cancelled") for w in _workers(after)]


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
    return runtime.spawn_worker(session, "\n\n".join(parts), name, provider, role, without, run)


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
) -> tuple[state.Run, Events]:
    """The run after entering `target`, and LADO's events about it. A state entered as
    often as its max_visits allow (and `limit`) is not entered: the run waits for the
    human instead."""
    entered = flow.states[target]
    visits = run.visits.get(target, 0)
    if limit and entered.max_visits is not None and visits >= entered.max_visits:
        reason = f"loop limit reached at {target}"
        return dataclasses.replace(run, status=state.WAITING, reason=reason), [
            (LADO, state.FLOW_WAIT, reason)
        ]
    after = dataclasses.replace(
        run,
        state=target,
        visits={**run.visits, target: visits + 1},
        status=state.ACTIVE,
        reason="",
    )
    if entered.kind == flows.GATE:
        after.status, after.reason = state.WAITING, entered.ask
        return after, [(LADO, state.FLOW_WAIT, f"at {target}: {entered.ask}")]
    if entered.kind == flows.END:
        after.status = state.ENDED
        return after, [(LADO, state.FLOW_END, f"at {target}")]
    return after, []


def _commit(before: state.Run, after: state.Run, events: Events, flow: flows.Flow) -> state.Run:
    if not state.update_run(before, after, events):
        raise LadoError(f'run "{before.name}" changed meanwhile; see flow_status')
    _arrived(after, flow)
    return after


def _arrived(run: state.Run, flow: flows.Flow) -> None:
    """Tell whoever acts now: the step's agent, or the supervisor; close an ended run."""
    if run.status == state.WAITING:
        _tell_supervisor(
            run,
            f"waiting for the human at {run.state}: {run.reason}",
            f"The human moves the run on with: lado flow-set {run.session} {run.name} "
            "<state> --reason TEXT",
        )
    elif run.status == state.ENDED:
        _close(run)
    else:
        _deliver_step(run, flow)


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


def _close(run: state.Run) -> None:
    """Finish an ended run's workers and remove its worktree and branch, if its branch is
    merged and its worktree clean. Otherwise keep them all and say why."""
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
    for worker in workers:
        runtime.close_worker(run.session, worker, "run ended")
    runtime.git(repo, "worktree", "remove", run.worktree)
    runtime.git(repo, "branch", "-d", run.branch)
    _tell_supervisor(run, f"ended at {run.state}; worktree and branch removed")


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
    return {
        "run": run.name,
        "flow": run.flow,
        "task": run.task,
        "state": run.state,
        "status": run.status,
        "reason": run.reason,
        "acting": acting(run),
        "outcomes": current.outcomes if run.status == state.ACTIVE else {},
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
