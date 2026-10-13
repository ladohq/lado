"""Agent hooks: how LADO learns what each agent is doing.

An agent CLI runs `lado hook <event>` at points in an agent's lifecycle (configured per
agent by its provider). The provider translates its native event into a neutral one; this
module keeps statuses and the inbox. A hook must never break the agent, so errors are
logged, not raised.
"""

import contextlib
import json
import os
import sys
import time
import traceback

from lado import fingerprint, providers, runtime, state, telemetry
from lado.runtime import format_message

# How long a session-start hook holds the agent's first turn for LADO's MCP server.
MCP_READY_TIMEOUT = 20.0
MCP_READY_POLL = 0.02  # seconds between two looks; each look is one small query

# A read-only agent's fingerprint of its turn's start (lado.fingerprint), in its config
# folder, which goes with the agent: {"state": "open" | "continued" | "closed",
# "fingerprint": ...}. Open from the turn's start until its end, whose fingerprint it then
# holds, closed; continued when the queue went in the turn-end hook's output, so that end
# starts the next turn.
OPEN_STATES = ("open", "continued")
BASELINE = "read-only-baseline.json"
# Of the time the CLI gives a hook (Provider.hook_limit), what the fingerprint leaves for
# the rest of the hook: the start of Python before main, and handing the queue over and the
# sweep after the fingerprint.
STARTUP_RESERVE = 0.5
QUEUE_RESERVE = 1.0


def deadline(provider: providers.Provider, native: str, started: float) -> float | None:
    """When (time.monotonic) a hook of `native` started at `started` must be done with its
    fingerprint; None when the CLI waits for it with no limit."""
    limit = provider.hook_limit(native)
    return None if limit is None else started + limit - STARTUP_RESERVE - QUEUE_RESERVE


def budget(by: float | None) -> float:
    """The seconds a fingerprint may take now, to be done `by` (deadline)."""
    if by is None:
        return fingerprint.BUDGET
    return min(fingerprint.BUDGET, by - time.monotonic())


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
    telemetry.bounded_append(state.home() / "hooks.log", f"{text}\n")


def _baseline_path(me: state.Agent):
    return providers.base.config_path(me) / BASELINE


def _read_baseline(me: state.Agent) -> dict | None:
    try:
        return json.loads(_baseline_path(me).read_text())
    except (OSError, ValueError):
        return None


def _write_baseline(me: state.Agent, kind: str, taken: fingerprint.Fingerprint | None) -> None:
    path = _baseline_path(me)
    if not path.parent.is_dir():
        return  # the agent's config folder is gone with the agent
    temporary = path.with_name(f"{BASELINE}.{os.getpid()}")
    temporary.write_text(json.dumps({"state": kind, "fingerprint": taken}))
    os.replace(temporary, path)


def _fingerprint(session: str, me: state.Agent, by: float | None) -> fingerprint.Fingerprint | None:
    """The fingerprint of the read-only agent's repository now; None, told as
    repo_check_failed, when it cannot be taken in time."""
    left = budget(by)
    if left < fingerprint.MIN_BUDGET:
        reason = "no time left in the hook"
    else:
        try:
            return fingerprint.take(me.cwd, state.get_session(session).repo, left)
        except fingerprint.FingerprintError as error:
            reason = str(error)
    _log(f"{session}/{me.name}: could not check {me.name}'s repository: {reason}")
    runtime.repo_check_failed(session, me.name, reason)
    return None


def _compare(session: str, me: state.Agent, now, end_seen: bool) -> None:
    """Tell the changes since the open baseline of its turn's start, if there is one."""
    baseline = _read_baseline(me)
    if baseline is None:
        _log(f"{session}/{me.name}: no fingerprint of its turn's start; nothing to compare")
    elif baseline.get("state") in OPEN_STATES and baseline.get("fingerprint"):
        if changes := fingerprint.diff(baseline["fingerprint"], now):
            runtime.repo_changed(session, me.name, changes, end_seen)


def _turn_start(session: str, me: state.Agent, by: float | None) -> None:
    """A read-only agent's turn starts: its fingerprint is the turn's open baseline. One
    still open means the previous turn ended with no turn-end hook (e.g. the human's Esc in
    Claude Code): compared first, as far as now. A continued one is replaced: the turn
    that goes on from the hook's output runs this hook too (OpenCode's and Kilo's
    chat.message for promptAsync), and its end was seen."""
    now = _fingerprint(session, me, by)
    if now is None:
        _write_baseline(me, "closed", None)  # nothing to compare this turn with
        return
    baseline = _read_baseline(me)
    if baseline and baseline.get("state") == "open":
        _compare(session, me, now, end_seen=False)
    _write_baseline(me, "open", now)


def _turn_end(session: str, me: state.Agent, by: float | None) -> fingerprint.Fingerprint | None:
    """A read-only agent's turn ends: compared with its start, then closed with this
    fingerprint; before the agent is idle, so before any queue is handed over (_idle)."""
    now = _fingerprint(session, me, by)
    if now is not None:
        _compare(session, me, now, end_seen=True)
    _write_baseline(me, "closed", now)
    return now


def handle(
    provider: providers.Provider,
    event: providers.Event,
    session: str,
    agent: str,
    deadline: float | None = None,
) -> str | None:
    """Update the agent's status for `event`. Returns the hook output to print, if any.
    `deadline` (hooks.deadline): when the CLI stops waiting for the hook, for a read-only
    agent's fingerprint."""
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
            # Ready: its first input (a worker's task, a resumed supervisor's messages from
            # LADO) is in its queue.
            _idle(provider, session, agent)
    elif event.kind == providers.PROMPT_SUBMIT:
        state.set_status(session, agent, state.BUSY)
        state.confirm_sent(session, agent, event.prompt, format_message)
        me = state.get_agent(session, agent)
        if me and me.read_only:
            _turn_start(session, me, deadline)
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
            runtime.turn_failed(session, agent, event.error, event.transient, event.background)
        else:
            state.reset_resumes(session, agent)
        me = state.get_agent(session, agent)
        # The lead's turn got requests for its recommendation and gave none: said so on
        # their cards. Not when LADO resumes it after a temporary error: its turn goes on.
        # Before the queue is handed over, so a request it gets now is not counted.
        if agent == runtime.SUPERVISOR and me and me.resume_at is None:
            state.recommendations_missed(session)
        ended = _turn_end(session, me, deadline) if me and me.read_only else None
        output = _idle(provider, session, agent, event)
        if output and ended is not None:
            # The queue went in this hook's output: this end is the start of the turn that
            # goes on from it, which runs no prompt-submit hook in Claude Code and Codex.
            _write_baseline(me, "continued", ended)
        return output
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
    """The agent is idle, or `background` at a turn's end with work it started still running
    (Event.background): either takes input, so hand over its queue. Every switch to them
    goes through here, in this order:

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
    background = turn_end is not None and turn_end.background
    state.set_status(session, agent, state.BACKGROUND if background else state.IDLE)
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
    began = time.monotonic()  # first: the CLI's limit for the hook runs from its start
    started = time.time()
    provider_name, where = None, event  # for the journal: the neutral event once known
    try:
        payload = sys.stdin.read()
        current = state.get_agent(session, agent)
        if current is None or current.instance != instance:
            return 0  # an earlier launch of this agent, e.g. exiting after `lado stop`
        provider_name = current.provider
        provider = providers.get(current.provider)
        neutral = provider.parse_event(event, payload)
        where = neutral.kind if neutral else event
        by = deadline(provider, event, began)
        output = handle(provider, neutral, session, agent, by) if neutral else None
        if output:
            print(output, flush=True)
            if provider.capabilities.output_taken_when_printed:
                _mark_printed(event, session, agent, started)
    except state.SchemaError as exc:
        # E.g. LADO upgraded in place under the running session: the database stays as it is.
        _log(f"{event} {session}/{agent}: {exc}")
    except Exception as exc:
        _log(f"{event} {session}/{agent}\n{traceback.format_exc()}")
        telemetry.record(f"hook:{where}", exc, provider_name, session, agent)
        # What it took for its output was never printed.
        with contextlib.suppress(Exception):  # logged above; the sweep's rule still holds
            state.output_not_taken(session, agent, since=started)
    return 0


def _mark_printed(event: str, session: str, agent: str, started: float) -> None:
    """Mark what this hook handed over for its output printed, after the print: a hook
    killed in between leaves it unmarked, and it may come twice, never not at all. An error
    is logged and leaves it unmarked; it is never output_not_taken, as the CLI has it."""
    try:
        state.output_printed(session, agent, since=started)
    except Exception:
        _log(f"{event} {session}/{agent}: marking the output printed\n{traceback.format_exc()}")
