"""scripts/check_lock.py: one heavy test run per machine at a time (Makefile)."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

HELPER = Path(__file__).parents[1] / "scripts" / "check_lock.py"
TIMEOUT = 10


@pytest.fixture
def env(tmp_path):
    """The helper's environment: its own lock file, and none of the lock's variables of the
    run these tests are part of (a `make test` holds the lock itself)."""
    environ = {
        k: v for k, v in os.environ.items() if k not in ("LADO_CHECK_LOCK", "LADO_CHECK_LOCK_HELD")
    }
    environ["LADO_CHECK_LOCK_FILE"] = str(tmp_path / "check.lock")
    return environ


def locked(env, cwd, *command, **kwargs) -> subprocess.Popen:
    """The helper running a command, in its own process group (as a terminal's job)."""
    return subprocess.Popen(
        [sys.executable, str(HELPER), *command],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        **kwargs,
    )


def waits_for(path: Path) -> list[str]:
    """A command that writes `path`.started, then waits until `path` exists."""
    return [
        sys.executable,
        "-c",
        "import pathlib, sys, time\n"
        f"pathlib.Path({str(path)!r} + '.started').touch()\n"
        f"while not pathlib.Path({str(path)!r}).exists(): time.sleep(0.02)\n",
    ]


def wait_until(check, what: str) -> None:
    deadline = time.monotonic() + TIMEOUT
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.02)


def started(path: Path) -> None:
    wait_until(Path(f"{path}.started").exists, f"{path.name} to start")


def test_a_second_run_waits_and_says_once_for_whom(tmp_path, env):
    first_dir = tmp_path / "worktree-a"
    first_dir.mkdir()
    release = tmp_path / "release"
    first = locked(env, first_dir, *waits_for(release))
    started(release)

    second = locked(env, tmp_path, *waits_for(tmp_path / "second-done"))
    time.sleep(0.5)
    assert not Path(f"{tmp_path / 'second-done'}.started").exists()

    release.touch()
    assert first.wait(TIMEOUT) == 0
    started(tmp_path / "second-done")
    (tmp_path / "second-done").touch()
    assert second.wait(TIMEOUT) == 0
    lines = second.stderr.read().splitlines()
    assert lines == [f"check lock: waiting for the run in {first_dir} (pid {first.pid})"]


def test_a_run_passes_its_exit_status_on_and_frees_the_lock_on_a_failure(tmp_path, env):
    failing = locked(env, tmp_path, sys.executable, "-c", "raise SystemExit(3)")
    assert failing.wait(TIMEOUT) == 3

    after = locked(env, tmp_path, sys.executable, "-c", "pass")
    assert after.wait(TIMEOUT) == 0
    assert after.stderr.read() == ""


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(lambda p: os.killpg(p.pid, signal.SIGINT), id="ctrl-c"),
        pytest.param(lambda p: p.send_signal(signal.SIGTERM), id="sigterm"),
    ],
)
def test_a_run_stopped_by_a_signal_frees_the_lock(tmp_path, env, stop):
    first = locked(env, tmp_path, *waits_for(tmp_path / "never"))
    started(tmp_path / "never")

    stop(first)
    assert first.wait(TIMEOUT) != 0

    after = locked(env, tmp_path, sys.executable, "-c", "pass")
    assert after.wait(TIMEOUT) == 0
    assert after.stderr.read() == ""


def test_a_process_the_run_leaves_behind_does_not_keep_the_lock(tmp_path, env):
    first = locked(env, tmp_path, "sh", "-c", "sleep 30 >/dev/null 2>&1 </dev/null & echo $!")
    assert first.wait(TIMEOUT) == 0
    orphan = int(first.stdout.read())
    try:
        after = locked(env, tmp_path, sys.executable, "-c", "pass")
        assert after.wait(TIMEOUT) == 0
    finally:
        os.kill(orphan, signal.SIGKILL)


def test_a_run_inside_a_run_does_not_wait_for_it(tmp_path, env):
    inner = [sys.executable, str(HELPER), sys.executable, "-c", "print('inner ran')"]
    outer = locked(env, tmp_path, *inner)
    assert outer.wait(TIMEOUT) == 0
    assert outer.stdout.read() == "inner ran\n"
    assert outer.stderr.read() == ""


def test_the_switch_runs_without_the_lock(tmp_path, env):
    release = tmp_path / "release"
    holder = locked(env, tmp_path, *waits_for(release))
    started(release)
    try:
        free = locked(
            {**env, "LADO_CHECK_LOCK": "0"}, tmp_path, sys.executable, "-c", "print('ran')"
        )
        assert free.wait(TIMEOUT) == 0
        assert free.stdout.read() == "ran\n"
    finally:
        release.touch()
        holder.wait(TIMEOUT)


def test_the_lock_file_is_the_machines_by_default(tmp_path, env):
    del env["LADO_CHECK_LOCK_FILE"]
    shown = subprocess.run(
        [sys.executable, str(HELPER), "--path"], env=env, capture_output=True, text=True
    )
    assert shown.stdout == f"/tmp/lado-check-{os.getuid()}.lock\n"
