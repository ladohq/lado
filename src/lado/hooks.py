"""Agent hooks: how LADO learns what each agent is doing.

An agent CLI runs `lado hook <event>` at points in an agent's lifecycle (configured per
agent by its provider). The provider translates its native event into a neutral one; this
module keeps statuses and the inbox. A hook must never break the agent, so errors are
logged, not raised.
"""

import contextlib
import sys
import time
import traceback

from lado import providers, runtime, state
from lado.runtime import format_message

# How long a session-start hook holds the agent's first turn for LADO's MCP server.
MCP_READY_TIMEOUT = 20.0
MCP_READY_POLL = 0.02  # seconds between two looks; each look is one small query


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
        time.sleep(MCP_READY_POLL)


def _log(text: str) -> None:
    with open(state.home() / "hooks.log", "a") as log:
        log.write(f"{text}\n")


def handle(
    provider: providers.Provider, event: providers.Event, session: str, agent: str
) -> str | None:
    """Update the agent's status for `event`. Returns the hook output to print, if any."""
    if event.kind == providers.HOOK_ERROR:
        # Not a sign that the agent took anything: no hook followed the hand-over it is
        # about, so sweep types those messages in (runtime._plan).
        _log(f"{session}/{agent}: {event.error}")
        return None
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
        # An agent whose CLI asks the human first waits from its start (state.block): this
        # hook says the human answered. Any other wait stays: a compaction starts a session
        # too.
        held = current and current.status == state.WAITING and agent in state.block_reasons(session)
        if current and (current.status == state.STARTING or held):
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
        # A turn that went on from the previous turn-end hook's output got the messages in
        # it: only those, as another Stop hook of the user's may have made it go on too. A
        # turn's end that does not say so did not take them: they wait to be typed in.
        if event.continued:
            state.confirm_channel(session, agent, state.HOOK_OUTPUT)
        else:
            state.output_not_taken(session, agent)
        # The human's messages this turn got: did it write to the human? Before the inbox is
        # handed over, so what the next turn gets is checked when that one ends.
        state.check_replies(session, agent)
        # Before the agent is idle: a resume planned for it holds while it stays idle, and
        # is dropped when the queue makes it busy now (state.schedule_resume).
        if event.error:
            runtime.turn_failed(session, agent, event.error, event.transient)
        else:
            state.reset_resumes(session, agent)
        return _idle(provider, session, agent, event)
    elif event.kind == providers.CONVERSATION_END:
        # Not ready while the next conversation loads: messages wait in the queue.
        state.set_status(session, agent, state.STARTING)
    elif event.kind == providers.CONVERSATION_START:
        # Ready again, as after the session's start.
        _idle(provider, session, agent)
    elif event.kind == providers.SESSION_END:
        runtime.agent_ended(session, agent, "its CLI exited")
    return None


def _idle(
    provider: providers.Provider,
    session: str,
    agent: str,
    turn_end: providers.Event | None = None,
) -> str | None:
    """The agent is idle: hand over its queue. Every switch to idle goes through here, in
    this order:

    1. At a turn's end (`turn_end`) that went on from the previous turn-end hook's output
       (Event.continued), handle has confirmed the messages in that output already; at
       one that did not, it has left them to be typed in (state.output_not_taken).
    2. Mark idle, then 3. take the queue (runtime.hand_over): what 1 confirmed does not
       keep the next batch back, so a chain of turns that go on from the hook's output
       gets each new batch at once. lado.runtime.send_message queues first and takes
       second, so a message sent in between is handed over by exactly one of us. At a
       turn's end a provider that can carries the queue on in the hook's output (returned)
       unless its CLI ignores that output; otherwise the messages are typed in.
    4. Sweep what was handed over and never confirmed (runtime.sweep).

    If the hook fails after 3, or the CLI does not take its output, the messages stay sent
    and sweep deals with them (runtime._plan)."""
    state.set_status(session, agent, state.IDLE)
    by_output = (
        turn_end is not None
        and not turn_end.output_ignored
        and provider.capabilities.deliver_on_turn_end
    )
    text = runtime.hand_over(session, agent, state.HOOK_OUTPUT if by_output else state.TYPED)
    runtime.sweep(session, agent)
    return provider.continue_output(text) if by_output and text else None


def main(event: str, session: str, agent: str, instance: str) -> int:
    """Run the hook for a native `event` and print its output. An error is logged and the
    hook exits 0; messages it handed over for its output before the error are sent, not
    delivered, and wait to be typed in by the sweep's rule (runtime._plan)."""
    started = time.time()
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
    except state.SchemaError as exc:
        # E.g. LADO upgraded in place under the running session: the database stays as it is.
        _log(f"{event} {session}/{agent}: {exc}")
    except Exception:
        _log(f"{event} {session}/{agent}\n{traceback.format_exc()}")
        # What it took for its output was never printed.
        with contextlib.suppress(Exception):  # logged above; the sweep's rule still holds
            state.output_not_taken(session, agent, since=started)
    return 0
