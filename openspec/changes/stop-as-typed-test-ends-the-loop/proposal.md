Task: LAD-236

## Why

Symptom: `tests/integration/test_human_messages.py::test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty`
fails now and then in CI with `Failed: DID NOT RAISE LadoError` in `refused_by_the_stop`
(line 165): run 42414787255 (integration (3.10, 3), PR #251), and on `main` on 2026-11-09 runs
42605436802 and 42614836191 (integration (3.13, 3), `-n0`). A rerun of the failed job passes.

Cause: a race in the test between two processes, not a defect of LADO. The test makes the
session stop "between the hand-over and the typing" by patching `tmux.send_text` in its own
process (`stop_as_it_types`). But the test process is not the only one that hands messages
over: the session loop (`lado loop`, a process of its own, started by `runtime.start_session`)
runs `runtime.sweep` every `LADO_LOOP_INTERVAL` (0.25 s in the integration layer), and its
`hand_over` types the queue of an idle agent with the real, unpatched `tmux.send_text`.
`runtime.post` queues the human's message in one transaction and `runtime._deliver` takes it
(`_sweep_sent`, then `hand_over` -> `state.take_pending`) in later ones. When a loop pass falls
into that gap, the loop takes the message, types it into the live window and makes the
supervisor busy; the test's own `take_pending` then finds nothing, so the patched `send_text`
never runs, no stop comes, and `_deliver` sees the message `sent` and returns "sent". No error,
so `pytest.raises` fails. The gap is a few milliseconds of a 250 ms period, so the test fails
on a small share of runs, more often on a loaded runner.

Shown by hand on 958dede7: with the test process's `runtime._sweep_sent` slowed by 0.6 s (longer
than one loop pass), the test fails every time with the same `Failed: DID NOT RAISE LadoError`
at line 165. The sibling test
`test_a_stop_as_the_message_is_typed_refuses_it_and_spares_a_session_of_a_longer_name` goes
through the same `refused_by_the_stop` and has the same race, though no failure of it is known.

The product is right: in a running session the loop delivering a message the writer queued is
how delivery is meant to work, and the human's message reaches the agent either way. Only the
test's premise, "this process does the typing", is wrong while the loop runs.

Options weighed:

- A (taken): the test ends the session's loop before it writes, so the only process that can
  hand the message over is the test's own. A helper in `tests/agent_helpers.py` ends the loop
  process (its pid from the session's `loop started, pid N` line in `loop.log`) and waits until
  `loop.running` is false; the resume in `refused_by_the_stop` starts a new loop, as it starts
  one for every session. Nothing is queued while the loop is ended, so ending it cannot cut a
  hand-over in half. Long-term cost: one small helper, and the test states its premise in code.
- B: queue and hand over in one transaction in the product (`post`/`_deliver`), so no other
  process can take a message between them. It closes this gap for the test, but changes the
  core message path that every provider uses, for a race that does no harm to users; and the
  loop could still take the message before the test's patched typing in other ways. Long-term
  cost: a riskier change of `runtime.py` with no user gain.
- C: a switch that keeps the loop from sweeping (an environment variable read by `lado loop`).
  It would work, but adds an option only tests use (AGENTS.md, "Only what is used") and a way
  to run a session with no sweep. Long-term cost: a knob to keep and document.

A retry or a weaker assertion (accepting "sent" as well) is ruled out by the task.

## What Changes

- `tests/agent_helpers.py`: a helper that ends a session's loop and waits for it to be gone.
- `tests/integration/test_human_messages.py`: `refused_by_the_stop` (both tests that use it)
  ends the session's loop before `runtime.write_as_human`, with a line saying why; the
  assertions stay as they are.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md
  line, and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/agent_helpers.py`, `tests/integration/test_human_messages.py`. Nothing in `src/` or
  `web/`.

## Out of scope

- The product's message path (option B): the race does no harm to users, and the human's
  message is delivered whoever types it.
- A test-only switch of the loop (option C): an option no kit or user needs.
- Other integration tests that patch a function of the test process while the loop runs: none
  patches `tmux.send_text` or another part of the hand-over (grep of `tests/integration/`);
  none has such a failure (AGENTS.md, "Only what is used").
- A rerun plugin, a longer timeout or accepting "sent": they hide the race rather than close it.

## Acceptance criteria

- AC-1: `refused_by_the_stop` ends the session's loop before it writes, by a helper of
  `tests/agent_helpers.py` that fails the test when the loop is not gone in time; the
  assertions of `refused_by_the_stop` and of both tests are unchanged.
- AC-2: The race is shown by hand before and after the fix with the probe of task 1.1 (the test
  process's `runtime._sweep_sent` slowed by 0.6 s): before, the test fails with
  `DID NOT RAISE LadoError`; after, both tests pass. The build report quotes both; the probe is
  not committed.
- AC-3: With the fix, each of the two tests passes 20 times in a row alone (`-n0`) and the whole
  file 3 times in a row under `-n auto`, each with `-m integration`; no loop is left after them
  (the layer's `no_loop_left`).
- AC-4: `make lint` passes and CI is green.

## Impact

- `tests/agent_helpers.py` and `tests/integration/test_human_messages.py` only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale hotfix: a defect of a test with a clear symptom and a cause shown by hand; review by
  precision.
- The fix is in the test (option A): the product behaves as designed, and the test's premise is
  what is wrong.
- The loop's pid is read from `loop.log` (the line `loop started, pid N` that `lado loop` writes
  at its start): it works on Linux and macOS alike, where finding a lock's holder does not.
- The loop is ended before the write, never paused with SIGSTOP: a loop stopped in mid-pass
  could hold a SQLite write lock; ended while nothing is queued, it cuts no hand-over in half.
- Test layer: integration (`-m integration`), the tests themselves: the race needs a real
  session loop process and real tmux; no new test.
