"""What the tests with real agent CLIs share: the live tests (tests/live/, real models) and the
smoke tests (tests/smoke/, no model). Their isolation, a provider with a test model, the
dialogs a human answers once per folder, the agents' processes, and the evidence a failed
test keeps."""

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import refuse_unless_isolated

from lado import runtime, state, tmux
from lado.providers import base
from lado.providers.claude import ClaudeProvider
from lado.providers.codex import CodexProvider
from lado.providers.kilo import KiloProvider
from lado.providers.opencode import OpenCodeProvider

CLASSES = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "kilo": KiloProvider,
    "opencode": OpenCodeProvider,
}

CLAUDE_TRUST = "Yes, I trust this folder"
CODEX_TRUST = "Trust this folder?"

EVIDENCE = Path(tempfile.gettempdir(), "lado-live-evidence")


def with_model(provider_class: type[base.Provider], model: str) -> base.Provider:
    """The provider, with `--model` added to its agents' argv.

    LADO has no model option yet; this is test-only. Hooks run in their own processes and
    look up the real provider by name, which parses events the same way.
    """

    class WithModel(provider_class):
        def launch_command(self, *args, **kwargs) -> base.Launch:
            launch = super().launch_command(*args, **kwargs)
            argv = [launch.argv[0], "--model", self.model, *launch.argv[1:]]
            return base.Launch(argv, launch.env, launch.warnings)

    provider = WithModel()
    provider.model = model  # also for checks that run the CLI themselves
    return provider


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"  # a tmux server of its own for each test
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    refuse_unless_isolated()
    yield
    kill_tmux_server(socket)


def keep_evidence(item, report) -> None:
    """When a test fails, keep what shows why (agent_helpers.keep_evidence) in a folder of its
    own under EVIDENCE, before teardown kills its tmux server and removes its LADO home, and
    name the folder in the failure report. A passing test keeps nothing. For a conftest's
    pytest_runtest_makereport; the test's module names its session as SESSION."""
    if not report.failed or report.when == "teardown":
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = EVIDENCE / f"{stamp}-{re.sub(r'[^A-Za-z0-9_.-]', '_', item.name)}"
    try:
        agent_helpers.keep_evidence(item.module.SESSION, folder)
        kept = f"kept in {folder}"
    except Exception as exc:  # the test's own failure must still be reported
        kept = f"could not keep it in {folder}: {exc!r}"
    report.sections.append(("LADO evidence", kept))


def status(session: str, agent: str) -> str:
    current = state.get_agent(session, agent)
    if current is None:
        pytest.fail(f"agent {agent} is gone\n{agent_helpers.diagnostics(session)}")
    return current.status


def answer_dialogs(provider: str, session: str, window: str) -> None:
    """Answer the dialogs a human answers once per repo, before the agent can start. The
    first time, the agent (named as its window) waits for the human and says why: LADO saw
    the trust dialog coming (Provider.first_hook_blocker)."""
    if provider == "claude" and CLAUDE_TRUST in tmux.capture(session, window):
        if (session, window) not in TRUST_ASKED:
            TRUST_ASKED.add((session, window))
            assert status(session, window) == state.WAITING
            reason = runtime.status_reason(session, window) or ""
            assert reason.startswith("Claude Code asks whether to trust "), reason
        tmux.run("send-keys", "-t", f"{session}:{window}", "Down", "Enter")
    if provider == "codex" and CODEX_TRUST in tmux.capture(session, window):
        if (session, window) not in TRUST_ASKED:
            TRUST_ASKED.add((session, window))
            assert status(session, window) == state.WAITING
            reason = runtime.status_reason(session, window) or ""
            assert reason.startswith("Codex CLI asks whether to trust "), reason
        # "Trust and continue" is the first choice; the prompt on its command line follows.
        tmux.run("send-keys", "-t", f"{session}:{window}", "Enter")


TRUST_ASKED: set[tuple[str, str]] = set()  # the agents answer_dialogs checked


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
