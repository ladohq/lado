"""An agent's environment comes from the user's login shell, not from whoever runs LADO."""

import json
import os
import shlex

import agent_helpers
import pytest

from lado import runtime, state

pytestmark = pytest.mark.integration

SESSION = "envtest"


def environ(agent: str) -> dict[str, str]:
    """The environment the fake agent reported at its start."""
    path = state.home() / "agents" / SESSION / agent / "seen.json"
    return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}


def wait_environ(agent: str) -> dict[str, str]:
    agent_helpers.wait_for(lambda: environ(agent), f"{agent} to report", SESSION)
    return environ(agent)


@pytest.fixture
def login_shell(tmp_path, monkeypatch):
    """$SHELL is a script whose startup exports FROM_SHELL, and, as a user's does, the PATH
    to tmux (also git kept from starting maintenance in the agents' repos, as in the test
    run)."""
    exports = {
        **agent_helpers.no_maintenance_env({}),
        "PATH": os.environ["PATH"],
        "FROM_SHELL": "yes",
    }
    exports = " ".join(f"{k}={shlex.quote(v)}" for k, v in exports.items())
    shell = tmp_path / "login-shell"
    shell.write_text(f'#!/bin/sh\necho "rc noise"\nexport {exports}\nexec /bin/sh -c "$2"\n')
    shell.chmod(0o755)
    monkeypatch.setenv("SHELL", str(shell))
    monkeypatch.delenv("LADO_AGENT_ENV")  # the shell, as for a user
    monkeypatch.delenv("FROM_SHELL", raising=False)
    monkeypatch.setenv("ONLY_IN_CALLER", "1")  # also in the tmux server LADO starts


def test_the_supervisor_and_a_spawned_worker_get_the_login_shells_environment(
    repo, login_shell, monkeypatch
):
    runtime.start_session(str(repo), SESSION, None, "fake")
    supervisor = wait_environ("supervisor")
    assert supervisor["FROM_SHELL"] == "yes"
    assert "ONLY_IN_CALLER" not in supervisor
    assert supervisor["LADO_AGENT"] == "supervisor"
    assert supervisor["TMUX"]  # its own window's, from tmux

    # The worker is spawned by the supervisor's LADO MCP server, a process of the agent.
    monkeypatch.delenv("SHELL")  # nothing of the test's process
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE,
        "supervisor to be idle",
        SESSION,
    )
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    worker = wait_environ("worker")
    assert worker["FROM_SHELL"] == "yes"
    assert "ONLY_IN_CALLER" not in worker
    assert worker["LADO_AGENT"] == "worker"
