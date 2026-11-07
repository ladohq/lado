"""A Codex agent in LADO's image (openspec capability codex-sandbox): Codex's sandbox cannot
start in Docker, so a Codex agent in the mode `default` runs without it, and `lado start`
says so (LAD-151). No model: the agent need not get past its start."""

import time

import pytest
from container_helpers import git_repo

pytestmark = pytest.mark.container

REPO = "/home/lado/repo"


def codex_args(container, session: str, window: str, timeout: float = 60) -> list[str]:
    """The argv of the Codex agent's window, once it has left `lado.agent_env` for `codex`.
    Read once and returned as read: a process's cmdline reads empty, with exit 0, while it
    execs, and the window's one pid goes from Python through `env` to `node` (LAD-214)."""
    deadline, cmdline = time.monotonic() + timeout, ""
    while time.monotonic() < deadline:
        pane = container.exec(
            "tmux", "-L", "lado", "display-message", "-p", "-t", f"{session}:{window}",
            "#{pane_pid}", check=False,
        ).stdout.strip()  # fmt: skip
        if pane:
            cmdline = container.exec("cat", f"/proc/{pane}/cmdline", check=False).stdout
            args = cmdline.split("\0")
            if "--no-daemon" in args and "lado.agent_env" not in args:
                return args
        time.sleep(0.5)
    raise AssertionError(f"no codex in {session}:{window}: {cmdline!r}")


def test_a_codex_supervisor_runs_without_the_sandbox_that_cannot_start(container):
    # The control: the cause of LAD-151 still holds in the image. When it does not, this test
    # would pass for no reason: re-check the cause, and whether the fallback is still needed.
    control = container.sh("cd ~ && codex sandbox -- true", check=False)
    assert control.returncode != 0 and "bwrap:" in control.stderr, (
        "Codex's sandbox now starts in LADO's image: re-check LAD-151's cause "
        f"(exit {control.returncode}): {control.stderr}"
    )

    git_repo(container, REPO)
    # A login variable in the agents' login shell, so the start is not refused for a login.
    container.sh("echo 'export OPENAI_API_KEY=container-fake-key' >> ~/.profile")
    started = container.exec(
        "lado", "start", REPO, "--name", "cx", "--provider", "codex",
        "--permission-mode", "default", "--no-attach", check=False,
    )  # fmt: skip
    assert started.returncode == 0, started.stdout + started.stderr
    assert "Codex's sandbox cannot start here (bwrap:" in started.stderr, started.stderr
    assert "Codex agent supervisor runs without it" in started.stderr, started.stderr

    args = codex_args(container, "cx", "supervisor")
    pairs = list(zip(args, args[1:], strict=False))
    assert ("-a", "on-request") in pairs, args
    assert ("--sandbox", "danger-full-access") in pairs, args
    config = container.exec("cat", "/home/lado/.lado/agents/cx/supervisor/config.toml").stdout
    assert "default_permissions" not in config and "[permissions" not in config, config
