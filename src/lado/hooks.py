"""Agent hooks: how LADO learns what each agent is doing.

An agent CLI runs `lado hook <event>` at points in an agent's lifecycle (configured per
agent by its provider). The provider translates its native event into a neutral one; this
module keeps statuses and the inbox. A hook must never break the agent, so errors are
logged, not raised.
"""

import sys
import time
import traceback

from lado import providers, runtime, state
from lado.runtime import format_message, format_messages

# How long a session-start hook holds the agent's first turn for LADO's MCP server.
MCP_READY_TIMEOUT = 20.0


def _wait_for_mcp(session: str, agent: state.Agent) -> None:
    """Return when the agent's CLI has listed the tools of this launch's LADO MCP server
    (lado.mcp_server records it), or after MCP_READY_TIMEOUT."""
    deadline = time.monotonic() + MCP_READY_TIMEOUT
    while not state.has_event(session, agent.name, state.MCP_READY, agent.instance):
        if time.monotonic() >= deadline:
            _log(
                f"{session}/{agent.name}: LADO's MCP server listed no tools within "
                f"{MCP_READY_TIMEOUT}s; the first turn starts without them"
            )
            return
        time.sleep(0.1)


def _log(text: str) -> None:
    with open(state.home() / "hooks.log", "a") as log:
        log.write(f"{text}\n")


def handle(
    provider: providers.Provider, event: providers.Event, session: str, agent: str
) -> str | None:
    """Update the agent's status for `event`. Returns the hook output to print, if any."""
    # First of all: the agent is alive, so what a dialog swallowed can go to it again.
    state.seen(session, agent)
    if event.kind == providers.SESSION_START:
        current = state.get_agent(session, agent)
        # Claude Code starts the first turn when its session-start hooks are done, whether
        # its MCP servers are connected or not, and defers the tools of a server that
        # connects later behind its tool search, alwaysLoad or not. A weak model then may
        # not find flow_advance or send_message. So the hook waits for LADO's server.
        if current and provider.capabilities.hold_first_turn:
            _wait_for_mcp(session, current)
        if current and current.status == state.STARTING:
            if current.task:
                state.set_status(session, agent, state.BUSY)  # its first turn: the task
            else:
                _idle(provider, session, agent)
    elif event.kind == providers.PROMPT_SUBMIT:
        state.set_status(session, agent, state.BUSY)
        state.confirm_sent(session, agent, event.prompt, format_message)
    elif event.kind == providers.WAITING:
        state.wait(session, agent, event.key)
    elif event.kind == providers.RESUMED:
        # Busy again; its queue waits for the turn's end, as for any busy agent.
        state.resume(session, agent, event.key)
    elif event.kind == providers.TURN_END:
        # The human's messages this turn got: did it write to the human? Before the inbox is
        # handed over, so what the next turn gets is checked when that one ends.
        state.check_replies(session, agent)
        return _idle(provider, session, agent, turn_end=True)
    elif event.kind == providers.CONVERSATION_END:
        # Not ready while the next conversation loads: messages wait in the queue.
        state.set_status(session, agent, state.STARTING)
    elif event.kind == providers.CONVERSATION_START:
        # Ready again, as after the session's start.
        _idle(provider, session, agent)
    elif event.kind == providers.SESSION_END:
        state.set_status(session, agent, state.STOPPED)
    return None


def _idle(
    provider: providers.Provider, session: str, agent: str, turn_end: bool = False
) -> str | None:
    """The agent is idle: hand over its queue. Every switch to idle goes through here.

    Mark idle first, then take the queue: lado.runtime.send_message does it the other way
    round, so a message sent in between is always handed over by exactly one of us. At a
    turn's end a provider that can carries the queue on in the hook's output (returned);
    otherwise the messages are typed in. Then what was typed and never confirmed."""
    state.set_status(session, agent, state.IDLE)
    if not (turn_end and provider.capabilities.deliver_on_turn_end):
        runtime.deliver_pending(session, agent)
    elif pending := state.take_pending(session, agent, state.DELIVERED, state.BUSY):
        return provider.continue_output(format_messages(pending))
    runtime.sweep(session, agent)
    return None


def main(event: str, session: str, agent: str, instance: str) -> int:
    try:
        payload = sys.stdin.read()
        current = state.get_agent(session, agent)
        if current is None or current.instance != instance:
            return 0  # an earlier launch of this agent, e.g. exiting after `lado stop`
        provider = providers.get(current.provider)
        neutral = provider.parse_event(event, payload)
        output = handle(provider, neutral, session, agent) if neutral else None
        if output:
            print(output)
    except Exception:
        _log(f"{event} {session}/{agent}\n{traceback.format_exc()}")
    return 0
