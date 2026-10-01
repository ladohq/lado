"""Agent hooks: how LADO learns what each agent is doing.

An agent CLI runs `lado hook <event>` at points in an agent's lifecycle (configured per
agent by its provider). The provider translates its native event into a neutral one; this
module keeps statuses and the inbox. A hook must never break the agent, so errors are
logged, not raised.
"""

import sys
import traceback

from lado import providers, runtime, state
from lado.runtime import CONFIRM_TIMEOUT, format_message, format_messages


def handle(
    provider: providers.Provider, event: providers.Event, session: str, agent: str
) -> str | None:
    """Update the agent's status for `event`. Returns the hook output to print, if any."""
    if event.kind == providers.SESSION_START:
        current = state.get_agent(session, agent)
        if current and current.status == state.STARTING:
            state.set_status(session, agent, state.BUSY if current.task else state.IDLE)
    elif event.kind == providers.PROMPT_SUBMIT:
        state.set_status(session, agent, state.BUSY)
        state.confirm_sent(session, agent, event.prompt, format_message)
    elif event.kind == providers.WAITING:
        state.set_status(session, agent, state.WAITING)
    elif event.kind == providers.TURN_END:
        # Mark idle first, then collect the inbox: lado.runtime.send_message does it the
        # other way round, so a message sent in between is always picked up by one of us.
        state.set_status(session, agent, state.IDLE)
        state.requeue_unconfirmed(session, agent, CONFIRM_TIMEOUT)
        if not provider.capabilities.deliver_on_turn_end:
            runtime.deliver_pending(session, agent)
            return None
        pending = state.take_pending(session, agent, state.DELIVERED)
        if pending:
            state.set_status(session, agent, state.BUSY)
            return provider.continue_output(format_messages(pending))
    elif event.kind == providers.SESSION_END:
        state.set_status(session, agent, state.STOPPED)
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
        with open(state.home() / "hooks.log", "a") as log:
            log.write(f"{event} {session}/{agent}\n{traceback.format_exc()}\n")
    return 0
