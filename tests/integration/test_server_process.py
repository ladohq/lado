"""The UI server as a process: one per LADO_HOME, started by `lado ui` in the background,
ended by `lado server stop`. No browser: that is tests/ui/."""

import json
import os
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

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


class StopAtRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


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
    assert (
        f"LADO server {info['version']} at {info['url']}, "
        f"listening on 127.0.0.1:{info['port']}, pid {info['pid']}"
    ) in log
    assert "open to other machines" not in log

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


def test_a_server_on_every_address_warns_and_gives_a_link_for_other_machines():
    """On macOS with its firewall on, a dialog may ask to accept incoming connections; the
    test does not need them."""
    first = lado_cli("ui", "--no-open", "--host", "0.0.0.0", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert info["host"] == "0.0.0.0"
    assert info["url"] == f"http://127.0.0.1:{info['port']}"
    token = auth.token()
    assert first.stdout.splitlines() == [
        f"{info['url']}/?token={token}",
        f"From another machine: http://{socket.gethostname()}:{info['port']}/?token={token} "
        "(or this host's address)",
    ]
    assert "open to other machines" in first.stderr
    assert "listens on 0.0.0.0" in (state.home() / "server.log").read_text()
    with urllib.request.urlopen(f"{info['url']}/api/health", timeout=10) as answer:
        assert json.load(answer)["ok"] is True

    stopped = lado_cli("server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert gone(info["pid"])


def test_ui_restarts_a_server_of_another_version_on_its_port():
    first = lado_cli("ui", "--no-open", "--port", "0")
    assert first.returncode == 0, first.stderr
    old = server_run.running()
    # As if the server were started by the LADO before an upgrade.
    server_run.info_path().write_text(json.dumps({**old, "version": "0.0.1"}))

    again = lado_cli("ui", "--no-open")
    assert again.returncode == 0, again.stderr
    new = server_run.running()
    assert f"lado: restarted the LADO server: 0.0.1 -> {new['version']}" in again.stderr
    assert gone(old["pid"])
    assert new["pid"] != old["pid"] and new["port"] == old["port"]
    assert again.stdout == first.stdout  # the same link: same port, same token
    lado_cli("server", "stop")


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


def test_server_log_is_the_owners_only_and_never_holds_the_token():
    link = lado_cli("ui", "--no-open", "--port", "0").stdout.strip()
    # Logs in and stops at the redirect: the page behind it needs the bundle (make web),
    # which the integration tests do not build.
    no_redirect = urllib.request.build_opener(StopAtRedirect)
    with pytest.raises(urllib.error.HTTPError) as answer:
        no_redirect.open(link, timeout=10)
    assert answer.value.code == 303
    lado_cli("server", "stop")
    log = state.home() / "server.log"
    assert auth.token() not in log.read_text()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600


def test_ui_says_at_once_when_the_server_it_started_exits():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        started = time.monotonic()
        result = lado_cli("ui", "--no-open", "--port", str(port))
        took = time.monotonic() - started
    assert result.returncode == 1
    assert f"port {port} is busy" in result.stderr  # the server's own error, from its log
    assert str(state.home() / "server.log") in result.stderr
    assert took < server_run.READY_TIMEOUT / 2
