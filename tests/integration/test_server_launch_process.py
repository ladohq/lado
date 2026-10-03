"""Launch and session control through a real UI server: the server is `lado` with the fake
providers (fake_provider.py), so the sessions it starts run the fake agent. No browser."""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import fake_provider
import pytest
from agent_helpers import init_repo, wait_for

from lado import loop, state, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration


@pytest.fixture
def server(tmp_path):
    """A real server that knows the fake providers; stopped after the test."""
    with open(tmp_path / "server.out", "w") as out:
        process = subprocess.Popen(
            [sys.executable, str(fake_provider.LADO), "server", "--port", "0"],
            stdout=out,
            stderr=subprocess.STDOUT,
            env=os.environ,
        )
    try:
        yield server_run.wait_ready()["url"]
    finally:
        server_run.stop()
        process.wait(timeout=10)


def call(url: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(
        url + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {auth.token()}",
            "Origin": url,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def supervisor_status(session: str) -> str | None:
    agent = state.get_agent(session, "supervisor")
    return agent.status if agent else None


def test_the_server_starts_stops_resumes_and_forgets_a_session(server, tmp_path):
    repo = init_repo(tmp_path / "app")
    where = {"kind": "folder", "path": str(repo)}
    status, started = call(server, "POST", "/api/sessions", {"where": where, "provider": "fake"})
    assert status == 200, started
    assert (started["session"]["name"], started["resumed"]) == ("app", False)
    wait_for(lambda: supervisor_status("app") == state.IDLE, "the supervisor idle", "app")
    assert tmux.has_session("app")
    wait_for(lambda: loop.running("app"), "the session loop", "app")

    status, taken = call(server, "POST", "/api/sessions", {"where": where, "provider": "fake"})
    assert status == 409 and taken["detail"]["repo"] == str(repo)

    status, stopped = call(server, "POST", "/api/sessions/app/stop")
    assert (status, stopped) == (200, {"dropped": 0})
    assert not tmux.has_session("app")

    status, resumed = call(server, "POST", "/api/sessions/app/resume", {"provider": "fake-paste"})
    assert status == 200, resumed
    assert resumed["resumed"] and resumed["changes"] == ["provider: fake -> fake-paste"]
    wait_for(lambda: supervisor_status("app") == state.IDLE, "the resumed supervisor", "app")
    assert state.get_agent("app", "supervisor").provider == "fake-paste"

    assert call(server, "POST", "/api/sessions/app/stop")[0] == 200
    status, forgotten = call(server, "DELETE", "/api/sessions/app")
    assert (status, forgotten) == (200, {"open_runs": [], "worktrees": []})
    assert state.get_session("app") is None
    assert not tmux.has_session("app")
