"""Agent runtime: starts Claude Code agents in tmux and delivers messages to them.

Each agent gets its own MCP config (so the LADO MCP server knows who is calling) and its
own settings with hooks (so LADO learns when the agent is busy, idle or waiting).
"""

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from lado import state, tmux

SUPERVISOR = "supervisor"
WORKER = "worker"
MAX_MESSAGE = 8000
CONFIRM_TIMEOUT = 15  # seconds for a typed message to show up as a prompt

SUPERVISOR_PROMPT = """\
You are the supervisor of LADO session "{session}". The human talks to you in this window.
You coordinate worker agents. Each worker is a separate Claude Code instance with its own \
git worktree and branch, created from your current HEAD.

Use the `lado` MCP tools:
- spawn_worker: hand a well-scoped, self-contained task to a new worker. Include the goal, \
the relevant files and how to check the result.
- send_message: talk to a worker, e.g. to answer its question.
- list_agents: see workers, their status, branch and worktree path.

Delegate implementation work to workers instead of doing it yourself. Workers report back \
with messages that arrive in your input as "[from <name>] ...". When a worker reports that \
it is done, review its branch and merge it into your branch.
"""

WORKER_PROMPT = """\
You are worker "{name}" in LADO session "{session}". Your supervisor gave you a task.
You work in your own git worktree on branch {branch}. Commit your work on that branch.
When you finish, or if you are blocked, report to your supervisor with the `lado` MCP tool \
send_message(to="supervisor", ...): a short summary, the branch, and anything they must check.
Messages from other agents arrive in your input as "[from <name>] ...".
"""

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


def lado_command(*args: str) -> list[str]:
    # The same interpreter that runs this code, so agents use the same LADO install.
    return [sys.executable, "-m", "lado.cli", *args]


def start_session(path: str, name: str | None, permission_mode: str | None) -> state.Session:
    repo = repo_root(path)
    session = slug(name or Path(repo).name)
    if state.get_session(session):
        if tmux.has_session(session):
            raise LadoError(f'session "{session}" is already running; use `lado attach {session}`')
        state.delete_session(session)  # left over from a tmux server that is gone
    sess = state.Session(session, repo, permission_mode)
    state.add_session(sess)
    agent = state.Agent(session, SUPERVISOR, SUPERVISOR, repo, None, None, state.STARTING)
    state.add_agent(agent)
    prompt = SUPERVISOR_PROMPT.format(session=session)
    try:
        tmux.new_session(session, SUPERVISOR, repo, _env(agent), _claude(sess, agent, prompt))
    except tmux.TmuxError:
        state.delete_session(session)
        raise
    return sess


def spawn_worker(session: str, task: str, name: str | None = None) -> state.Agent:
    sess = state.get_session(session)
    if sess is None:
        raise LadoError(f'unknown session "{session}"')
    taken = {a.name for a in state.list_agents(session)}
    worker = slug(name) if name else _next_name(taken)
    if worker in taken:
        raise LadoError(f'an agent named "{worker}" already exists')
    branch = f"lado/{session}/{worker}"
    worktree = Path(sess.repo) / ".lado" / "worktrees" / session / worker
    _exclude_lado_dir(sess.repo)
    git(sess.repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
    agent = state.Agent(session, worker, WORKER, str(worktree), branch, task, state.STARTING)
    state.add_agent(agent)
    prompt = WORKER_PROMPT.format(name=worker, session=session, branch=branch)
    cmd = _claude(sess, agent, prompt, first_message=task + REPORT_REMINDER)
    tmux.new_window(session, worker, str(worktree), _env(agent), cmd)
    return agent


def send_message(session: str, sender: str, recipient: str, text: str) -> str:
    """Queue a message and deliver it now if the recipient is idle.

    A busy recipient gets it from its Stop hook when its current turn ends (see lado.hooks).
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
    # Queue first, read the status second: the Stop hook does the reverse, so a message is
    # never left behind by an agent that went idle in between.
    status = state.get_agent(session, recipient).status
    if status != state.IDLE and not lost:
        return f"queued; {recipient} is {status} and will get it when its turn ends"
    return "sent" if deliver_pending(session, recipient) else "queued"


def deliver_pending(session: str, recipient: str) -> bool:
    """Type the recipient's pending messages into its window. They stay "sent" until its
    UserPromptSubmit hook confirms them."""
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
    workers = [a for a in state.list_agents(session) if a.role == WORKER]
    state.delete_session(session)
    return workers


def _next_name(taken: set[str]) -> str:
    n = 1
    while f"w{n}" in taken:
        n += 1
    return f"w{n}"


def _exclude_lado_dir(repo: str) -> None:
    """Keep `.lado/` (worker worktrees) out of `git status` without touching .gitignore."""
    exclude = Path(repo, git(repo, "rev-parse", "--git-common-dir"), "info", "exclude")
    lines = exclude.read_text().splitlines() if exclude.exists() else []
    if "/.lado/" not in lines:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("\n".join([*lines, "/.lado/"]) + "\n")


def _env(agent: state.Agent) -> dict[str, str]:
    return {
        "LADO_HOME": str(state.home()),
        "LADO_SESSION": agent.session,
        "LADO_AGENT": agent.name,
    }


def _claude(
    sess: state.Session, agent: state.Agent, prompt: str, first_message: str | None = None
) -> list[str]:
    config_dir = state.home() / "agents" / agent.session / agent.name
    config_dir.mkdir(parents=True, exist_ok=True)
    env = _env(agent)

    mcp_config = config_dir / "mcp.json"
    server = lado_command("mcp")
    mcp = {"mcpServers": {"lado": {"command": server[0], "args": server[1:], "env": env}}}
    mcp_config.write_text(json.dumps(mcp, indent=2))

    def hook(event: str) -> list[dict]:
        command = lado_command(
            "hook",
            event,
            "--session",
            agent.session,
            "--agent",
            agent.name,
            "--instance",
            agent.instance,
        )
        return [{"hooks": [{"type": "command", "command": shlex.join(command)}]}]

    settings = config_dir / "settings.json"
    events = ("SessionStart", "UserPromptSubmit", "Stop", "Notification", "SessionEnd")
    settings.write_text(json.dumps({"hooks": {e: hook(e) for e in events}}, indent=2))

    cmd = [
        "claude",
        "--mcp-config",
        str(mcp_config),
        "--settings",
        str(settings),
        "--append-system-prompt",
        prompt,
    ]
    if sess.permission_mode:
        cmd += ["--permission-mode", sess.permission_mode]
    if first_message:
        cmd += ["--", first_message]
    return cmd
