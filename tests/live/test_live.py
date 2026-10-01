"""One short scenario per real agent CLI: a worker does a tiny task, reports and gets a message."""

import os
import subprocess
import sys
import time

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.live

SESSION = "live"
TASK = (
    "Create a file hello.txt containing exactly OK, commit it on your branch, "
    "then report to the supervisor with send_message. Do nothing else."
)
CLAUDE_TRUST = "Yes, I trust this folder"
FOLLOW_UP = "Thanks, nothing more to do. Reply with the single word ACK and do not use any tools."


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def status(agent: str) -> str:
    return state.get_agent(SESSION, agent).status


def messages(sender: str, recipient: str) -> list[tuple[str, str]]:
    with state.connect() as db:
        rows = db.execute(
            "SELECT text, state FROM messages "
            "WHERE session = ? AND sender = ? AND recipient = ? ORDER BY id",
            (SESSION, sender, recipient),
        ).fetchall()
    return [(r["text"], r["state"]) for r in rows]


def agent_processes() -> set[int]:
    """The test tmux server and every process below it: agents, hooks, MCP servers."""
    server = tmux.run("display-message", "-p", "#{pid}").strip()
    table = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True)
    children: dict[int, list[int]] = {}
    for line in table.stdout.splitlines():
        pid, ppid = map(int, line.split())
        children.setdefault(ppid, []).append(pid)
    found, todo = set(), [int(server)]
    while todo:
        pid = todo.pop()
        found.add(pid)
        todo += children.get(pid, [])
    return found


def alive(pids: set[int]) -> set[int]:
    living = set()
    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            pass
        living.add(pid)
    return living


def answer_dialogs(provider: str, session: str, window: str) -> None:
    """Answer the dialogs a human answers once per repo, before the agent can start."""
    if provider == "claude" and CLAUDE_TRUST in tmux.capture(session, window):
        tmux.run("send-keys", "-t", f"{session}:{window}", "Down", "Enter")


def check_log(provider: str) -> None:
    """`lado log` shows w1's spawn, its statuses and its report, in that order."""
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "log", SESSION, "--agent", "w1"],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    print(result.stdout)
    lines = [line.split(" ", 1)[1] for line in result.stdout.splitlines() if line[:1] != " "]
    assert lines[0].startswith("w1: spawned (role ")
    assert lines[0].endswith(f", provider {provider})")
    assert lines.index("w1: busy") < len(lines) - 1 - lines[::-1].index("w1: idle")
    assert any(line.startswith("w1 → supervisor [delivered]") for line in lines)


def test_worker_does_a_task_reports_and_gets_a_message(live_repo, live_provider):
    repo = live_repo
    started = time.monotonic()
    runtime.start_session(str(repo), SESSION, "bypassPermissions", live_provider)

    def supervisor_idle() -> bool:
        if status("supervisor") == state.IDLE:
            return True
        answer_dialogs(live_provider, SESSION, "supervisor")
        return False

    wait_for(supervisor_idle, "the supervisor to be idle", 60)

    worker = runtime.spawn_worker(SESSION, TASK, name="w1")
    wait_for(lambda: status("w1") == state.BUSY, "w1 to be busy", 60)
    wait_for(lambda: messages("w1", "supervisor"), "w1's report", 240)
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle", 60)

    hello = runtime.git(str(repo), "show", f"{worker.branch}:hello.txt")
    assert hello.strip() == "OK"

    runtime.send_message(SESSION, "supervisor", "w1", FOLLOW_UP)
    wait_for(
        lambda: (FOLLOW_UP, state.DELIVERED) in messages("supervisor", "w1"),
        "the follow-up to be delivered",
        60,
    )
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle after the follow-up", 120)
    check_log(live_provider)

    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    deadline = time.monotonic() + 30
    while (left := alive(processes)) and time.monotonic() < deadline:
        time.sleep(0.5)
    if left:
        ps = subprocess.run(
            ["ps", "-o", "pid,ppid,command", "-p", ",".join(map(str, left))],
            capture_output=True,
            text=True,
        )
        pytest.fail(f"processes left after stop:\n{ps.stdout}")
    print(f"{live_provider}: {time.monotonic() - started:.0f}s")
