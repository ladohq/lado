Task: LAD-221

## Why

Symptom: `tests/integration/test_project_secrets.py::test_every_agent_of_a_session_gets_its_project_s_secrets`
failed once in CI with `timed out after 30s waiting for the brief written` at
`tests/agent_helpers.py:376` (PR #232, run 42279198936, attempt 1, `integration (3.13, 1)`).
That pull request did not touch the test, and the rerun of the failed jobs passed.

Cause: the test races the supervisor's turn; the product is right, and secrets play no part:
every assertion on them before that line had passed. The test tells the supervisor
`spawnrun`, waits until the run's worker exists and has reported its environment, and calls
`_approve_and_start` at once. `spawn_worker` is then still running in the supervisor's turn:
the worker's row and its `seen.json` appear before the tool returns. The message
`artifact_write brief brief.md` therefore goes into the supervisor's queue while it is busy,
and `spawn_worker`'s result takes it, as the spec `mid-turn-messages` says every `lado` tool's
result does. A real agent reads that line and acts on it. The fake agent only runs commands
it reads as input, so it prints the line and ends its turn, and nothing writes the brief. The
log of the failure shows exactly this: the message is `delivered`, the supervisor is idle, and
the result of `spawn_worker` ends with `Messages that came during your turn:` and the line.

A longer timeout cannot help: the message is used up, and the wait ends the same way however
long it is.

`_approve_and_start` has a second window of the same kind: the question's row exists before
`ask_human` returns, so the `start_session` line sent right after the answer can go into
`ask_human`'s result. CI has hit this one too:
`test_project_secrets_canary.py::test_a_project_secret_is_found_nowhere_else` failed at head
`ef82e9b9` (run 42063805570, `integration (3.10, 2)`) with `timed out after 30s waiting for
start_session's result`, and `ask_human`'s result ends with the `Answer to` line under
`Messages that came during your turn:`. The review report of 2026-11-05 recorded that as one
case, cause unknown; this is its cause, and the same fix closes it.

Reproduced 2026-11-06 in a throwaway copy, with `await asyncio.sleep(4)` after the tool's call
in `mcp_server`'s `call_tool`:

    spawn_worker slowed, no fix                  timed out ... waiting for the brief written
    spawn_worker and ask_human slowed,
      only the first wait added                  timed out ... waiting for start_session's result
    both slowed, both waits added                14 passed (the three test files below and
                                                 test_project_sessions.py)

The first line gives the same state as the CI log: the message delivered in `spawn_worker`'s
result, all three agents idle.

Options weighed:

- A (taken): `_approve_and_start` waits for the supervisor to be idle before each message that
  must start a turn: at its start, and before it answers the question. One helper serves all
  its callers: `test_project_secrets.py`, `test_project_variables.py` and
  `test_project_secrets_canary.py` have the same `spawnrun` step before it, and every caller
  has the second window. Long-term cost: none; `idle` is already in the file.
- B: `wait_idle` in each of the three tests. Fixes the first window only, and the next caller
  has to know the rule.
- C: the fake agent runs the commands that come in a tool's result. Nearer to a real agent,
  and it would remove this class of race, but it changes what every integration test drives:
  a command would run inside another one's turn, and `test_mid_turn_messages.py` and the tests
  that read `Messages that came during your turn:` from a fake's output would need review, for
  one flake.
- D: a longer `TIMEOUT` or a retry. Does not help (above).

## What Changes

- `_approve_and_start` in `tests/integration/test_project_sessions.py` waits for the
  supervisor to be idle at its start and again before `runtime.answer_question`. Its docstring
  says why: a message sent during the supervisor's turn comes in a tool's result, where the
  fake agent does not act on it.

## Scope

- That one helper. Its callers need no change.

## Out of scope

- `src/lado/`: the behaviour is right and spec'd (`mid-turn-messages`); no delay in the product
  and no effect on secrets (Why).
- The fake agent acting on messages in a tool's result: option C; a wider change than one
  flake is worth.
- The waits for idle the callers in `test_project_sessions.py` already have: harmless, and
  not this task.
- `TIMEOUT` in `tests/agent_helpers.py`: not the cause.

## Impact

- Tests only. No behaviour rule changes, so there is no delta; archive with `--skip-specs`.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the
  patch rule at most).
- Neutral core, one source of truth, no silent drops: untouched, as `src/` does not change.
