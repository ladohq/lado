"""Agents talking through LADO for real: tmux, git, hooks and the MCP server as processes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "itest"


def wait_for(check, what: str, timeout: float = 10):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def status(agent: str) -> str:
    return state.get_agent(SESSION, agent).status


def wait_status(agent: str, expected: str) -> None:
    wait_for(lambda: status(agent) == expected, f"{agent} to be {expected}")


def inputs(agent: str) -> list[str]:
    """What the fake agent got as input, in order."""
    log = state.home() / "agents" / SESSION / agent / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def message_states(recipient: str) -> list[str]:
    with state.connect() as db:
        rows = db.execute(
            "SELECT state FROM messages WHERE session = ? AND recipient = ? ORDER BY id",
            (SESSION, recipient),
        ).fetchall()
    return [r["state"] for r in rows]


def start(repo: Path, provider: str = "fake") -> None:
    runtime.start_session(str(repo), SESSION, None, provider)
    wait_status("supervisor", state.IDLE)


def test_supervisor_starts_and_becomes_idle(repo):
    runtime.start_session(str(repo), SESSION, None, "fake")
    assert status("supervisor") == state.STARTING
    wait_status("supervisor", state.IDLE)
    assert tmux.has_session(SESSION)


def test_message_to_idle_agent_is_pasted_and_confirmed(repo):
    start(repo)
    assert runtime.send_message(SESSION, "human", "supervisor", "hello\nthere") == "sent"
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED], "delivery")
    wait_status("supervisor", state.IDLE)
    assert inputs("supervisor") == ["[from human] hello\nthere"]  # one paste, one input


@pytest.mark.parametrize("provider", ["fake", "fake-paste"])
def test_message_to_busy_agent_arrives_when_its_turn_ends(repo, provider):
    start(repo, provider)
    assert runtime.send_message(SESSION, "human", "supervisor", "sleep 1") == "sent"
    reply = runtime.send_message(SESSION, "human", "supervisor", "hello")
    assert reply.startswith("queued; supervisor is busy")
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED] * 2, "delivery")
    wait_status("supervisor", state.IDLE)
    assert inputs("supervisor") == ["[from human] sleep 1", "[from human] hello"]


def test_spawned_worker_reports_back_to_supervisor(repo):
    start(repo)
    runtime.send_message(SESSION, "human", "supervisor", "spawn send supervisor finished")
    wait_for(lambda: "[from w1] finished" in inputs("supervisor"), "the report", timeout=20)
    worker = state.get_agent(SESSION, "w1")
    assert (worker.branch, worker.task) == ("lado/itest/w1", "send supervisor finished")
    assert Path(worker.cwd, ".git").exists()
    runtime.git(str(repo), "rev-parse", "--verify", "lado/itest/w1")
    assert inputs("w1")[0].startswith("send supervisor finished\n")
    wait_status("w1", state.IDLE)
    wait_status("supervisor", state.IDLE)


def test_stop_kills_agents_and_keeps_worktrees(repo):
    start(repo)
    worker = runtime.spawn_worker(SESSION, "sleep 0")
    wait_status("w1", state.IDLE)
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "stop", SESSION],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"kept worktree {worker.cwd}" in result.stdout
    assert not tmux.has_session(SESSION)
    assert state.get_session(SESSION) is None
    assert Path(worker.cwd, ".git").exists()
