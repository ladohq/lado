Task: LAD-284

## Why

Two integration tests failed once in CI and passed on a rerun (found in LAD-280, PR #300,
2026-11-14). Their logs show that neither waited too short: each went on before the fake
agent's turn was over, and a message LADO handles at a turn's end overtook the test.

1. `tests/integration/test_session_start.py::test_an_approved_proposal_starts_an_independent_session_with_the_brief`
   (run 43622349434, `integration (3.10, 1)`, "timed out after 30s waiting for start_session's
   result; agents: supervisor idle"). The test answers the supervisor's question and at once
   sends `start_session b 4` from the human, while the supervisor is still in its `askhuman`
   turn. LADO delivers a message to a busy agent with the result of its next tool call
   (openspec mid-turn-messages): the log shows `ask_human`'s result ending in "Messages that
   came during your turn: … [from human] start_session b 4". The fake agent runs commands only
   from what is typed into its terminal, so the command was read as text and never run; the
   turn ended, LADO reminded it of the unanswered human message, and the test waited 30 s for
   a call that could no longer come. Any wait would have timed out.
2. `tests/integration/test_flow_runs.py::test_the_humans_files_with_a_gates_answer_reach_the_next_steps_worker`
   (Windows probe run 43622342944, WSL, `make test-integration`): not a timeout but an
   assertion. `to_the_gate` sends the worker `advance <run> done` from the human and returns
   once the gate reaches the supervisor, which happens inside the worker's turn. At that turn's
   end the hook queues LADO's reminder "your answer to the human's message #6 went only to your
   terminal…" (LAD-274, 2026-11-11). Under load the reminder was queued after the test's gate
   answer, so the test's "last message to the worker" was the reminder, not the step:
   `assert 'your answer ...e do nothing.' == 'flow reviewe...t: step build'`.

The common cause: a test sends the next command, or reads "the last message", while the agent
still has a turn or its turn-end bookkeeping in flight. LAD-274 made this likelier: a human
command the fake agent answers in no chat now adds one more message and one more turn after
it. The product behaves as specified in both cases; the defect is in the tests.

## What Changes

- A shared test helper `agent_helpers.settled(session, agent)`: the agent is idle and every
  message to it has left LADO's queue (none pending or sent but not yet taken). A reminder is
  queued before the hook marks the agent idle, and a typed message marks it busy before it is
  confirmed, so "settled" cannot be true while a turn or its reminder is still due.
- `test_session_start.py`: the approved-proposal test waits for the supervisor to be settled
  before each human command that follows another turn (the `askhuman` command and
  `start_session b <id>`).
- `test_flow_runs.py`: `to_the_gate` waits for the worker to be settled after the gate, so the
  turn-end reminder is in before the test answers the gate; the two tests that use it then find
  the step as the worker's last message, as they assert.
- One BACKLOG.md entry for the same shape elsewhere in `tests/integration/` (see Out of scope).

## Scope

In: `tests/agent_helpers.py` (the helper and its docstring, which says that the fake agent runs
only typed commands and treats a mid-turn message as text), its unit tests in
`tests/test_agent_helpers.py`, the two integration test files, BACKLOG.md, and
`docs/testing.md` where it describes the shared helpers.

## Out of scope

- Raising a timeout or retrying a test: the task forbids it (as LAD-281 decided), and neither
  failure was a short wait.
- The fake agent running commands that arrive mid-turn: it would change the fake's contract
  that `test_mid_turn_messages.py` and others rely on (a mid-turn message is text the turn sees,
  not a new input), for a behaviour no test needs.
- The product: LADO's mid-turn delivery and the reply reminder work as their specs say.
- Auditing all of `tests/integration/` (about 64 human commands in 20 files): too wide for a
  hotfix; most of them already wait for idle or for the agent's tool call. A BACKLOG.md entry
  names the shape so the next flake of it is found fast.
- BACKLOG.md's P1 entry "`make check` fails on timeouts…": these two failures were races, not
  load timeouts, so they are not added there.

## Acceptance

- AC-1: the approved-proposal test sends `start_session b <id>` only when the supervisor is
  settled; its other assertions are unchanged.
- AC-2: `to_the_gate` returns only when the worker is settled; both gate tests in
  `test_flow_runs.py` pass with their assertions unchanged.
- AC-3: unit tests of `settled`: false while the agent is busy, false while it is idle with a
  message pending or sent, true when idle and every message to it is delivered or read (a
  delivered message with an unread body counts as taken).
- AC-4: each race is reproduced once by forcing its window (e.g. a `pause` in the fake agent's
  turn, or a delay before the reminder is queued) on the test without the wait, and the build
  report says how; the forcing is not committed.
- AC-5: the two test files pass alone with `-n0` and in a parallel `-m integration -n auto` run
  of both files; `make test` and `make lint` pass.

## Impact

- Tests and docs only: no change under `src/`, no CHANGELOG.md line (users see nothing), no
  version bump of its own.
