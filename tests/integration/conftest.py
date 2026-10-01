"""Integration tests: real tmux, git, hooks and MCP servers, with a fake agent instead of an LLM.

Run them with `uv run pytest -m integration` (or `make test-integration`).
"""

import re
import shutil
import tempfile
import uuid
from pathlib import Path

import fake_provider
import pytest

from lado import providers, state, tmux


def _refuse_unless_isolated() -> None:
    """These tests start and kill tmux servers and agents: never let them near a live LADO."""
    home = state.home().resolve()
    if not home.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        pytest.exit(f"integration tests need LADO_HOME in a temp dir, not {home}", returncode=2)
    if not re.fullmatch(r"lado-test-[0-9a-f]{8}", tmux.socket()):
        pytest.exit(f"integration tests need a test tmux socket, not {tmux.socket()}", returncode=2)


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"  # a tmux server of its own for each test
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    _refuse_unless_isolated()
    for fake in fake_provider.FAKES:
        monkeypatch.setitem(providers._PROVIDERS, fake.name, fake)
    yield
    kill_tmux_server(socket)
