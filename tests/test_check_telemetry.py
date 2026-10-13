"""scripts/check_telemetry.py: the Release workflow's check that the endpoint's region
accepts LADO's telemetry token."""

import http.server
import importlib.util
import json
import socket
import threading
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_telemetry.py"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_telemetry = _load("check_telemetry", SCRIPT)


class _Server:
    """A local HTTP server in a thread that answers every POST with `status` after
    `delay` seconds and keeps each request."""

    def __init__(self, status: int, delay: float = 0.0):
        self.requests: list[dict] = []
        self.release = threading.Event()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.requests.append({"path": self.path, "body": json.loads(body or b"{}")})
                if delay:
                    outer.release.wait(delay)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.httpd.server_address[1]}/batch/"

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def serve():
    servers = []

    def start(status: int, delay: float = 0.0) -> _Server:
        servers.append(_Server(status, delay))
        return servers[-1]

    yield start
    for server in servers:
        server.close()


def test_a_2xx_accepts_the_token(serve):
    server = serve(200)
    ok, line = check_telemetry.check(server.endpoint, "phc_abc")
    assert (ok, line) == (True, "telemetry: 127.0.0.1 accepts the project token")
    assert server.requests == [
        {"path": "/flags/?v=2", "body": {"api_key": "phc_abc", "distinct_id": "lado-release-check"}}
    ]


@pytest.mark.parametrize("status", [401, 403])
def test_401_and_403_refuse_the_token(serve, status):
    ok, line = check_telemetry.check(serve(status).endpoint, "phc_abc")
    assert not ok
    assert line == (
        "telemetry: 127.0.0.1 refuses the project token: "
        "it is not a token of a project in this region"
    )


def test_another_answer_cannot_check(serve):
    ok, line = check_telemetry.check(serve(500).endpoint, "phc_abc")
    assert not ok
    assert line.startswith("telemetry: cannot check the project token: ")
    assert "500" in line


def test_a_closed_port_cannot_check():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    ok, line = check_telemetry.check(f"http://127.0.0.1:{port}/batch/", "phc_abc")
    assert not ok
    assert line.startswith("telemetry: cannot check the project token: ")


def test_an_empty_token_cannot_check_and_sends_nothing(serve):
    server = serve(200)
    ok, line = check_telemetry.check(server.endpoint, "")
    assert (ok, line) == (False, "telemetry: cannot check the project token: the token is empty")
    assert server.requests == []


def test_no_answer_in_time_cannot_check(serve):
    server = serve(200, delay=5)
    ok, line = check_telemetry.check(server.endpoint, "phc_abc", timeout=0.3)
    assert not ok
    assert line.startswith("telemetry: cannot check the project token: ")


def test_main_checks_the_package_constants(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(
        check_telemetry,
        "check",
        lambda endpoint, token: seen.append((endpoint, token)) or (False, "no"),
    )
    from lado import telemetry

    assert check_telemetry.main() == 1
    assert seen == [(telemetry.ENDPOINT, telemetry.PROJECT_TOKEN)]
    assert capsys.readouterr().out == "no\n"


def test_the_release_checks_the_token_before_it_builds_and_publishes():
    steps = yaml.safe_load(RELEASE.read_text())["jobs"]["pypi"]["steps"]
    runs = [step.get("run", "").strip() for step in steps]
    names = [step.get("name", "") for step in steps]
    check = runs.index("uv run python scripts/check_telemetry.py")
    assert names.index("Check tag matches package version") < check
    assert check < runs.index("make dist")
    assert check < runs.index("uv publish")
