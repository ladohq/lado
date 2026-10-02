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


@pytest.fixture
def server(tmp_path):
    """A real `lado server` on a free port; its server.json. Stopped after the test, and no
    server process may be left."""
    with open(tmp_path / "server.out", "w") as out:
        process = subprocess.Popen(
            [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
            stdout=out,
            stderr=subprocess.STDOUT,
            env=os.environ,
        )
    try:
        yield {**server_run.wait_ready(), "token": auth.token()}
    finally:
        server_run.stop()
        process.wait(timeout=10)


@pytest.fixture
def shot(request):
    """Save a screenshot of the page as <temp dir>/lado-ui-shots/<test>[-<name>].png."""

    def save(page, name: str = "") -> Path:
        SHOTS.mkdir(exist_ok=True)
        path = SHOTS / f"{request.node.name}{'-' + name if name else ''}.png"
        page.screenshot(path=str(path), full_page=True)
        print(f"screenshot: {path}")
        return path

    return save
