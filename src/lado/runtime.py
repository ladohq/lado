"""Agent runtime: starts agents in tmux and delivers messages to them.

Each agent's provider (lado.providers) gives it its own MCP config (so the LADO MCP server
knows who is calling) and hooks (so LADO learns when the agent is busy, idle or waiting).
"""

import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from lado import kits, providers, state, tmux

SUPERVISOR = "supervisor"  # the supervisor's agent name, whatever its role
MAX_MESSAGE = 8000
CONFIRM_TIMEOUT = 15  # seconds for a typed message to show up as a prompt

# What every agent must know about LADO, appended to its role prompt from the kit. Kits only
# describe the role.
SUPERVISOR_INSTRUCTIONS = """\
You are agent "supervisor" in LADO session "{session}". The human talks to you in this window.
Use the `lado` MCP tools:
- spawn_worker: start a worker agent on a task, in its own git worktree and a branch created \
from your current HEAD. Give it the goal, the relevant files and how to check the result. \
`role` picks the kind of worker{default_role}. Roles:
{roles}
- send_message: talk to another agent, e.g. to answer a worker's question.
- read_messages: read the full text of the messages you got.
- list_agents: see the agents, their role, status, branch and worktree.
- finish_worker: once you merged a worker's branch, end that worker; its window, worktree \
and branch are removed.
Workers report back with messages that arrive in your input as "[from <name>] ...".
Do not relay worker or reviewer reports to the human. Talk to the human only when a \
decision is needed (the question and your recommendation) or at a milestone (one or two \
lines). The details stay in `lado log {session}`.
"""

WORKER_INSTRUCTIONS = """\
You are worker "{name}" in LADO session "{session}", working in your own git worktree on \
branch {branch}. Commit your work on that branch.
Report to your supervisor with the `lado` MCP tool send_message(to="supervisor", ...).
The supervisor cannot see your screen: calling that tool is the only way to reach it, and a
report you only write as text is lost.
Messages from other agents arrive in your input as "[from <name>] ...".
"""

FLOW_INSTRUCTIONS = """\
Flows are optional algorithms from the kits for one task: steps, who does each and the \
allowed outcomes. Use one when its description fits the task:
{flows}
- flow_start(flow, task): start a run of a flow. It gets its own git worktree and branch \
from your current HEAD, shared by all its workers. LADO then sends each step, as a message \
from "lado", to the agent that acts in it: to you for supervisor steps, otherwise to the \
run's worker with the step's role. When a step needs a worker the run does not have, LADO \
asks you to start it with spawn_worker(role=..., run=...); it gets the step as its task.
- flow_advance(run, outcome, note_summary, note_body): report the outcome of your own step.
- flow_status: the runs, their state, who acts and the allowed outcomes.
- flow_cancel(run, reason): stop a run; its worktree and branch are kept.
When a run waits for the human (a gate or a loop limit), only the human can answer it, \
with `lado answer` (LADO asks them in a popup); no tool of yours does. The run's next step \
arrives once they answer.
"""

RUN_WORKER_INSTRUCTIONS = """\
You are worker "{name}" in LADO session "{session}", working for the flow run "{run}" in \
the run's git worktree on branch {branch}, shared with the run's other workers. Commit \
your work on that branch.
LADO sends you the run's steps as messages from "lado". When you finish a step, report its \
outcome with the `lado` MCP tool flow_advance(run="{run}", outcome=...); flow_status shows \
the step and its outcomes. Report to your supervisor as well, with send_message(to="supervisor", \
...).
The supervisor cannot see your screen: calling those tools is the only way to reach it, and a
report you only write as text is lost.
Messages from other agents arrive in your input as "[from <name>] ...".
"""

# How every agent sends and reads messages, appended to the instructions above.
MESSAGING = """\
Messages: send_message takes a one-line summary (at most 200 characters), the only thing \
the recipient sees at first; put the details in body. A message with a body arrives as one \
line ending in "call read_messages": call read_messages to get its full text. Make \
send_message the last action of your turn. Send no status-only messages: being idle tells \
the others you are done.
"""

WORKTREES_EXCLUDE = "/.lado/worktrees/"
REPORT_REMINDER = (
    '\n\nWhen you are done, report back with send_message(to="supervisor"): summary = your '
    "status and a one-line result, body = the full report."
)


class LadoError(RuntimeError):
    pass


def slug(value: str) -> str:
    """A name that is safe for tmux targets, git branches and paths."""
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "lado"


def git(repo: str, *args: str) -> str:
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LadoError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def repo_root(path: str) -> str:
    try:
        return git(path, "rev-parse", "--show-toplevel")
    except LadoError as exc:
        raise LadoError(f"{path} is not inside a git repository") from exc


@dataclass
class Started:
    session: state.Session
    resumed: bool = False  # a stopped session started again, with its history and runs
    changes: list[str] = field(default_factory=list)  # settings a resume replaced
    problems: list[str] = field(default_factory=list)  # open runs that cannot go on as they are


def start_session(
    path: str,
    name: str | None,
    permission_mode: str | None,
    provider: str | None = None,
    kit_names: list[str] | None = None,
    without: list[str] | None = None,
) -> Started:
    """Start a session whose agents come from `kit_names` (default: the "default" kit), minus
    the `without` items ("agent:x", "skill:y", "mcp:z").

    A stopped session of that name, or one whose tmux server is gone, is resumed: it keeps
    its history, open runs and gates, and the settings given replace its stored ones. The
    new supervisor starts with a message about the open runs (lado.runs.resume)."""
    repo = repo_root(path)
    session = slug(name or Path(repo).name)
    old = state.get_session(session)
    if old:
        if not old.stopped_at and tmux.has_session(session):
            raise LadoError(f'session "{session}" is already running; use `lado attach {session}`')
        if old.repo != repo:
            raise LadoError(
                f'session "{session}" was started in {old.repo}; to start a fresh session for '
                f"{repo}, give it another name with --name, or drop the old one with "
                f"`lado forget {session}`"
            )
    agent_cli = _provider(provider or (old.provider if old else providers.DEFAULT))
    sess = state.Session(
        session,
        repo,
        permission_mode or (old.permission_mode if old else None),
        agent_cli.name,
        kit_names or (old.kits if old else [kits.DEFAULT_KIT]),
        without if without is not None else (old.without if old else []),
    )
    env = kits.resolve(repo, sess.kits, sess.without)
    role = env.supervisor()
    agent = state.Agent(
        session, SUPERVISOR, role.name, repo, None, None, state.STARTING, sess.provider
    )
    spec = _spec(agent_cli, env, role.name, agent, _supervisor_instructions(env, session))
    started = Started(sess)
    if old:
        if not old.stopped_at:
            state.stop_session(session)  # left over from a tmux server that is gone
        started.resumed, started.changes = True, _changes(old, sess)
        state.resume_session(sess, "; ".join(started.changes) or "same settings")
        # Imported here: lado.runs builds on this module.
        from lado import runs

        started.problems = runs.resume(sess, env)
        # LADO's messages about the open runs are its first input, so they cannot be lost
        # while it starts.
        agent.task = format_messages(state.take_pending(session, SUPERVISOR, state.DELIVERED))
    else:
        state.add_session(sess)
    _add_agent(agent)
    try:
        launch = agent_cli.launch_command(agent, sess, spec, first_message=agent.task)
        tmux.new_session(session, SUPERVISOR, repo, _env(agent, launch), launch.argv)
    except tmux.TmuxError:
        if old:
            state.stop_session(session)
        else:
            state.delete_session(session)
        raise
    return started


def _changes(old: state.Session, new: state.Session) -> list[str]:
    """The settings a resume replaced, as "<what>: <old> -> <new>"."""
    changes = []
    for what, before, after in (
        ("provider", old.provider, new.provider),
        ("permission mode", old.permission_mode, new.permission_mode),
        ("kits", ", ".join(old.kits), ", ".join(new.kits)),
        ("without", ", ".join(old.without), ", ".join(new.without)),
    ):
        if before != after:
            changes.append(f"{what}: {before or 'none'} -> {after or 'none'}")
    return changes


def spawn_worker(
    session: str,
    task: str,
    name: str | None = None,
    provider: str | None = None,
    role: str | None = None,
    without: list[str] | None = None,
    run: state.Run | None = None,
) -> state.Agent:
    """Start a worker with `role` from the session's kits (default: the kits' default_agent,
    else "worker"), minus the `without` items ("skill:y", "mcp:z") for this worker.

    A worker gets its own worktree and branch; a worker for a flow `run` works in the
    run's worktree, shared with the run's other workers (see lado.runs.spawn_worker)."""
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    agent_cli = _provider(provider or sess.provider)
    env = kits.resolve(sess.repo, sess.kits, sess.without)
    role_def = env.worker_role(role)
    taken = {a.name for a in state.list_agents(session)}
    # A worker of a stopped launch of the session may have left its branch.
    branches = git(sess.repo, "branch", "--list", "--format=%(refname:short)", f"lado/{session}/*")
    kept = {b.rsplit("/", 1)[1] for b in branches.split()}
    worker = slug(name) if name else _next_name(taken | kept)
    if worker in taken:
        raise LadoError(f'an agent named "{worker}" already exists')
    if run:
        branch, worktree = run.branch, Path(run.worktree)
        instructions = RUN_WORKER_INSTRUCTIONS.format(
            name=worker, session=session, branch=branch, run=run.name
        )
    else:
        branch = f"lado/{session}/{worker}"
        worktree = Path(sess.repo) / ".lado" / "worktrees" / session / worker
        instructions = WORKER_INSTRUCTIONS.format(name=worker, session=session, branch=branch)
    agent = state.Agent(
        session,
        worker,
        role_def.name,
        str(worktree),
        branch,
        task,
        state.STARTING,
        agent_cli.name,
        run=run.name if run else None,
    )
    spec = _spec(agent_cli, env, role_def.name, agent, instructions, without or [])
    if not run:
        exclude_worktrees(sess.repo)
        git(sess.repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
    _add_agent(agent)
    launch = agent_cli.launch_command(agent, sess, spec, first_message=task + REPORT_REMINDER)
    tmux.new_window(session, worker, str(worktree), _env(agent, launch), launch.argv)
    return agent


@dataclass
class Finished:
    worker: state.Agent
    how: str  # "merged", "discarded", or CLOSED: only its window, its run keeps the worktree
    dropped: int  # messages it never got

    @property
    def removed_worktree(self) -> bool:
        return self.how in ("merged", "discarded")

    def detail(self) -> str:
        if not self.dropped:
            return self.how
        return f"{self.how}; {self.dropped} message{'s' if self.dropped > 1 else ''} dropped"


def finish_worker(session: str, name: str, discard: bool = False) -> Finished:
    """End a worker whose branch is merged: close its window, remove its worktree and branch
    and forget it, so the name can be used again. Its messages and events stay in the log.

    `discard` also ends a worker whose work is not merged or not committed, and throws that
    work away.

    A worker of a flow run shares the run's worktree: while the run is open or other
    workers of it remain, only its window is closed. The last worker of an ended run takes
    the worktree and branch with it, as above.
    """
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    if name == SUPERVISOR:
        raise LadoError(
            f"the supervisor is not a worker and cannot be finished; "
            f"end the whole session with `lado stop {session}`"
        )
    worker = state.get_agent(session, name)
    if worker is None or worker.branch is None:
        workers = ", ".join(a.name for a in state.list_agents(session) if a.branch) or "none"
        raise LadoError(f'no worker "{name}"; workers: {workers}')
    if worker.run and _run_keeps_worktree(session, worker):
        if discard:
            return close_worker(session, worker, f"{CLOSED}; {DISCARD_NOT_APPLIED}")
        return close_worker(session, worker, CLOSED)
    if not discard:
        _check_finished(sess.repo, worker)
    # Git first: if it fails, the worker keeps running and nothing is half done.
    git(sess.repo, "worktree", "remove", *(["--force"] if discard else []), worker.cwd)
    git(sess.repo, "branch", "-D" if discard else "-d", worker.branch)
    return close_worker(session, worker, "discarded" if discard else "merged")


CLOSED = "closed"  # a run's worker: its window is closed, the run keeps the worktree
DISCARD_NOT_APPLIED = "discard does not apply: the run keeps its worktree"


def close_worker(session: str, worker: state.Agent, how: str) -> Finished:
    """Close the worker's window and forget it; its worktree is left alone."""
    tmux.kill_window(session, worker.name)
    state.delete_agent(session, worker.name)
    # Forgotten first, so no new message can be queued for it: a later worker with the
    # same name must not get what was meant for this one.
    dropped = state.drop_undelivered(session, worker.name)
    finished = Finished(worker, how, dropped)
    state.add_event(session, worker.name, state.FINISHED, finished.detail())
    return finished


def _run_keeps_worktree(session: str, worker: state.Agent) -> bool:
    """A run's worktree stays while the run is open or other workers of it remain."""
    run = state.get_run(session, worker.run)
    others = [
        a for a in state.list_agents(session) if a.run == worker.run and a.name != worker.name
    ]
    return bool(others) or (run is not None and run.status in state.OPEN)


def _check_finished(repo: str, worker: state.Agent) -> None:
    """Refuse to end a worker whose work would be lost."""
    try:
        git(repo, "merge-base", "--is-ancestor", worker.branch, "HEAD")
    except LadoError:
        head = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        raise LadoError(
            f"branch {worker.branch} is not merged into {head} (the current branch of {repo}); "
            "merge it first, or finish with discard to throw its work away"
        ) from None
    changes = git(worker.cwd, "status", "--porcelain")
    if changes:
        raise LadoError(
            f'worker "{worker.name}" has uncommitted changes in {worker.cwd}:\n{changes}\n'
            "have it commit them and merge again, or finish with discard to throw them away"
        )


def send_message(
    session: str, sender: str, recipient: str, summary: str, body: str | None = None
) -> str:
    """Queue a message and deliver it now if the recipient is idle. Only the one-line
    summary is typed; the recipient reads the body with read_messages.

    A busy recipient gets it from its turn-end hook when its current turn ends (see lado.hooks).
    """
    summary = summary.strip()
    _check_summary(summary)
    body = body or ""
    if len(body) > MAX_MESSAGE:
        raise LadoError(
            f"body is {len(body)} characters, the limit is {MAX_MESSAGE}; "
            "write the details to a file and send its path"
        )
    return post(session, sender, recipient, summary, body)


def post(session: str, sender: str, recipient: str, summary: str, body: str = "") -> str:
    """Queue a message whose summary is checked already and deliver it now if the
    recipient is idle. LADO's own messages (lado.runs) come here directly: a step's body
    carries the task, which may be longer than an agent's message."""
    agent = state.get_agent(session, recipient)
    if agent is None or agent.status == state.STOPPED:
        names = ", ".join(a.name for a in state.list_agents(session) if a.status != state.STOPPED)
        raise LadoError(f'no running agent "{recipient}"; running agents: {names}')
    state.queue_message(session, sender, recipient, summary, body)
    # A typed message the agent never received leaves it marked busy without it being so.
    lost = state.requeue_unconfirmed(session, recipient, CONFIRM_TIMEOUT)
    # Queue first, read the status second: the turn-end hook does the reverse, so a message is
    # never left behind by an agent that went idle in between.
    status = state.get_agent(session, recipient).status
    if status != state.IDLE and not lost:
        return f"queued; {recipient} is {status} and will get it when its turn ends"
    return "sent" if deliver_pending(session, recipient) else "queued"


def deliver_pending(session: str, recipient: str) -> bool:
    """Type the recipient's pending messages into its window. They stay "sent" until its
    prompt-submit hook confirms them."""
    pending = state.take_pending(session, recipient, state.SENT)
    if not pending:
        return False
    state.set_status(session, recipient, state.BUSY)
    tmux.send_text(session, recipient, format_messages(pending))
    return True


def _check_summary(summary: str) -> None:
    """Refuse a summary that cannot be typed as one line. It must be stripped already: the
    agent CLI trims what is typed, and the typed line must match the prompt it confirms."""
    if not summary:
        raise LadoError("summary is empty; say in one line what the message is about")
    if len(summary.splitlines()) > 1:
        raise LadoError("summary must be one line; put the details in body")
    if any(unicodedata.category(c) == "Cc" for c in summary):
        raise LadoError(
            "summary must be one line without control characters; put the details in body"
        )
    if len(summary) > state.SUMMARY_LIMIT:
        raise LadoError(
            f"summary is {len(summary)} characters, the limit is {state.SUMMARY_LIMIT}; "
            "put the details in body"
        )


def format_message(message: state.Message) -> str:
    """The one line typed for a message; its body is left for read_messages."""
    line = f"[from {message.sender}] {message.title}"
    if not message.body:
        return line
    lines = len(message.body.splitlines())
    return f"{line} (#{message.id}, {lines} line{'s' if lines != 1 else ''}: call read_messages)"


def format_messages(messages: list[state.Message]) -> str:
    return "\n".join(format_message(m) for m in messages)


@dataclass
class Stopped:
    workers: list[state.Agent]  # their worktrees stay on disk
    dropped: int  # messages no agent got


def stop_session(session: str) -> Stopped:
    """Kill the session's agents and mark it stopped. Its history, runs and gates stay
    until `lado start` resumes it or `lado forget` drops it; worktrees stay on disk."""
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    if sess.stopped_at:
        raise LadoError(
            f'session "{session}" is stopped already; resume it with `lado start`, '
            f"or drop it with `lado forget {session}`"
        )
    if tmux.has_session(session):
        tmux.kill_session(session)
    agents, dropped = state.stop_session(session)
    return Stopped([a for a in agents if a.name != SUPERVISOR], dropped)


@dataclass
class Forgotten:
    runs: list[str]  # the open runs dropped
    worktrees: dict[str, str]  # worktree -> branch, left on disk


def forget_session(session: str, force: bool = False) -> Forgotten:
    """Delete a stopped session with its history, runs and gates. With open runs only if
    `force`. Worktrees and branches stay on disk."""
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    if not sess.stopped_at:
        raise LadoError(
            f'session "{session}" is not stopped; stop it first with lado stop {session}'
        )
    open_runs = [r.name for r in state.list_runs(session, open_only=True)]
    if open_runs and not force:
        raise LadoError(
            f'session "{session}" has open runs: {", ".join(open_runs)}; forget it with --force '
            "to drop them, or resume it with lado start"
        )
    worktrees = session_worktrees(sess.repo, session)
    state.delete_session(session)
    return Forgotten(open_runs, worktrees)


def session_worktrees(repo: str, session: str) -> dict[str, str]:
    """The worktrees git has for the session's workers and runs: path -> branch."""
    try:
        listed = git(repo, "worktree", "list", "--porcelain")
    except LadoError:
        return {}  # the repo is gone
    folder = str(Path(repo) / ".lado" / "worktrees" / session) + "/"
    found, path = {}, ""
    for line in listed.splitlines():
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch ") and path.startswith(folder):
            found[path] = line.removeprefix("branch refs/heads/")
    return found


def _provider(name: str) -> providers.Provider:
    try:
        return providers.get(name)
    except ValueError as exc:
        raise LadoError(str(exc)) from None


def _supervisor_instructions(env: kits.Environment, session: str) -> str:
    roles = "\n".join(f"  - {a.name}: {a.description}" for a in env.roles()) or "  (none)"
    default = env.default_agent or (kits.DEFAULT_ROLE if kits.DEFAULT_ROLE in env.agents else "")
    default_role = f' (default: "{default}")' if default else ""
    text = SUPERVISOR_INSTRUCTIONS.format(session=session, roles=roles, default_role=default_role)
    if env.flows:
        listed = "\n".join(f"  - {f.name}: {f.description}" for f in env.flows.values())
        text += FLOW_INSTRUCTIONS.format(flows=listed)
    return text


def _spec(
    agent_cli: providers.Provider,
    env: kits.Environment,
    role: str,
    agent: state.Agent,
    instructions: str,
    without: list[str] | None = None,
) -> providers.AgentSpec:
    """What `agent` is given: its role from the kits plus LADO's instructions, its skills
    and MCP servers. Fails on anything its CLI cannot do."""
    resolved = env.resolve(role, without or [])
    if resolved.skills and not agent_cli.capabilities.skills:
        raise LadoError(
            f'{agent_cli.title} cannot load skills, but agent "{agent.name}" ({role}) gets '
            f"{', '.join(resolved.skills)}; switch them off with --without skill:<name>"
        )
    return providers.AgentSpec(
        prompt=f"{resolved.agent.body}\n\n{instructions}{MESSAGING}",
        skills={name: skill.path for name, skill in resolved.skills.items()},
        mcp={"lado": providers.base.mcp_server(agent), **resolved.mcp_servers()},
    )


def _add_agent(agent: state.Agent) -> None:
    state.add_agent(agent)
    detail = f"role {agent.role}, provider {agent.provider}"
    state.add_event(agent.session, agent.name, state.SPAWNED, detail)


def _env(agent: state.Agent, launch: providers.Launch) -> dict[str, str]:
    return {**providers.agent_env(agent), **launch.env}


def _next_name(taken: set[str]) -> str:
    n = 1
    while f"w{n}" in taken:
        n += 1
    return f"w{n}"


def exclude_worktrees(repo: str) -> None:
    """Keep worker worktrees out of `git status` without touching .gitignore. The rest of
    `.lado/` (project kits) stays visible, so it can be committed."""
    exclude = Path(repo, git(repo, "rev-parse", "--git-common-dir"), "info", "exclude")
    lines = exclude.read_text().splitlines() if exclude.exists() else []
    if WORKTREES_EXCLUDE in lines and "/.lado/" not in lines:
        return
    # LADO 0.3 and earlier excluded all of .lado/.
    lines = [line for line in lines if line not in ("/.lado/", WORKTREES_EXCLUDE)]
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("\n".join([*lines, WORKTREES_EXCLUDE]) + "\n")
