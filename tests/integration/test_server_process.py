"""The UI server as a process: one per LADO_HOME, started by `lado ui` in the background,
ended by `lado server stop`. No browser: that is tests/ui/."""

import json
import os
import socket
import stat
import subprocess
import sys
import threading
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


def test_stop_returns_once_the_servers_process_has_ended():
    """The server frees its lock a moment before its process ends; a stop that returned
    on the lock let `lado uninstall` go on while the old server lived."""
    for _ in range(5):
        started = lado_cli("ui", "--no-open", "--port", "0")
        assert started.returncode == 0, started.stderr
        pid = server_run.running()["pid"]
        assert server_run.stop()["pid"] == pid
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_a_server_on_every_address_warns_and_gives_a_link_for_other_machines():
    """On macOS with its firewall on, a dialog may ask to accept incoming connections; the
    test does not need them."""
    first = lado_cli("ui", "--no-open", "--host", "0.0.0.0", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert info["host"] == "0.0.0.0"
    assert info["url"] == f"http://127.0.0.1:{info['port']}"
    token = auth.token()
    address = server_run.network_address() or socket.gethostname()
    assert first.stdout.splitlines() == [
        f"{info['url']}/?token={token}",
        f"From another machine: http://{address}:{info['port']}/?token={token}",
    ]
    assert "open to other machines" in first.stderr
    assert "listens on 0.0.0.0" in (state.home() / "server.log").read_text()
    with urllib.request.urlopen(f"{info['url']}/api/health", timeout=10) as answer:
        assert json.load(answer)["ok"] is True

    stopped = lado_cli("server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert gone(info["pid"])


def test_ui_prints_the_servers_link_for_another_device_not_its_own(monkeypatch):
    """The server's environment decides the link, not that of the shell running lado ui."""
    monkeypatch.setenv("LADO_PUBLIC_HOST", "server-side.local")
    info = server_run.wait_ready(server_run.start_background("0.0.0.0", 0))
    monkeypatch.setenv("LADO_PUBLIC_HOST", "shell side")  # not a host: lado ui would warn
    shown = lado_cli("ui", "--no-open")
    assert shown.returncode == 0, shown.stderr
    token = auth.token()
    assert shown.stdout.splitlines() == [
        f"{info['url']}/?token={token}",
        f"From another machine: http://server-side.local:{info['port']}/?token={token}",
    ]
    assert "LADO_PUBLIC_HOST" not in shown.stderr  # warned at the server's start only
    lado_cli("server", "stop")


def test_a_public_host_that_is_not_a_host_is_warned_at_the_start(monkeypatch):
    monkeypatch.setenv("LADO_PUBLIC_HOST", "http://kaos.local:8765")
    first = lado_cli("ui", "--no-open", "--host", "0.0.0.0", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert (
        "lado: warning: LADO_PUBLIC_HOST is not a host name or address: http://kaos.local:8765; "
        "the link for other devices does not use it"
    ) in (state.home() / "server.log").read_text()
    assert "From another machine: http://kaos.local" not in first.stdout
    lado_cli("server", "stop")
    assert gone(info["pid"])


def test_a_new_token_ends_an_open_event_stream_and_the_old_cookie():
    info = server_run.wait_ready(server_run.start_background(None, 0))
    old = auth.token()
    cookie = {"Cookie": f"{auth.cookie_name(info['port'])}={old}"}
    stream = urllib.request.urlopen(
        urllib.request.Request(f"{info['url']}/api/events", headers=cookie), timeout=10
    )
    ended = threading.Event()

    def read() -> None:
        while stream.readline():
            pass
        ended.set()

    threading.Thread(target=read, daemon=True).start()
    ask = urllib.request.Request(
        f"{info['url']}/api/access/new-token",
        method="POST",
        headers={**cookie, "Origin": info["url"]},
    )
    with urllib.request.urlopen(ask, timeout=10) as answer:
        said = json.load(answer)
        set_cookie = answer.headers["set-cookie"]
    new = auth.token()
    assert new != old and said["reason"] == "loopback"
    assert f"{auth.cookie_name(info['port'])}={new}" in set_cookie
    assert ended.wait(5), "the open event stream did not end"
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(
            urllib.request.Request(f"{info['url']}/api/sessions", headers=cookie), timeout=10
        )
    assert refused.value.code == 401
    stream.close()
    lado_cli("server", "stop")


def test_a_server_in_a_container_notes_the_publication_and_no_other_machines(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    first = lado_cli("ui", "--no-open", "--host", "0.0.0.0", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert first.stdout.splitlines() == [f"{info['url']}/?token={auth.token()}"]
    log = (state.home() / "server.log").read_text()
    for text in (log, first.stderr):
        assert f"listens on 0.0.0.0:{info['port']} inside it" in text
        assert "open to other machines" not in text

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
