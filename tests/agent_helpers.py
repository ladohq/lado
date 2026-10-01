"""Helpers for tests that run real agent processes: integration (fake agent) and live tests."""

import re
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from lado import state, tmux


def init_repo(path: Path) -> Path:
    """A git repo with one empty commit on main, and a committer for agents that commit."""
    path.mkdir(parents=True)
    git = ["git", "-C", str(path)]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "config", "user.name", "LADO test"], check=True)
    subprocess.run([*git, "config", "user.email", "test@lado.invalid"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return path


def refuse_unless_isolated() -> None:
    """These tests start and kill tmux servers and agents: never let them near a live LADO."""
    home = state.home().resolve()
    if not home.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        pytest.exit(f"agent tests need LADO_HOME in a temp dir, not {home}", returncode=2)
    if not re.fullmatch(r"lado-test-[0-9a-f]{8}", tmux.socket()):
        pytest.exit(f"agent tests need a test tmux socket, not {tmux.socket()}", returncode=2)


def wait_for(check, what: str, session: str, timeout: float = 10, interval: float = 0.05):
    """Poll `check` until it returns something true, and return that."""
    deadline = time.monotonic() + timeout
    while not (result := check()):
        if time.monotonic() > deadline:
            pytest.fail(f"timed out waiting for {what}\n{diagnostics(session)}")
        time.sleep(interval)
    return result


def diagnostics(session: str) -> str:
    """The agents' windows, the hook log and the messages, to see why a wait failed."""
    out = []
    for agent in state.list_agents(session):
        out.append(f"--- {agent.name} ({agent.status})")
        try:
            out.append(tmux.capture(session, agent.name).rstrip())
        except tmux.TmuxError as exc:
            out.append(str(exc))
    log = state.home() / "hooks.log"
    if log.exists():
        out += ["--- hooks.log", log.read_text()]
    with state.connect() as db:
        rows = db.execute(
            "SELECT sender, recipient, state, text FROM messages WHERE session = ? ORDER BY id",
            (session,),
        ).fetchall()
    out.append("--- messages")
    out += [f"{r['sender']} -> {r['recipient']} [{r['state']}] {r['text'][:200]!r}" for r in rows]
    return "\n".join(out)
