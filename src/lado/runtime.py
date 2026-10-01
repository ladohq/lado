"""Agent runtime: starts agents in tmux and delivers messages to them.

Each agent's provider (lado.providers) gives it its own MCP config (so the LADO MCP server
knows who is calling) and hooks (so LADO learns when the agent is busy, idle or waiting).
"""

import re
import subprocess
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
- list_agents: see the agents, their role, status, branch and worktree.
- finish_worker: once you merged a worker's branch, end that worker; its window, worktree \
and branch are removed.
Workers report back with messages that arrive in your input as "[from <name>] ...".
"""

WORKER_INSTRUCTIONS = """\
You are worker "{name}" in LADO session "{session}", working in your own git worktree on \
branch {branch}. Commit your work on that branch.
Report to your supervisor with the `lado` MCP tool send_message(to="supervisor", ...).
Messages from other agents arrive in your input as "[from <name>] ...".
"""

WORKTREES_EXCLUDE = "/.lado/worktrees/"
REPORT_REMINDER = '\n\nWhen you are done, report back with send_message(to="supervisor").'


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


def start_session(
    path: str,
    name: str | None,
    permission_mode: str | None,
    provider: str | None = None,
    kit_names: list[str] | None = None,
    without: list[str] | None = None,
) -> state.Session:
    """Start a session whose agents come from `kit_names` (default: the "default" kit), minus
    the `without` items ("agent:x", "skill:y", "mcp:z")."""
    agent_cli = _provider(provider or providers.DEFAULT)
    repo = repo_root(path)
    session = slug(name or Path(repo).name)
    if state.get_session(session):
        if tmux.has_session(session):
            raise LadoError(f'session "{session}" is already running; use `lado attach {session}`')
        state.delete_session(session)  # left over from a tmux server that is gone
    sess = state.Session(
        session,
        repo,
        permission_mode,
        agent_cli.name,
        kit_names or [kits.DEFAULT_KIT],
        without or [],
    )
    env = kits.resolve(repo, sess.kits, sess.without)
    role = env.supervisor()
    agent = state.Agent(
        session, SUPERVISOR, role.name, repo, None, None, state.STARTING, sess.provider
    )
    spec = _spec(agent_cli, env, role.name, agent, _supervisor_instructions(env, session))
    state.add_session(sess)
    _add_agent(agent)
    try:
        launch = agent_cli.launch_command(agent, sess, spec)
        tmux.new_session(session, SUPERVISOR, repo, _env(agent, launch), launch.argv)
    except tmux.TmuxError:
        state.delete_session(session)
        raise
    return sess


def spawn_worker(
    session: str,
    task: str,
    name: str | None = None,
    provider: str | None = None,
    role: str | None = None,
    without: list[str] | None = None,
) -> state.Agent:
    """Start a worker with `role` from the session's kits (default: the kits' default_agent,
    else "worker"), minus the `without` items ("skill:y", "mcp:z") for this worker."""
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    agent_cli = _provider(provider or sess.provider)
    env = kits.resolve(sess.repo, sess.kits, sess.without)
    role_def = env.worker_role(role)
    taken = {a.name for a in state.list_agents(session)}
    worker = slug(name) if name else _next_name(taken)
    if worker in taken:
        raise LadoError(f'an agent named "{worker}" already exists')
    branch = f"lado/{session}/{worker}"
    worktree = Path(sess.repo) / ".lado" / "worktrees" / session / worker
    agent = state.Agent(
        session, worker, role_def.name, str(worktree), branch, task, state.STARTING, agent_cli.name
    )
    instructions = WORKER_INSTRUCTIONS.format(name=worker, session=session, branch=branch)
    spec = _spec(agent_cli, env, role_def.name, agent, instructions, without or [])
    _exclude_worktrees(sess.repo)
    git(sess.repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
    _add_agent(agent)
    launch = agent_cli.launch_command(agent, sess, spec, first_message=task + REPORT_REMINDER)
    tmux.new_window(session, worker, str(worktree), _env(agent, launch), launch.argv)
    return agent


def finish_worker(session: str, name: str, discard: bool = False) -> state.Agent:
    """End a worker whose branch is merged: close its window, remove its worktree and branch
    and forget it, so the name can be used again. Its messages and events stay in the log.

    `discard` also ends a worker whose work is not merged or not committed, and throws that
    work away.
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
    if not discard:
        _check_finished(sess.repo, worker)
    tmux.kill_window(session, name)
    git(sess.repo, "worktree", "remove", *(["--force"] if discard else []), worker.cwd)
    git(sess.repo, "branch", "-D" if discard else "-d", worker.branch)
    state.add_event(session, name, state.FINISHED, "discarded" if discard else "merged")
    state.delete_agent(session, name)
    return worker


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


def send_message(session: str, sender: str, recipient: str, text: str) -> str:
    """Queue a message and deliver it now if the recipient is idle.

    A busy recipient gets it from its turn-end hook when its current turn ends (see lado.hooks).
    """
    if len(text) > MAX_MESSAGE:
        raise LadoError(
            f"message is {len(text)} characters, the limit is {MAX_MESSAGE}; "
            "write the details to a file and send its path"
        )
    agent = state.get_agent(session, recipient)
    if agent is None or agent.status == state.STOPPED:
        names = ", ".join(a.name for a in state.list_agents(session) if a.status != state.STOPPED)
        raise LadoError(f'no running agent "{recipient}"; running agents: {names}')
    state.queue_message(session, sender, recipient, text)
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


def format_messages(messages: list[state.Message]) -> str:
    return "\n\n".join(f"[from {m.sender}] {m.text}" for m in messages)


def stop_session(session: str) -> list[state.Agent]:
    """Kill the session's agents. Returns the workers, whose worktrees stay on disk."""
    if tmux.has_session(session):
        tmux.kill_session(session)
    workers = [a for a in state.list_agents(session) if a.name != SUPERVISOR]
    state.delete_session(session)
    return workers


def _provider(name: str) -> providers.Provider:
    try:
        return providers.get(name)
    except ValueError as exc:
        raise LadoError(str(exc)) from None


def _supervisor_instructions(env: kits.Environment, session: str) -> str:
    roles = "\n".join(f"  - {a.name}: {a.description}" for a in env.roles()) or "  (none)"
    default = env.default_agent or (kits.DEFAULT_ROLE if kits.DEFAULT_ROLE in env.agents else "")
    default_role = f' (default: "{default}")' if default else ""
    return SUPERVISOR_INSTRUCTIONS.format(session=session, roles=roles, default_role=default_role)


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
        prompt=f"{resolved.agent.body}\n\n{instructions}",
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


def _exclude_worktrees(repo: str) -> None:
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
