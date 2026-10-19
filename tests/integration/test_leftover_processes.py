"""tests/leftovers.py on real processes: the sweep after a test, the reaping of a dead
run's leftovers and the check at a run's end."""

import os
import signal
import subprocess
import time
import uuid

import leftovers
import pytest

pytestmark = pytest.mark.integration

IGNORES_HUP = ["sh", "-c", 'trap "" HUP; sleep 60']


def start(argv: list[str], **env: str) -> subprocess.Popen:
    """`argv` with `env` added to the test's environment, once it runs (exec'd, so its
    environment is the one it was given)."""
    process = subprocess.Popen(argv, env={**os.environ, **env})
    deadline = time.monotonic() + 5
    while not any(
        p.pid == process.pid and p.command == " ".join(argv) for p in leftovers.processes()
    ):
        assert time.monotonic() < deadline, f"{argv} never started"
        time.sleep(0.02)
    return process


def stop(*processes: subprocess.Popen) -> None:
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait()


def test_a_sweep_with_nothing_left_returns_at_once(tmp_path):
    started = time.monotonic()

    assert leftovers.sweep(tmp_path / "nobody's home") == []
    assert time.monotonic() - started < 1


def test_a_sweep_kills_and_names_what_outlives_the_wait_and_leaves_other_homes(tmp_path):
    mine, other = tmp_path / "home", tmp_path / "home-2"
    stubborn = start(IGNORES_HUP, LADO_HOME=str(mine))
    neighbour = start(["sleep", "60"], LADO_HOME=str(other))
    try:
        stubborn.send_signal(signal.SIGHUP)

        left = leftovers.sweep(mine, wait=0.5)

        assert stubborn.pid in [p.pid for p in left]
        assert any(p.command == " ".join(IGNORES_HUP) for p in left)
        assert stubborn.wait(timeout=5) == -signal.SIGKILL
        assert neighbour.poll() is None
        with pytest.raises(
            pytest.fail.Exception, match=f"(?s)left after the test.*{stubborn.pid} sh -c"
        ):
            leftovers.fail_if(left, "the test")
    finally:
        stop(stubborn, neighbour)


def test_a_dead_runs_processes_are_reaped_and_a_living_runs_are_not():
    gone = subprocess.Popen(["true"])
    gone.wait()
    orphan = start(["sleep", "60"], LADO_TEST_PID=str(gone.pid))
    living = start(["sleep", "60"], LADO_TEST_PID=str(os.getpid()))
    try:
        reaped = leftovers.reap_dead_runs()

        assert orphan.pid in [p.pid for p in reaped]
        assert living.pid not in [p.pid for p in reaped]
        assert orphan.wait(timeout=5) == -signal.SIGKILL
        assert living.poll() is None
    finally:
        stop(orphan, living)


def tmux_server(socket: str) -> tuple[int, int]:
    """A tmux server on `socket` with one session; its pid and its pane's."""
    subprocess.run(["tmux", "-L", socket, "new-session", "-d", "sleep", "60"], check=True)
    pids = subprocess.run(
        ["tmux", "-L", socket, "display-message", "-p", "#{pid} #{pane_pid}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return int(pids[0]), int(pids[1])


def test_a_dead_tmux_servers_socket_is_removed_and_a_living_ones_kept(kill_tmux_server):
    folder = leftovers.tmux_folder()
    dead, living = (f"lado-test-{uuid.uuid4().hex[:8]}" for _ in range(2))
    dead_server, dead_pane = tmux_server(dead)
    tmux_server(living)
    try:
        os.kill(dead_server, signal.SIGKILL)
        os.kill(dead_pane, signal.SIGKILL)  # an orphan now, of a run still alive: the test's
        assert (folder / dead).exists()

        leftovers.reap_dead_runs()

        assert not (folder / dead).exists()
        assert (folder / living).exists()
    finally:
        kill_tmux_server(dead)
        kill_tmux_server(living)


def test_a_process_of_the_run_left_at_its_end_is_killed_and_named():
    left_behind = start(["sleep", "60"])
    try:
        left = leftovers.own_left(wait=0.5)

        assert [p.command for p in left if p.pid == left_behind.pid] == ["sleep 60"]
        assert left_behind.wait(timeout=5) == -signal.SIGKILL
    finally:
        stop(left_behind)
