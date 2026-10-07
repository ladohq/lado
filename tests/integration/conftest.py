"""Integration tests: real tmux, git, hooks and MCP servers, with a fake agent instead of an LLM.

Run them with `uv run pytest -m integration` (or `make test-integration`).
"""

import shutil
import time
import uuid

import fake_provider
import pytest
from agent_helpers import refuse_unless_isolated

from lado import loop, providers, runtime, state

# LADO's timers, short: the session loop's interval and the delays before an unconfirmed
# message is typed again, for every process a test starts (the loop, the agents' hooks and
# lado mcp, the CLI) and for the test's own waits, which read loop.INTERVAL and
# runtime.RETRY_DELAYS. The first retry delay must outlast the time from a paste to its
# prompt-submit hook's confirmation, else the loop types a message again that the agent
# took already, and the fake agent runs it twice: under `-n auto` that took 0.18 s at the
# median, 0.6 s at p99 and 0.7 s at most (2026-10-07, 8 workers on 4+4 cores, load up to
# 130). 2 s is about three times that most; the later delays, after a paste that no hook
# took, stay short.
LOOP_INTERVAL = "0.25"
RETRY_DELAYS = "2,0.5,0.5"


@pytest.fixture(autouse=True)
def isolated(lado_home, monkeypatch, kill_tmux_server):
    if shutil.which("tmux") is None:
        pytest.skip("tmux not installed")
    socket = f"lado-test-{uuid.uuid4().hex[:8]}"  # a tmux server of its own for each test
    monkeypatch.setenv("LADO_TMUX_SOCKET", socket)
    monkeypatch.setenv("LADO_LOOP_INTERVAL", LOOP_INTERVAL)
    monkeypatch.setattr(loop, "INTERVAL", loop.interval_from(LOOP_INTERVAL))
    retry_delays(monkeypatch, RETRY_DELAYS)
    refuse_unless_isolated()
    for fake in fake_provider.FAKES:
        monkeypatch.setitem(providers._PROVIDERS, fake.name, fake)
    yield
    kill_tmux_server(socket)
    no_loop_left()


def retry_delays(monkeypatch, value: str | None) -> None:
    """LADO_RETRY_DELAYS `value` (None: unset, LADO's own) for the processes a test starts
    and for the test."""
    if value is None:
        monkeypatch.delenv("LADO_RETRY_DELAYS", raising=False)
    else:
        monkeypatch.setenv("LADO_RETRY_DELAYS", value)
    monkeypatch.setattr(runtime, "RETRY_DELAYS", runtime.retry_delays_from(value))


@pytest.fixture
def production_retry_delays(monkeypatch):
    """LADO's own retry delays, for a test that moves time itself (agents' seen_at and
    messages' sent_at back by a delay), or whose agent's turns go on longer than a short
    delay without a hook: with short delays the session loop would type a message again
    before the test does, or while the turn still goes on."""
    retry_delays(monkeypatch, None)


def no_loop_left() -> None:
    """Session loops end by themselves once their tmux session is gone: fail a test that
    leaves one running five loop intervals after."""
    timeout = 5 * loop.INTERVAL
    deadline = time.monotonic() + timeout
    folder = state.home() / "loop"
    locks = sorted(folder.glob("*.lock")) if folder.exists() else []
    while left := [p.stem for p in locks if loop.running(p.stem)]:
        if time.monotonic() > deadline:
            pytest.fail(f"session loops still running {timeout:g}s after the test: {left}")
        time.sleep(0.02)
