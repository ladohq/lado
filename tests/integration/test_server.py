"""The UI server as a process: one per LADO_HOME, started by `lado ui` in the background,
ended by `lado server stop`. No browser: that is tests/ui/."""

import os
import subprocess
import sys
import time

import pytest

from lado import state
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration


def lado_cli(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
        timeout=timeout,
    )


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie of a process this test started counts as ended.
    found = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return not found.stdout.strip().startswith("Z")


def gone(pid: int, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while alive(pid):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


@pytest.fixture(autouse=True)
def no_server_left():
    yield
    info = server_run.running()
    if info:
        server_run.stop()
        pytest.fail(f"the test left a LADO server running: {info}")


def test_ui_starts_one_server_in_the_background_and_stop_ends_it():
    first = lado_cli("ui", "--no-open", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert first.stdout.strip() == f"{info['url']}/?token={auth.token()}"
    log = (state.home() / "server.log").read_text()
    assert f"LADO server {info['version']} at {info['url']}, pid {info['pid']}" in log

    again = lado_cli("ui", "--no-open")  # finds the running server, starts none
    assert again.returncode == 0, again.stderr
    assert again.stdout == first.stdout
    assert server_run.running()["pid"] == info["pid"]

    stopped = lado_cli("server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert f"Stopped the LADO server at {info['url']}" in stopped.stdout
    assert gone(info["pid"])
    assert not server_run.info_path().exists()
    assert "not running" in lado_cli("server", "stop").stdout


def test_a_second_server_refuses_and_names_the_first():
    first = subprocess.Popen(
        [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ,
    )
    try:
        info = server_run.wait_ready()
        assert info["pid"] == first.pid
        second = lado_cli("server", "--port", "0")
        assert second.returncode == 1
        assert f"a LADO server already runs at {info['url']}" in second.stderr
    finally:
        lado_cli("server", "stop")
        first.wait(timeout=10)
    assert first.returncode == 0  # ended by SIGTERM, cleanly
