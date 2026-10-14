"""The smoke scenario, the same for each provider: real CLI, real tmux, hooks, `lado mcp` and
SQLite, no model (tests/smoke/conftest.py). It shows that a session starts, the CLI's hooks
run, LADO's messages reach it, a worker starts, and `lado stop` leaves no process."""

import agent_helpers
import pytest
from real_clis import agent_processes, answer_dialogs, check_gone, status

from lado import loop, runtime, state, tmux

pytestmark = pytest.mark.smoke

SESSION = "smoke"
RECEIVED = (state.DELIVERED, state.READ)
HUMAN_SAYS = "Smoke test: a line from the human\nwith a body to read"
TASK = "Smoke test: no model answers; this task only has to reach you."
# Codex CLI 0.162 runs no hook for a turn that ends on an API error: the agent stays busy,
# so nothing more is handed over to it, and no turn_error is recorded.
CODEX_GAP = "A Codex agent whose turn ends on a model or API error stays busy"


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def answering(provider: str, agent: str, check):
    """`check` for wait_for, answering the agent's trust dialog first (each Codex agent has a
    home of its own, so it asks about its folder)."""

    def answered():
        answer_dialogs(provider, SESSION, agent)
        return check()

    return answered


def message(sender: str, recipient: str, summary: str) -> state.Message:
    [found] = [
        m
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient, m.summary) == (sender, recipient, summary)
    ]
    return found


def delivered(sender: str, recipient: str, summary: str):
    """A check that the message is delivered: the agent's own prompt-submit hook or plugin
    saw its line."""
    return lambda: message(sender, recipient, summary).state in RECEIVED


def events(agent: str, kind: str) -> list[state.Event]:
    return [e for e in state.list_events(SESSION) if (e.agent, e.kind) == (agent, kind)]


def test_a_session_starts_takes_messages_and_stops(smoke_repo, smoke_provider, fake_endpoint):
    provider = smoke_provider

    # 1. The session starts: its window, the agents' environment and PATH, the CLI.
    started = runtime.start_session(str(smoke_repo), SESSION, "bypassPermissions", provider)
    print(f"{provider}: started, warnings {started.warnings}")

    # 2. The supervisor's session-start hook ran: it is idle. Codex starts its session only
    # on its first input, LADO's FIRST_INPUT, which its prompt-submit hook confirms.
    if provider == "codex":
        print(f"codex: the session starts on its first input; then: {CODEX_GAP} (BACKLOG)")
        first = delivered(state.LADO, "supervisor", runtime.FIRST_INPUT)
        wait_for(answering(provider, "supervisor", first), "codex's first input delivered", 120)
    else:
        idle = answering(provider, "supervisor", lambda: status(SESSION, "supervisor") == "idle")
        wait_for(idle, "the supervisor to be idle after its session start", 120)
    assert loop.running(SESSION)

    # 3. The CLI listed LADO's MCP tools.
    wait_for(lambda: events("supervisor", state.MCP_READY), "the supervisor's mcp_ready", 60)

    # 4. A message with a body reaches the supervisor through its own hook, and its turn
    # fails at the endpoint: a turn's end with an error. Not Codex (above).
    if provider != "codex":
        runtime.write_as_human(SESSION, HUMAN_SAYS)
        summary = HUMAN_SAYS.splitlines()[0]
        wait_for(delivered(state.HUMAN, "supervisor", summary), "the human's message", 120)
        wait_for(lambda: events("supervisor", state.TURN_ERROR), "the supervisor's turn_error", 120)
        print(f"{provider}: turn_error {events('supervisor', state.TURN_ERROR)[0].detail!r}")
    # Codex posts its first request after its prompt-submit hook confirmed the input, so the
    # confirmation can come first; for the others the turn_error above came after it.
    wait_for(lambda: fake_endpoint.requests, "the supervisor's turn at the endpoint", 120)
    asked = len(fake_endpoint.requests)

    # 5. A worker: its worktree, a second agent, its hooks; its task reaches it.
    worker = runtime.spawn_worker(SESSION, TASK, name="w1")
    task = delivered(state.LADO, "w1", "your task")
    wait_for(answering(provider, "w1", task), "w1's task delivered", 120)
    wait_for(lambda: len(fake_endpoint.requests) > asked, "w1's turn at the endpoint", 120)
    assert worker.cwd and worker.branch
    print(f"{provider}: requests at the endpoint {fake_endpoint.requests}")

    # 6. lado stop: the windows, the loop and every process go.
    processes = agent_processes()
    runtime.stop_session(SESSION)
    assert not tmux.has_session(SESSION)
    check_gone(processes, "stop")
    wait_for(lambda: not loop.running(SESSION), "the session loop to end", 5 * loop.INTERVAL)
    agent_helpers.check_loop_ended_by_stop(SESSION)
