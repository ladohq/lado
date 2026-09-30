"""Claude Code hooks: how LADO learns what each agent is doing.

Claude Code runs `lado hook <event>` at points in an agent's lifecycle (configured per
agent in lado.runtime). A hook must never break the agent, so errors are logged, not raised.
"""

import json
import sys
import traceback

from lado import state
from lado.runtime import CONFIRM_TIMEOUT, format_messages


def handle(event: str, session: str, agent: str, payload: dict) -> dict | None:
    """Update the agent's status for `event`. Returns the JSON to print, if any."""
    if event == "SessionStart":
        current = state.get_agent(session, agent)
        if current and current.status == state.STARTING:
            state.set_status(session, agent, state.BUSY if current.task else state.IDLE)
    elif event == "UserPromptSubmit":
        state.set_status(session, agent, state.BUSY)
        state.confirm_sent(session, agent, payload.get("prompt", ""))
    elif event == "Notification":
        kind = payload.get("notification_type") or payload.get("message", "")
        if "permission" in kind.lower():
            state.set_status(session, agent, state.WAITING)
    elif event == "Stop":
        # Mark idle first, then collect the inbox: lado.runtime.send_message does it the
        # other way round, so a message sent in between is always picked up by one of us.
        state.set_status(session, agent, state.IDLE)
        state.requeue_unconfirmed(session, agent, CONFIRM_TIMEOUT)
        pending = state.take_pending(session, agent, state.DELIVERED)
        if pending:
            state.set_status(session, agent, state.BUSY)
            # Blocking the stop makes Claude Code continue with `reason` as its next input.
            return {"decision": "block", "reason": format_messages(pending)}
    elif event == "SessionEnd":
        state.set_status(session, agent, state.STOPPED)
    return None


def main(event: str, session: str, agent: str, instance: str) -> int:
    try:
        raw = sys.stdin.read()
        current = state.get_agent(session, agent)
        if current is None or current.instance != instance:
            return 0  # an earlier launch of this agent, e.g. exiting after `lado stop`
        payload = json.loads(raw) if raw.strip() else {}
        output = handle(event, session, agent, payload)
        if output:
            print(json.dumps(output))
    except Exception:
        with open(state.home() / "hooks.log", "a") as log:
            log.write(f"{event} {session}/{agent}\n{traceback.format_exc()}\n")
    return 0
