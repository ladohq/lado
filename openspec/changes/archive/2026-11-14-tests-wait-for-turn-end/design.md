## Context

The integration tests drive the fake agent (`tests/integration/fake_agent.py`) by sending it
human messages; it runs each command typed into its terminal. A message sent while the agent is
busy reaches it either typed at its turn's end, or, when the turn makes another LADO tool call,
inside that call's result (`runtime.MID_TURN`), where the fake agent only sees text. At a clean
turn's end `hooks.handle` queues `REPLY_REMINDER` for every human message the turn answered in no
chat (`state.check_replies`), then `_idle` marks the agent idle and hands its queue over. On
`PROMPT_SUBMIT` the hook marks it busy before it confirms the typed messages.

## Decisions

### D1: Wait for "settled", not for "idle" or a later side effect

`agent_helpers.settled(session, agent)` is true when the agent's status is idle and no message to
it is pending or sent. Idle alone is not enough: the reminder is queued just before the agent
turns idle and makes it busy again a moment later. A side effect (the gate reaching the
supervisor, a question existing) is not enough: it happens inside the turn. The order in
`hooks.py` (queue the reminder, then idle; busy, then confirm) means "settled" cannot be seen
between a turn and the input it still owes. A delivered message whose body was never read
(`state.UNRECEIVED` counts it) does not block it: the fake agent reads bodies only when told to,
so waiting on it would hang.

Alternatives: wait for the reminder message itself (ties each test to LAD-274's text and breaks
when a command is answered in the chat); pick the step by its summary instead of "the last
message" (hides the race in `test_flow_runs.py` but not in `test_session_start.py`, and drops the
assertion that the step is the newest message).

### D2: Fix the tests, not the fake agent

The fake agent keeps running only typed input. Making it run commands from mid-turn messages
would fix `test_session_start.py` alone, change a contract other tests rely on, and make a test's
command run inside another command's turn, an order no real test asks for.

### D3: Reproduce once, do not commit a forced race

Each race is shown once on the old test by widening its window by hand (AC-4), so the fix is
known to remove the cause, not just to pass. A committed test that forces the window would test
the test helpers' ordering, which `settled`'s unit tests already cover at the lowest layer.

### D4: Scope to the two failed tests and their shared helper

`to_the_gate` serves both gate tests in `test_flow_runs.py`, so both are fixed. Other tests of the
same shape are left to a BACKLOG.md entry (proposal, Out of scope).

### D5: No delta spec

No behaviour of LADO changes, and the wait is a way of writing tests, not a rule a check could
enforce: it goes to `docs/testing.md` and the helper's docstring (`skip_specs` in
`.openspec.yaml`), as earlier test-only changes did.

## Risks

- A test that waits for `settled` where the agent never settles (a message stuck in `sent`)
  times out with the usual diagnostics, which name the message's state: that is a real failure.
