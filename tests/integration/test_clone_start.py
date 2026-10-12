"""`lado start <git-url>`: the CLI as its own process clones, then starts a session of the
fake agent in the clone; Ctrl-C during the clone leaves nothing (openspec change
clone-from-url)."""

import os
import signal
import subprocess
import sys
import time

import fake_provider
import pytest
from agent_helpers import bare_remote, fake_git, fake_git_calls, gone, wait_for

from lado import runtime, state

pytestmark = pytest.mark.integration


def test_clone_and_start(tmp_path):
    url = bare_remote(tmp_path)
    folder = tmp_path / "work" / "app"
    done = subprocess.run(
        [
            sys.executable,
            str(fake_provider.LADO),
            "start",
            url,
            str(folder),
            "--branch",
            "develop",
            "--provider",
            "fake",
            "--no-attach",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        assert done.returncode == 0, done.stderr
        assert runtime.branch(str(folder)) == "develop"
        sess = state.get_session("app")
        assert sess is not None and sess.repo == os.path.realpath(folder)

        def idle():
            agent = state.get_agent("app", "supervisor")
            return agent is not None and agent.status == state.IDLE

        wait_for(idle, "the supervisor idle in the clone", "app")
    finally:
        if state.get_session("app"):
            runtime.stop_session("app")


def test_ctrl_c_during_the_clone_leaves_nothing(tmp_path):
    env = {**os.environ, **fake_git(tmp_path / "fake", "slow")}
    folder = tmp_path / "app"
    process = subprocess.Popen(
        [
            sys.executable,
            str(fake_provider.LADO),
            "start",
            "https://git.example.com/a/app",
            str(folder),
            "--provider",
            "fake",
            "--no-attach",
        ],
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        deadline = time.monotonic() + 30
        while not fake_git_calls(tmp_path / "fake"):
            assert time.monotonic() < deadline, "git never started"
            time.sleep(0.05)
        assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".app.clone-")]
        process.send_signal(signal.SIGINT)
        _, err = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 130, err
    assert err.splitlines()[-1] == "lado: clone cancelled"
    assert not folder.exists()
    assert [p.name for p in tmp_path.iterdir() if ".clone-" in p.name] == []
    [call] = fake_git_calls(tmp_path / "fake")
    assert gone(call["pid"]) and gone(call["child"])
    assert state.get_session("app") is None


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP])
def test_a_kill_or_a_closed_terminal_during_the_clone_leaves_nothing(tmp_path, sig):
    env = {**os.environ, **fake_git(tmp_path / "fake", "slow")}
    folder = tmp_path / "app"
    process = subprocess.Popen(
        [
            sys.executable,
            str(fake_provider.LADO),
            "start",
            "https://git.example.com/a/app",
            str(folder),
            "--provider",
            "fake",
            "--no-attach",
        ],
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        deadline = time.monotonic() + 30
        while not fake_git_calls(tmp_path / "fake"):
            assert time.monotonic() < deadline, "git never started"
            time.sleep(0.05)
        process.send_signal(sig)
        _, err = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 128 + sig, err
    assert not folder.exists()
    assert [p.name for p in tmp_path.iterdir() if ".clone-" in p.name] == []
    [call] = fake_git_calls(tmp_path / "fake")
    assert gone(call["pid"]) and gone(call["child"])
