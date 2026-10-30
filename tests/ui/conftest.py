"""UI end-to-end tests: Chromium (pytest-playwright) against a real `lado server`, with
sessions of the fake agent, isolated like the integration tests (a temp LADO_HOME, a tmux
server of each test's own). Run them with `make test-ui` (marker `ui`).

Each test saves a screenshot of every screen it checks to <temp dir>/lado-ui-shots/, outside
the tree, for the reviewer: `shot(page, name)`.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import agent_helpers
import leftovers
import pytest
from agent_helpers import refuse_unless_isolated

# The fake agent's provider lives beside the integration tests.
sys.path.insert(0, str(Path(__file__).parent.parent / "integration"))
import fake_provider  # noqa: E402

from lado import providers  # noqa: E402
from lado.server import auth  # noqa: E402
from lado.server import run as server_run  # noqa: E402

SHOTS = Path(tempfile.gettempdir()) / "lado-ui-shots"


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    refuse_unless_isolated()
    for fake in fake_provider.FAKES:
        monkeypatch.setitem(providers._PROVIDERS, fake.name, fake)
    yield
    kill_tmux_server(socket)
    leftovers.fail_if(leftovers.sweep(lado_home), "the test")


@pytest.fixture(autouse=True)
def _workspace(tmp_path, monkeypatch):
    """The servers' workspace is in tmp_path (LADO_REPOS, not made), never the user's
    ~/workspace, which the system panel's checks would write a probe in. A test of its own
    sets LADO_REPOS, or takes home_server for the ~/workspace default."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "workspace"))


def _serve(tmp_path, env):
    with open(tmp_path / "server.out", "w") as out:
        process = subprocess.Popen(
            [sys.executable, str(fake_provider.LADO), "server", "--port", "0"],
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
        )
    try:
        yield {**server_run.wait_ready(), "token": auth.token()}
    finally:
        server_run.stop()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def logins(tmp_path, monkeypatch):
    """The fake provider "fake-login"'s login file (absent: not logged in), taken before
    `server`, in the environment of the server and of the agents; the waiting window knows
    the fake providers; the real CLIs' status commands read nothing of the user's."""
    marker = tmp_path / "fake-login"
    monkeypatch.setenv("FAKE_AGENT_LOGIN", str(marker))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setattr(providers, "lado_command", fake_provider.lado_command)
    return marker


@pytest.fixture
def server(tmp_path):
    """A real `lado server` on a free port; its server.json. It is `lado` with the fake
    providers (fake_provider.py), so a session it starts runs the fake agent. Stopped after
    the test, and killed when it does not stop (also when it never got ready)."""
    yield from _serve(tmp_path, os.environ)


@pytest.fixture
def home_server(tmp_path):
    """`server` whose process has its HOME in tmp_path (<tmp>/home, made) and no
    LADO_REPOS: its workspace is the default <tmp>/home/workspace, not made. Only the
    server's: the test's own HOME stays, which the browser's files are found by."""
    home = tmp_path / "home"
    home.mkdir()
    env = {key: value for key, value in os.environ.items() if key != "LADO_REPOS"}
    yield from _serve(tmp_path, {**env, "HOME": str(home)})


@pytest.fixture
def slow_clone(tmp_path, monkeypatch):
    """A remote's URL, and a git whose clone prints progress and then waits, on the
    server's PATH (before the server starts); ls-remote is the real git's."""
    url = agent_helpers.bare_remote(tmp_path)  # by the real git
    for key, value in agent_helpers.fake_git(tmp_path / "fake", "slow-clone").items():
        monkeypatch.setenv(key, value)
    return url


@pytest.fixture
def shot(request):
    """Save a screenshot of the page as <temp dir>/lado-ui-shots/<test>[-<name>].png. A full
    page's capture resizes the viewport for a moment, which a touch emulation does not
    survive: `full_page=False` keeps the window as it is."""

    def save(page, name: str = "", full_page: bool = True) -> Path:
        SHOTS.mkdir(exist_ok=True)
        path = SHOTS / f"{request.node.name}{'-' + name if name else ''}.png"
        page.screenshot(path=str(path), full_page=full_page)
        print(f"screenshot: {path}")
        return path

    return save
