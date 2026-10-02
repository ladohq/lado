"""Integration tests: real tmux, git, hooks and MCP servers, with a fake agent instead of an LLM.

Run them with `uv run pytest -m integration` (or `make test-integration`).
"""

import shutil
import time
import uuid

import fake_provider
import pytest
from agent_helpers import refuse_unless_isolated

from lado import loop, providers, state


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"  # a tmux server of its own for each test
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    refuse_unless_isolated()
    for fake in fake_provider.FAKES:
        monkeypatch.setitem(providers._PROVIDERS, fake.name, fake)
    yield
    kill_tmux_server(socket)
    no_loop_left()


def no_loop_left(timeout: float = 5 * loop.INTERVAL) -> None:
    """Session loops end by themselves once their tmux session is gone: fail a test that
    leaves one running."""
    deadline = time.monotonic() + timeout
    folder = state.home() / "loop"
    locks = sorted(folder.glob("*.lock")) if folder.exists() else []
    while left := [p.stem for p in locks if loop.running(p.stem)]:
        if time.monotonic() > deadline:
            pytest.fail(f"session loops still running {timeout:g}s after the test: {left}")
        time.sleep(0.1)
