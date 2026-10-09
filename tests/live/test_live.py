"""Two short scenarios per real agent CLI: a worker does a tiny task, reports, gets a message
and is finished after its branch is merged; and a flow run's worker does its step and
reports the outcome, which ends the run."""

import json
import os
import re
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import agent_helpers
import pytest

from lado import artifacts, loop, providers, runs, runtime, state, terminal, tmux
from lado.providers import base

pytestmark = pytest.mark.live

SESSION = "live"
TASK = (
    "Create a file hello.txt containing exactly OK and a file report.md containing exactly "
    "REPORT, and commit both on your branch. Keep report.md as an artifact with "
    'write_artifact(name="report", file="report.md"). Then report to the supervisor with '
    'send_message, attaching it with artifacts=["report"]. Do nothing else.'
)
RECEIVED = (state.DELIVERED, state.READ)
CLAUDE_TRUST = "Yes, I trust this folder"
CODEX_TRUST = "Trust this folder?"
# The follow-up has a body, so w1 must call read_messages to get it.
FOLLOW_UP = "Thanks, one last note for you"
FOLLOW_UP_BODY = (
    "Nothing more to do. Reply with the single word ACK and do not use any other tools."
)
# Sent while w1 works on the follow-up: it goes in w1's turn-end hook's output.
WHILE_BUSY = "No reply needed to this line"
# The test merges and finishes w1 itself, so the supervisor must not: the default
# supervisor role merges what a worker reports and may then finish the worker.
PASSIVE_SUPERVISOR = """\
---
name: passive
description: Only acknowledges messages; for the live test.
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


# The passive supervisor's MCP server: it writes the token it got next to itself, then
# answers as an MCP server with no tools, so the CLI keeps it.
TOKEN_SERVER = """\
import json, os, pathlib, sys
pathlib.Path(sys.argv[0]).with_name("mcp-token").write_text(os.environ.get("TOKEN", ""))
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    result = {}
    if request["method"] == "initialize":
        version = request["params"].get("protocolVersion", "2024-11-05")
        info = {"name": "token", "version": "1"}
        result = {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": info}
    elif request["method"] == "tools/list":
        result = {"tools": []}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
"""
MCP_TOKEN = "live-s3cr3t"


def passive_kit(repo, token_server: bool) -> str:
    """A project kit: the default kit's worker with a supervisor that does nothing, and the
    flow `tiny`. With `token_server` the supervisor has an MCP server whose env refers to
    LIVE_MCP_TOKEN."""
    kit = repo / ".lado" / "kits" / "live"
    (kit / "agents").mkdir(parents=True)
    (kit / "flows").mkdir()
    (kit / "kit.yaml").write_text("name: live\nversion: 1.0.0\nsupervisor: passive\n")
    passive = PASSIVE_SUPERVISOR
    if token_server:
        command = f"[{json.dumps(sys.executable)}, '${{KIT_DIR}}/token.py']"
        mcp = f"mcp:\n  token:\n    command: {command}\n    env: {{TOKEN: '${{LIVE_MCP_TOKEN}}'}}\n"
        passive = passive.replace("---\nYou", f"{mcp}---\nYou")
        (kit / "token.py").write_text(TOKEN_SERVER)
    (kit / "agents" / "passive.md").write_text(passive)
    (kit / "flows" / "tiny.yaml").write_text(TINY_FLOW)
    return kit.name


def check_mcp_token(repo) -> None:
    """The kit's MCP server got LIVE_MCP_TOKEN from the agent's environment, through
    lado.mcp_exec: the config holds only its name."""
    got = repo / ".lado" / "kits" / "live" / "mcp-token"
    wait_for(lambda: got.exists() and got.read_text() == MCP_TOKEN, "the MCP server's token", 60)
    configs = state.home() / "agents" / SESSION
    token = MCP_TOKEN.encode()
    assert [p for p in configs.rglob("*") if p.is_file() and token in p.read_bytes()] == []


def start_session(repo, provider: str, monkeypatch=None) -> None:
    """Start the session with the passive supervisor and wait until it is idle. With
    `monkeypatch` the supervisor has the token server, and the token is checked."""
    if monkeypatch:
        monkeypatch.setenv("LIVE_MCP_TOKEN", MCP_TOKEN)
    kit = passive_kit(repo, token_server=bool(monkeypatch))
    # The default kit's supervisor is switched off in its kit only, so the live kit's leads.
    started = runtime.start_session(
        str(repo),
        SESSION,
        "bypassPermissions",
        provider,
        ["default", kit],
        ["agent:supervisor@default"],
    )
    assert started.lead == "lead: passive of kit live"
    assert state.get_agent(SESSION, "supervisor").role == "passive"
    if provider == "claude" and not any("whether to trust" in w for w in started.warnings):
        # The fixed repo path is trusted from an earlier run: no dialog to check.
        print("Claude Code trusts the repo already: the wait for its trust dialog is not checked")

    def supervisor_idle() -> bool:
        if status("supervisor") == state.IDLE:
            return True
        answer_dialogs(provider, SESSION, "supervisor")
        return False

    wait_for(supervisor_idle, "the supervisor to be idle", 60)
    assert loop.running(SESSION)
    if monkeypatch:
        check_mcp_token(repo)


def check_loop_ended() -> None:
    """The session loop ends by itself after `lado stop`, within a few passes."""
    wait_for(lambda: not loop.running(SESSION), "the session loop to end", 5 * loop.INTERVAL)
    agent_helpers.check_loop_ended_by_stop(SESSION)


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def status(agent: str) -> str:
    current = state.get_agent(SESSION, agent)
    if current is None:
        pytest.fail(f"agent {agent} is gone\n{agent_helpers.diagnostics(SESSION)}")
    return current.status


def check_first_input(recipient: str, summary: str) -> None:
    """The agent's first input, a message from LADO through its queue (no part of its
    command line), was handed over once and taken at the first attempt: a hand-over from
    its session-start hook works with this CLI. Its line can show on the agent's screen
    before the prompt-submit hook confirms it, so wait until it is no longer on its way
    (pending or sent)."""

    def settled() -> state.Message | None:
        [first] = [
            m
            for m in state.list_messages(SESSION)
            if (m.sender, m.recipient, m.summary) == (state.LADO, recipient, summary)
        ]
        return first if first.state not in (state.PENDING, state.SENT) else None

    first = wait_for(settled, f"{recipient}'s first input {summary!r} to be confirmed", 120)
    assert (first.state, first.attempts) in [(s, 1) for s in RECEIVED], (
        f"{recipient}'s first input {summary!r}: {first.state} after {first.attempts} attempts"
    )


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
    """Answer the dialogs a human answers once per repo, before the agent can start. The
    first time, the agent (named as its window) waits for the human and says why: LADO saw
    the trust dialog coming (Provider.first_hook_blocker)."""
    if provider == "claude" and CLAUDE_TRUST in tmux.capture(session, window):
        if (session, window) not in TRUST_ASKED:
            TRUST_ASKED.add((session, window))
            assert status(window) == state.WAITING
            reason = runtime.status_reason(session, window) or ""
            assert reason.startswith("Claude Code asks whether to trust "), reason
        tmux.run("send-keys", "-t", f"{session}:{window}", "Down", "Enter")
    if provider == "codex" and CODEX_TRUST in tmux.capture(session, window):
        if (session, window) not in TRUST_ASKED:
            TRUST_ASKED.add((session, window))
            assert status(window) == state.WAITING
            reason = runtime.status_reason(session, window) or ""
            assert reason.startswith("Codex CLI asks whether to trust "), reason
        # "Trust and continue" is the first choice; the prompt on its command line follows.
        tmux.run("send-keys", "-t", f"{session}:{window}", "Enter")


TRUST_ASKED: set[tuple[str, str]] = set()  # the agents answer_dialogs checked


def answering(provider: str, agent: str, check):
    """`check` for wait_for, answering the agent's dialogs first: each Codex agent has a
    new home, so a worker asks about the folder too (Claude Code's trusts it by then)."""

    def answered():
        answer_dialogs(provider, SESSION, agent)
        return check()

    return answered


def check_report() -> str:
    """w1 reported with a one-line summary, which reached the supervisor. The passive
    supervisor may or may not read the body."""
    report = next(m for m in state.list_messages(SESSION) if m.sender == "w1")
    print(f"report: {report.summary!r}, body: {report.body!r}, {report.state}")
    assert report.summary and "\n" not in report.summary
    assert report.state in RECEIVED
    return report.summary


def check_artifact() -> None:
    """w1 kept report.md as the artifact "report" by its path relative to its worktree (read
    by its own `lado mcp`), and attached it to its report."""
    artifact, record = artifacts.find(SESSION, "report")
    content = artifacts.content(record)
    print(f"artifact: {artifact.full_name}, {record.media_type}, {content!r}")
    assert (record.author, record.media_type) == ("w1", "text/markdown")
    assert content.decode().strip() == "REPORT"
    report = next(m for m in state.list_messages(SESSION) if m.sender == "w1")
    assert [a for a, _ in state.message_attachments(report.id)] == [artifact.id]


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


def check_no_snapshots(provider: str, repo) -> None:
    """Kilo and OpenCode: the agents took no snapshots of the repo. Both keep them in
    <data>/snapshot/<project id>/ and the project id in the repo's .git/<command> (Kilo 7.8.1,
    OpenCode 1.18.34); on a slow repo their setup stops the agent on a question for the
    human."""
    if provider not in ("kilo", "opencode"):
        return
    paths = subprocess.run(
        [provider, "debug", "paths"], capture_output=True, text=True, check=True
    ).stdout
    [data] = [line.split(None, 1)[1] for line in paths.splitlines() if line.startswith("data ")]
    project = (repo / ".git" / provider).read_text().strip()
    snapshots = Path(data) / "snapshot" / project
    assert not snapshots.exists(), f"{provider} took snapshots: {snapshots}"


LADO_TOOLS = {"mcp__lado__flow_advance", "mcp__lado__send_message", "mcp__lado__read_messages"}


def claude_transcripts(cwd: str, since: float) -> list[list[dict]]:
    """The Claude Code transcripts (one per conversation) of an agent in `cwd`, written
    since `since` (a time.time()). Claude Code keeps them in its config folder under
    projects/<the real path of cwd, each character other than a letter or digit a "-">."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    folder = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd))
    files = [f for f in folder.glob("*.jsonl") if f.stat().st_mtime >= since]
    return [[json.loads(line) for line in f.read_text().splitlines() if line] for f in files]


def check_lado_tools_loaded(provider: str, cwd: str, since: float) -> None:
    """Claude Code: the tools sent with w1's first turn include LADO's, and none of them is
    deferred behind ToolSearch, which happens to the tools of an MCP server that connects
    after the first turn has started (see providers/claude.py). The CLI's init event can
    not tell: it lists deferred tools too."""
    if provider != "claude":
        return

    def first_tools() -> list[str] | None:
        for transcript in claude_transcripts(cwd, since):
            for entry in transcript:
                attachment = entry.get("attachment") or {}
                if attachment.get("type") == "prompt_snapshot" and "tools" in attachment:
                    return [t["name"] for t in attachment["tools"]]
        return None

    tools = wait_for(first_tools, "w1's first turn in its transcript", 120)
    deferred = {
        name
        for transcript in claude_transcripts(cwd, since)
        for entry in transcript
        if (entry.get("attachment") or {}).get("type") == "deferred_tools_delta"
        for name in entry["attachment"].get("addedNames", [])
        if name.startswith("mcp__lado__")
    }
    assert not deferred, f"LADO's tools deferred: {sorted(deferred)}"
    assert LADO_TOOLS <= set(tools), f"LADO's tools not loaded; the first turn had: {tools}"


def cli_version(provider: str) -> str:
    command = providers.get(provider).command
    return subprocess.run([command, "--version"], capture_output=True, text=True).stdout


def test_worker_does_a_task_reports_and_gets_a_message(live_repo, live_provider, monkeypatch):
    repo = live_repo
    started, since = time.monotonic(), time.time()
    version = cli_version(live_provider)
    start_session(repo, live_provider, monkeypatch)

    worker = runtime.spawn_worker(SESSION, TASK, name="w1")
    busy = answering(live_provider, "w1", lambda: status("w1") == state.BUSY)
    wait_for(busy, "w1 to be busy", 60)
    check_lado_tools_loaded(live_provider, worker.cwd, since)
    wait_for(lambda: messages("w1", "supervisor"), "w1's report", 240)
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle", 60)
    wait_for(
        lambda: messages("w1", "supervisor")[0][1] in RECEIVED,
        "w1's report to be delivered",
        60,
    )
    summary = check_report()
    check_first_input("w1", "your task")
    check_artifact()

    hello = runtime.git(str(repo), "show", f"{worker.branch}:hello.txt")
    assert hello.strip() == "OK"
    check_agent_config(live_provider, repo, worker)
    check_no_snapshots(live_provider, repo)

    # The UI's terminal on w1, open while LADO delivers to it: a viewer must not stop that.
    viewing = terminal.open(SESSION, "w1", terminal.VIEW)
    runtime.send_message(SESSION, "supervisor", "w1", FOLLOW_UP, FOLLOW_UP_BODY)
    runtime.send_message(SESSION, "supervisor", "w1", WHILE_BUSY)
    wait_for(
        lambda: (FOLLOW_UP, state.READ) in messages("supervisor", "w1"),
        "w1 to read the follow-up with read_messages",
        120,
    )
    check_turn_end_output()
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle after the follow-up", 120)
    check_human()
    check_terminal(viewing)
    check_log(live_provider, summary)
    check_clear(live_provider)

    finish_worker(repo, worker)

    processes = agent_processes()
    supervisor = terminal.open(SESSION, "supervisor", terminal.CONTROL)
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "stop")
    check_terminal_ended(supervisor)
    check_loop_ended()
    check_resume(live_provider, repo)
    # Kilo and OpenCode update themselves unless told not to; LADO's agents must not (the
    # providers switch it off, so the test needs no *_DISABLE_AUTOUPDATE from outside).
    if live_provider in ("kilo", "opencode"):
        assert cli_version(live_provider) == version
    print(f"{live_provider}: {time.monotonic() - started:.0f}s")


def check_turn_end_output() -> None:
    """The line queued while w1 was busy went in its turn-end hook's output and is delivered
    once the CLI confirms it: the prompt the plugin's promptAsync makes (Kilo, OpenCode), or
    the end of the turn that went on from it (Claude Code's stop_hook_active)."""
    [line] = [m for m in state.list_messages(SESSION) if m.summary == WHILE_BUSY]
    wait_for(
        lambda: state.get_message(SESSION, line.id).state in RECEIVED,
        "the line sent while w1 was busy to be delivered",
        120,
    )
    assert state.get_message(SESSION, line.id).channel == state.HOOK_OUTPUT


HUMAN_ASKS = 'From the human: reply to me with send_message(to="human", summary="ACK") only'


def check_human() -> None:
    """The human's message (as the UI's composer sends it) reaches w1, w1 replies to the
    human with send_message, and the end of its turn marks the human's message replied."""
    runtime.write_as_human(SESSION, HUMAN_ASKS, to="w1")
    wait_for(lambda: messages("w1", "human"), "w1's reply to the human", 120)
    assert messages("w1", "human")[0][1] == state.DELIVERED
    wait_for(lambda: status("w1") == state.IDLE, "w1 to be idle after replying", 120)
    [asked] = [m for m in state.list_messages(SESSION) if m.sender == "human"]
    wait_for(
        lambda: state.get_message(SESSION, asked.id).reply_state == state.REPLIED,
        "the human's message to be marked replied",
        60,
    )


def check_terminal(term: terminal.Terminal) -> None:
    """The terminal showed the agent's screen; its history answers, full screen or not."""
    shown = b""
    while (chunk := term.read(0.5)) not in (None, b""):
        shown += chunk
    assert shown, "the terminal showed nothing"
    found = terminal.history(SESSION, term.agent, 200)
    assert found.alternate or found.text.strip()
    print(f"{term.agent}: full screen {found.alternate}")
    term.close()


def check_terminal_ended(term: terminal.Terminal) -> None:
    """A terminal open at `lado stop` ends, and no viewer of the session is left."""
    deadline = time.monotonic() + 10
    while term.read() is not None:
        assert time.monotonic() < deadline, "the terminal did not end at stop"
    assert str(terminal.ended(SESSION, "supervisor")) == f'session "{SESSION}" is stopped'
    term.close()
    assert terminal.close_viewers(SESSION) == []


def check_clear(provider: str) -> None:
    """Claude Code: /clear, typed by the human, ends the supervisor's conversation and goes
    on with a new one in the same process (as /resume does). The supervisor is idle again
    without being stopped and gets the next message. Kilo starts a new conversation without
    ending its plugin, so nothing changes there."""
    if provider != "claude":
        return
    wait_for(lambda: status("supervisor") == state.IDLE, "the supervisor to be idle", 120)
    mark = state.list_events(SESSION)[-1].id
    target = f"{SESSION}:supervisor"
    tmux.run("send-keys", "-t", target, "-l", "/clear")
    tmux.run("send-keys", "-t", target, "Enter")

    def statuses() -> list[str]:
        events = state.list_events(SESSION, mark)
        return [e.detail for e in events if (e.agent, e.kind) == ("supervisor", state.STATUS)]

    wait_for(lambda: statuses()[-2:] == [state.STARTING, state.IDLE], "a new conversation", 60)
    assert state.STOPPED not in statuses()
    runtime.send_message(SESSION, "w1", "supervisor", "After the clear")
    wait_for(
        lambda: messages("w1", "supervisor")[-1] in [("After the clear", s) for s in RECEIVED],
        "the message after /clear to be delivered",
        60,
    )


def check_resume(provider: str, repo) -> None:
    """`lado start` again: the stopped session resumes, and the new supervisor's first input
    is LADO's resume message, through its queue. Then stop it for good."""
    started = runtime.start_session(str(repo), SESSION, None)
    assert (started.resumed, started.changes, started.problems) == (True, [], [])
    resumed = "[from lado] session resumed: 0 open runs"
    assert state.get_agent(SESSION, "supervisor").task is None
    resume_event = [e for e in state.list_events(SESSION) if e.kind == state.SESSION_RESUME][-1]

    def answered() -> bool:
        answer_dialogs(provider, SESSION, "supervisor")
        idle = [
            e
            for e in state.list_events(SESSION, resume_event.id)
            if (e.agent, e.kind, e.detail) == ("supervisor", state.STATUS, state.IDLE)
        ]
        return bool(idle) and resumed in tmux.capture(SESSION, "supervisor")

    wait_for(answered, "the supervisor to take the resume message", 120)
    check_first_input("supervisor", "session resumed: 0 open runs")
    assert loop.running(SESSION)
    ls = subprocess.run(
        [sys.executable, "-m", "lado.cli", "ls"], capture_output=True, text=True, env=os.environ
    )
    listed = f"{SESSION}  {started.session.repo}\n"
    assert listed in ls.stdout and "(stopped)" not in ls.stdout, ls.stdout
    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "the stop after the resume")
    check_loop_ended()
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
    started, since = time.monotonic(), time.time()
    start_session(repo, live_provider)

    run = runs.start(SESSION, "tiny", "Add flow.txt for the live test.")
    worker = runs.spawn_worker(SESSION, run.name, name="w1")
    assert worker.task.startswith(f"Run {run.name} (flow tiny), step step.")
    assert worker.cwd == run.worktree
    check_lado_tools_loaded(live_provider, worker.cwd, since)

    ended = wait_for(
        answering(
            live_provider,
            "w1",
            lambda: (r := state.get_run(SESSION, run.name)).status == state.ENDED and r,
        ),
        "the run to end",
        240,
    )
    assert ended.state == "end"
    check_first_input("w1", f"flow {run.name}: step step")
    moves = [(e.agent, e.detail) for e in state.list_events(SESSION) if e.kind == state.FLOW]
    assert moves == [("w1", "step -done-> end")]
    assert runtime.git(str(repo), "show", f"{run.branch}:flow.txt").strip() == "OK"
    # w1's MCP server stores the end first and tells the supervisor after its git checks.
    kept = f"flow {run.name}: ended at end; kept its worktree and branch"
    wait_for(
        lambda: kept in [summary for summary, _ in messages(state.LADO, "supervisor")],
        "the supervisor to be told the run ended",
        30,
    )
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


IMAGE_WORKER = (
    "Do nothing now. When a message from the human comes, do exactly what it says, using "
    "only the tools it names."
)


def rgb_png(width: int, height: int, row) -> bytes:
    """A PNG of 8-bit RGB pixels, `row()` giving each row's width * 3 bytes."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + crc

    pixels = b"".join(b"\x00" + row() for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def solid_png(width: int, height: int, rgb: bytes) -> bytes:
    return rgb_png(width, height, lambda: rgb * width)


def noise_png(width: int, height: int) -> bytes:
    """Random pixels: as large as a screenshot of that size gets, or larger."""
    return rgb_png(width, height, lambda: os.urandom(width * 3))


def ask_about_image(name: str, data: bytes, ask: str) -> str:
    """The human sends `data` as the file `name` to w1 with `ask`; w1's reply to the human."""
    upload = artifacts.upload(SESSION, name, data)
    before = len(messages("w1", "human"))
    runtime.write_as_human(
        SESSION, ask.format(name=upload.full_name), to="w1", attached=[upload.full_name]
    )
    wait_for(lambda: len(messages("w1", "human")) > before, f"w1's reply about {name}", 180)
    wait_for(lambda: status("w1") == state.IDLE, f"w1 to be idle after {name}", 120)
    errors = [e.detail for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR]
    assert errors == [], f"a turn of w1 ended on an error after {name}: {errors}"
    return messages("w1", "human")[-1][0]


def test_an_agent_sees_the_image_the_human_attaches(live_repo, live_provider):
    """The human's PNG reaches the model as an image through read_artifact: w1 names the
    colour of a solid red one. A screenshot-sized one over 1 MB and one just under
    artifacts.IMAGE_LIMIT do not end its turn on an error (an image the API refuses would
    fail every later turn). A model that takes no images is named and skipped, never a
    pass."""
    repo = live_repo
    start_session(repo, live_provider)
    runtime.spawn_worker(SESSION, IMAGE_WORKER, name="w1")
    try:
        idle = answering(live_provider, "w1", lambda: status("w1") == state.IDLE)
        wait_for(idle, "w1 to be idle", 120)
        colour = ask_about_image(
            "colour.png",
            solid_png(64, 64, b"\xff\x00\x00"),
            'Read the attached image "{name}" with read_artifact. Then reply to me with '
            'send_message(to="human", summary=<its colour in one lower-case English word>) '
            "and nothing else.",
        )
        print(f"{live_provider}: the colour: {colour!r}")
        if "red" not in colour.lower():
            if live_provider == "claude":
                pytest.fail(f"Claude Code did not see the image: {colour!r}")
            pytest.skip(
                f"{live_provider}'s model did not see the image (no image input?): {colour!r}"
            )
        if live_provider != "claude":
            return  # the sizes are Claude's API's limits (artifacts.IMAGE_LIMIT)
        seen = (
            'Read the attached image "{name}" with read_artifact, then reply to me with '
            'send_message(to="human", summary="SEEN") and nothing else.'
        )
        screenshot = noise_png(1280, 300)
        assert 1_000_000 < len(screenshot) <= artifacts.IMAGE_LIMIT
        assert "SEEN" in ask_about_image("screenshot.png", screenshot, seen)
        largest = noise_png(1440, 900)
        assert artifacts.IMAGE_LIMIT - 100_000 < len(largest) <= artifacts.IMAGE_LIMIT
        assert "SEEN" in ask_about_image("largest.png", largest, seen)
    finally:
        runtime.stop_session(SESSION)
