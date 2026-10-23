"""The canary of a project's secrets (openspec change project-secrets, "A project's secrets
stay out of LADO's records"): a unique value set as a project's secret through the CLI and
through a real server, given to every kind of agent, is found nowhere else: not in any
process's arguments, the tmux server's environment, any file under LADO_HOME but its own,
any output of the CLI, any answer of the API (refusals included), the change feed, or
telemetry's payload. No browser: the UI's feed is the server's change feed."""

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import fake_provider
import pytest
from agent_helpers import install_kit, wait_for
from test_project_sessions import _approve_and_start, stop_all
from test_project_variables import TINY, environ, tell, wait_idle

from lado import project_secrets, projects, runs, runtime, state, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration

CLI_NAME, API_NAME = "IT_CANARY_TOKEN", "IT_CANARY_API_KEY"


def lado(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        fake_provider.lado_command(*args),
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


class Api:
    """A real server's API, with the token's cookie and its own origin."""

    def __init__(self, info: dict):
        self.url = info["url"]
        self.headers = {
            "Cookie": f"{auth.cookie_name(info['port'])}={auth.token()}",
            "Origin": info["url"],
            "Content-Type": "application/json",
        }

    def call(self, method: str, path: str, body: object = None) -> tuple[int, str]:
        data = None if body is None else json.dumps(body).encode()
        ask = urllib.request.Request(
            self.url + path, data=data, method=method, headers=self.headers
        )
        try:
            with urllib.request.urlopen(ask, timeout=30) as answer:
                return answer.status, answer.read().decode()
        except urllib.error.HTTPError as refused:
            return refused.code, refused.read().decode()

    def feed(self, seconds: float) -> str:
        """What the change feed sends from its start for `seconds`."""
        ask = urllib.request.Request(f"{self.url}/api/events?after=0", headers=self.headers)
        got: list[bytes] = []
        stream = urllib.request.urlopen(ask, timeout=30)

        def read() -> None:
            try:
                while line := stream.readline():
                    got.append(line)
            except (OSError, ValueError, AttributeError):
                pass  # closed below, maybe mid-read

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        time.sleep(seconds)
        stream.close()
        reader.join(5)
        return b"".join(got).decode()


def files_holding(root: Path, value: bytes, skip: list[Path]) -> list[Path]:
    """Every file under `root` holding `value`, but under `skip`."""
    found = []
    for folder, _, names in os.walk(root):
        for name in names:
            path = Path(folder) / name
            if any(path.is_relative_to(s) for s in skip) or path.is_symlink():
                continue
            try:
                if value in path.read_bytes():
                    found.append(path)
            except OSError:
                pass  # a socket or a file gone meanwhile
    return found


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config, telemetry_endpoint):
    """The project shop with its repository frontend, the plain variable BOARD_URL, the
    flow kit itcanary; statistics on, sent to a local endpoint."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("LADO_ENV_DIR", raising=False)
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    projects.set_variable("shop", "BOARD_URL", "https://board")
    kit = tmp_path / "kits" / "itcanary"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itcanary\nversion: 1.0.0\n")
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    install_kit(kit)
    yield telemetry_endpoint
    stop_all()
    if server_run.running():
        server_run.stop()


def test_a_project_secret_is_found_nowhere_else(shop):
    canary = f"canary-{uuid.uuid4().hex}"
    said: list[str] = []  # every output and answer

    # The CLI: set from stdin; refused with the value as an argument and on a plain name.
    done = lado("project", "set", "shop", CLI_NAME, "--secret", stdin=f"{canary}\n")
    assert done.returncode == 0, done.stderr
    said += [done.stdout, done.stderr]
    for refused in (
        lado("project", "set", "shop", CLI_NAME, canary, "--secret"),
        lado("project", "set", "shop", "BOARD_URL", "--secret", stdin=canary),
        lado("project", "set", "shop", "PATH", "--secret", stdin=canary),
    ):
        assert refused.returncode == 1
        said += [refused.stdout, refused.stderr]

    # The API of a real server: set, replaced, and refused (400, 404, 422).
    api = Api(server_run.wait_ready(server_run.start_background(None, 0)))
    for value in (f"{canary}-old", f"{canary}-api"):
        status, body = api.call("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"value": value})
        assert status == 200, body
        said.append(body)
    for method, path, body, expected in [
        ("PUT", "/api/projects/shop/secrets/PATH", {"value": canary}, 400),
        ("PUT", "/api/projects/shop/secrets/BOARD_URL", {"value": canary}, 400),
        ("PUT", "/api/projects/acme/secrets/X", {"value": canary}, 404),
        ("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"secret": canary}, 422),
        ("PUT", f"/api/projects/shop/secrets/{API_NAME}", {"value": [canary]}, 422),
        ("PUT", "/api/projects/shop/variables/BOARD_URL", {"value": 5}, 422),
    ]:
        status, answer = api.call(method, path, body)
        assert status == expected, answer
        said.append(answer)
    assert project_secrets.names("shop") == [API_NAME, CLI_NAME]

    # Every kind of agent of a session in the project gets the secrets.
    kits = ["default", "itcanary"]
    runtime.start_session(None, None, None, "fake", kits, project="shop", repo_name="frontend")
    assert environ("shop-frontend", "supervisor")[CLI_NAME] == canary
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", "spawn sleep 0")
    assert environ("shop-frontend", "worker")[API_NAME] == f"{canary}-api"
    run = runs.start("shop-frontend", "tiny", "build it", notices=[])
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", f"spawnrun {run.name}")
    runner = wait_for(
        lambda: next((a for a in state.list_agents("shop-frontend") if a.run), None),
        "the run's worker",
        "shop-frontend",
    )
    assert environ("shop-frontend", runner.name)[CLI_NAME] == canary
    (projects.folder("shop") / "frontend" / "brief.md").write_text("# Fix the login\n")
    _approve_and_start("shop-frontend", "fix-login")
    assert environ("fix-login", "supervisor")[CLI_NAME] == canary

    # While the agents run: no process's arguments, not the tmux server's environment.
    processes = subprocess.run(["ps", "-ww", "-eo", "args"], capture_output=True, text=True)
    assert processes.returncode == 0 and "lado" in processes.stdout
    assert canary not in processes.stdout
    server_env = subprocess.run(
        ["tmux", "-L", tmux.socket(), "show-environment", "-g"], capture_output=True, text=True
    )
    assert server_env.returncode == 0 and server_env.stdout
    assert canary not in server_env.stdout
    home = state.home_path()
    # The launch files were read and removed by the windows that run.
    assert sorted(home.rglob("env.json")) == []
    secrets_folder = project_secrets.folder("shop")
    # fake-agents/ is the fake agent's own report of its environment, as a real CLI's
    # memory: not LADO's record.
    skip = [secrets_folder, home / "fake-agents"]
    assert files_holding(home, canary.encode(), skip) == []

    # What the human runs and reads.
    for args in (
        ("project", "show", "shop"),
        ("doctor",),
        ("bug-report",),
        ("log", "shop-frontend"),
        ("log", "fix-login"),
        ("ls",),
    ):
        done = lado(*args)
        said += [done.stdout, done.stderr]
    status, body = api.call("GET", "/api/projects/shop")
    assert status == 200 and API_NAME in body
    said.append(body)
    feed = api.feed(2.0)
    assert '"kind"' in feed  # the feed was read: its replay of the changes so far
    said.append(feed)

    # Telemetry's payload: what it queued, and what it sent.
    done = lado("telemetry", "send")
    said += [done.stdout, done.stderr]
    wait_for(lambda: shop.requests, "a post of the statistics", "shop-frontend")
    said += [json.dumps(body) for body in shop.requests]

    stop_all()
    server_run.stop()
    assert [text for text in said if canary in text] == []
    assert files_holding(home, canary.encode(), skip) == []
    assert sorted(path.name for path in secrets_folder.iterdir()) == [API_NAME, CLI_NAME]
