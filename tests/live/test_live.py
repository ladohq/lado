"""One short scenario per real agent CLI: a worker does a tiny task, reports, gets a message
and is finished after its branch is merged."""

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
# The test merges and finishes w1 itself, so the supervisor must not: the default
# supervisor role merges what a worker reports and may then finish the worker.
PASSIVE_SUPERVISOR = """\
---
name: passive
description: Only acknowledges messages; for the live test.
supervisor: true
---
You are a passive supervisor in an automated test. When a message arrives, reply with the
single word ACK. Never use any tool: no spawn_worker, finish_worker or send_message, no
git commands, no file edits.
"""


def passive_kit(repo) -> str:
    """A project kit: the default kit's worker with a supervisor that does nothing."""
    kit = repo / ".lado" / "kits" / "live"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: live\ninclude: [default]\n")
    (kit / "agents" / "passive.md").write_text(PASSIVE_SUPERVISOR)
    return kit.name


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def status(agent: str) -> str:
    current = state.get_agent(SESSION, agent)
    if current is None:
        pytest.fail(f"agent {agent} is gone\n{agent_helpers.diagnostics(SESSION)}")
    return current.status


def messages(sender: str, recipient: str) -> list[tuple[str, str]]:
    with state.connect() as db:
        rows = db.execute(
            "SELECT text, state FROM messages "
            "WHERE session = ? AND sender = ? AND recipient = ? ORDER BY id",
            (SESSION, sender, recipient),
        ).fetchall()
    return [(r["text"], r["state"]) for r in rows]


def agent_processes(target: str = "") -> set[int]:
    """The test tmux server and every process below it: agents, hooks, MCP servers. With
    `target`, that window's process and every process below it."""
    if target:
        root = tmux.run("display-message", "-p", "-t", target, "#{pane_pid}").strip()
    else:
        root = tmux.run("display-message", "-p", "#{pid}").strip()
    table = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True)
    children: dict[int, list[int]] = {}
    for line in table.stdout.splitlines():
        pid, ppid = map(int, line.split())
        children.setdefault(ppid, []).append(pid)
    found, todo = set(), [int(root)]
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
    kit = passive_kit(repo)
    runtime.start_session(
        str(repo), SESSION, "bypassPermissions", live_provider, [kit], ["agent:supervisor"]
    )
    assert state.get_agent(SESSION, "supervisor").role == "passive"

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

    finish_worker(repo, worker)

    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "stop")
    print(f"{live_provider}: {time.monotonic() - started:.0f}s")


def finish_worker(repo, worker: state.Agent) -> None:
    """Merge w1's branch and finish w1: its processes, window, worktree and branch go."""
    runtime.git(str(repo), "merge", "-q", "--ff-only", worker.branch)
    processes = agent_processes(f"{SESSION}:w1")
    runtime.finish_worker(SESSION, "w1")
    windows = tmux.run("list-windows", "-t", f"={SESSION}", "-F", "#{window_name}").split()
    assert windows == ["supervisor"]
    assert not os.path.exists(worker.cwd)
    assert runtime.git(str(repo), "branch", "--list", worker.branch) == ""
    assert state.get_agent(SESSION, "w1") is None
    check_gone(processes, "finish_worker")
    # Hooks fired by w1 while it died, from its removed worktree, were ignored without errors.
    hooks_log = state.home() / "hooks.log"
    assert not hooks_log.exists(), hooks_log.read_text()
    # w1's late hooks add nothing after `finished`; the supervisor may still change status.
    event = [e for e in state.list_events(SESSION) if e.agent == "w1"][-1]
    assert (event.kind, event.detail) == (state.FINISHED, "merged")


def check_gone(processes: set[int], after: str) -> None:
    deadline = time.monotonic() + 30
    while (left := alive(processes)) and time.monotonic() < deadline:
        time.sleep(0.5)
    if left:
        ps = subprocess.run(
            ["ps", "-o", "pid,ppid,command", "-p", ",".join(map(str, left))],
            capture_output=True,
            text=True,
        )
        pytest.fail(f"processes left after {after}:\n{ps.stdout}")
