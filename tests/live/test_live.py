"""Two short scenarios per real agent CLI: a worker does a tiny task, reports, gets a message
and is finished after its branch is merged; and a flow run's worker does its step and
reports the outcome, which ends the run."""

import json
import os
import subprocess
import sys
import time

import agent_helpers
import pytest

from lado import providers, runs, runtime, state, tmux
from lado.providers import base

pytestmark = pytest.mark.live

SESSION = "live"
TASK = (
    "Create a file hello.txt containing exactly OK, commit it on your branch, "
    "then report to the supervisor with send_message. Do nothing else."
)
RECEIVED = (state.DELIVERED, state.READ)
CLAUDE_TRUST = "Yes, I trust this folder"
# The follow-up has a body, so w1 must call read_messages to get it.
FOLLOW_UP = "Thanks, one last note for you"
FOLLOW_UP_BODY = (
    "Nothing more to do. Reply with the single word ACK and do not use any other tools."
)
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


# One worker step, then the end. The test plays the supervisor's part (start the run, spawn
# its worker) itself; the worker reports the outcome with flow_advance.
TINY_FLOW = """\
name: tiny
description: One worker step, then the end; for the live test.
start: step
states:
  step:
    agent: worker
    do: >-
      Create a file flow.txt containing exactly OK and commit it on your branch. Then call
      flow_advance with the outcome done. Do nothing else.
    outcomes: {done: end}
  end:
    end: true
"""


def passive_kit(repo) -> str:
    """A project kit: the default kit's worker with a supervisor that does nothing, and the
    flow `tiny`."""
    kit = repo / ".lado" / "kits" / "live"
    (kit / "agents").mkdir(parents=True)
    (kit / "flows").mkdir()
    (kit / "kit.yaml").write_text("name: live\ninclude: [default]\n")
    (kit / "agents" / "passive.md").write_text(PASSIVE_SUPERVISOR)
    (kit / "flows" / "tiny.yaml").write_text(TINY_FLOW)
    return kit.name


def start_session(repo, provider: str) -> None:
    """Start the session with the passive supervisor and wait until it is idle."""
    kit = passive_kit(repo)
    runtime.start_session(
        str(repo), SESSION, "bypassPermissions", provider, [kit], ["agent:supervisor"]
    )
    assert state.get_agent(SESSION, "supervisor").role == "passive"

    def supervisor_idle() -> bool:
        if status("supervisor") == state.IDLE:
            return True
        answer_dialogs(provider, SESSION, "supervisor")
        return False

    wait_for(supervisor_idle, "the supervisor to be idle", 60)


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def status(agent: str) -> str:
    current = state.get_agent(SESSION, agent)
    if current is None:
        pytest.fail(f"agent {agent} is gone\n{agent_helpers.diagnostics(SESSION)}")
    return current.status


def messages(sender: str, recipient: str) -> list[tuple[str, str]]:
    """(summary, state) of each message from `sender` to `recipient`."""
    return [
        (m.summary, m.state)
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient) == (sender, recipient)
    ]


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


def check_report() -> str:
    """w1 reported with a one-line summary, which reached the supervisor. The passive
    supervisor may or may not read the body."""
    report = next(m for m in state.list_messages(SESSION) if m.sender == "w1")
    print(f"report: {report.summary!r}, body: {report.body!r}, {report.state}")
    assert report.summary and "\n" not in report.summary
    assert report.state in RECEIVED
    return report.summary


def check_log(provider: str, summary: str) -> None:
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
    assert any(f"w1 → supervisor [{s}] {summary}" in lines for s in RECEIVED)
    assert f"supervisor → w1 [read] {FOLLOW_UP}" in lines
    assert f"    {FOLLOW_UP_BODY}" in result.stdout.splitlines()


def claude_tools(repo, settings: str, permission_mode: str) -> list[str]:
    """The tools a Claude Code agent with these settings sees, from the CLI's init event."""
    model = providers.get("claude").model  # the test model, see conftest.with_model
    cmd = ["claude", "-p", "Reply OK.", "--settings", settings, "--model", model]
    cmd += ["--permission-mode", permission_mode, "--output-format", "stream-json", "--verbose"]
    out, no_input = subprocess.PIPE, subprocess.DEVNULL
    with subprocess.Popen(cmd, cwd=repo, stdin=no_input, stdout=out, text=True) as proc:
        try:
            for line in proc.stdout:
                event = json.loads(line)
                if (event.get("type"), event.get("subtype")) == ("system", "init"):
                    return event["tools"]
        finally:
            proc.kill()
    pytest.fail("claude printed no init event")


def check_agent_config(provider: str, repo, worker: state.Agent) -> None:
    """Claude Code: w1 does not see Claude Code's own tools for messaging agents, only
    LADO's send_message, which carried its report."""
    if provider == "claude":
        # Without w1's hooks: they would report this probe's session as w1's.
        settings = json.loads((base.config_dir(worker) / "settings.json").read_text())
        probe = repo.parent / "probe-settings.json"
        probe.write_text(json.dumps({"permissions": settings["permissions"]}))
        mode = state.get_session(SESSION).permission_mode
        tools = claude_tools(repo, str(probe), mode)
        assert "Read" in tools
        assert not {"SendMessage", "ListAgents"} & set(tools), tools


def cli_version(provider: str) -> str:
    command = providers.get(provider).command
    return subprocess.run([command, "--version"], capture_output=True, text=True).stdout


def test_worker_does_a_task_reports_and_gets_a_message(live_repo, live_provider):
    repo = live_repo
    started = time.monotonic()
    version = cli_version(live_provider)
    start_session(repo, live_provider)

    worker = runtime.spawn_worker(SESSION, TASK, name="w1")
    wait_for(lambda: status("w1") == state.BUSY, "w1 to be busy", 60)
    wait_for(lambda: messages("w1", "supervisor"), "w1's report", 240)
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle", 60)
    wait_for(
        lambda: messages("w1", "supervisor")[0][1] in RECEIVED,
        "w1's report to be delivered",
        60,
    )
    summary = check_report()

    hello = runtime.git(str(repo), "show", f"{worker.branch}:hello.txt")
    assert hello.strip() == "OK"
    check_agent_config(live_provider, repo, worker)

    runtime.send_message(SESSION, "supervisor", "w1", FOLLOW_UP, FOLLOW_UP_BODY)
    wait_for(
        lambda: (FOLLOW_UP, state.READ) in messages("supervisor", "w1"),
        "w1 to read the follow-up with read_messages",
        120,
    )
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle after the follow-up", 120)
    check_log(live_provider, summary)

    finish_worker(repo, worker)

    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "stop")
    check_resume(live_provider, repo)
    # Kilo updates itself unless told not to; LADO's agents must not (the Kilo provider
    # switches it off, so the test needs no KILO_DISABLE_AUTOUPDATE from outside).
    if live_provider == "kilo":
        assert cli_version(live_provider) == version
    print(f"{live_provider}: {time.monotonic() - started:.0f}s")


def check_resume(provider: str, repo) -> None:
    """`lado start` again: the stopped session resumes, and the new supervisor's first input
    is LADO's resume message, given on its command line. Then stop it for good."""
    started = runtime.start_session(str(repo), SESSION, None)
    assert (started.resumed, started.changes, started.problems) == (True, [], [])
    resumed = "[from lado] session resumed: 0 open runs"
    assert state.get_agent(SESSION, "supervisor").task == resumed
    resume_event = state.list_events(SESSION)[-2]
    assert resume_event.kind == state.SESSION_RESUME

    def answered() -> bool:
        answer_dialogs(provider, SESSION, "supervisor")
        idle = [
            e
            for e in state.list_events(SESSION, resume_event.id)
            if (e.agent, e.kind, e.detail) == ("supervisor", state.STATUS, state.IDLE)
        ]
        return bool(idle) and resumed in tmux.capture(SESSION, "supervisor")

    wait_for(answered, "the supervisor to take the resume message", 120)
    ls = subprocess.run(
        [sys.executable, "-m", "lado.cli", "ls"], capture_output=True, text=True, env=os.environ
    )
    listed = f"{SESSION}  {started.session.repo}\n"
    assert listed in ls.stdout and "(stopped)" not in ls.stdout, ls.stdout
    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "the stop after the resume")
    assert not (state.home() / "hooks.log").exists()


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


def test_a_flow_run_moves_on_when_its_worker_reports(live_repo, live_provider):
    """The run's worker gets its step as its task, does it and reports the outcome with
    flow_advance; the run ends. Its branch is not merged yet, so LADO keeps the worktree,
    the branch and the worker and tells the supervisor; finishing the worker after the
    merge removes them."""
    repo = live_repo
    started = time.monotonic()
    start_session(repo, live_provider)

    run = runs.start(SESSION, "tiny", "Add flow.txt for the live test.")
    worker = runs.spawn_worker(SESSION, run.name, name="w1")
    assert worker.task.startswith(f"Run {run.name} (flow tiny), step step.")
    assert worker.cwd == run.worktree

    ended = wait_for(
        lambda: (r := state.get_run(SESSION, run.name)).status == state.ENDED and r,
        "the run to end",
        240,
    )
    assert ended.state == "end"
    moves = [(e.agent, e.detail) for e in state.list_events(SESSION) if e.kind == state.FLOW]
    assert moves == [("w1", "step -done-> end")]
    assert runtime.git(str(repo), "show", f"{run.branch}:flow.txt").strip() == "OK"
    kept = f"flow {run.name}: ended at end; kept its worktree and branch"
    assert kept in [summary for summary, _ in messages(state.LADO, "supervisor")]
    assert state.get_agent(SESSION, "w1") is not None
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle", 120)

    # The human merges; finishing the run's last worker takes the worktree and branch.
    runtime.git(str(repo), "merge", "-q", "--ff-only", run.branch)
    processes = agent_processes(f"{SESSION}:w1")
    runtime.finish_worker(SESSION, "w1")
    assert not os.path.exists(run.worktree)
    assert runtime.git(str(repo), "branch", "--list", run.branch) == ""
    assert state.get_agent(SESSION, "w1") is None
    check_gone(processes, "finish_worker")

    processes = agent_processes()
    runtime.stop_session(SESSION)
    check_gone(processes, "stop")
    hooks_log = state.home() / "hooks.log"
    assert not hooks_log.exists(), hooks_log.read_text()
    print(f"{live_provider} flow: {time.monotonic() - started:.0f}s")
