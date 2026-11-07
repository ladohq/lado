Task: LAD-233

## Why

Symptom: `tests/integration/test_agents.py::test_unmerged_worker_is_finished_only_with_discard`
failed in CI on e7c8773 (run 37887140737, Python 3.13, `-n auto`, the 0.31.0 release) with
`assert state.get_agent(SESSION, "w1").status == state.IDLE` -> `'busy' == 'idle'`; a rerun of
the failed jobs passed. The check is now line 745 and still reads the status once.

Cause: a race in the test, not a defect of LADO. The test reads w1's status once, and nothing
it waited for says that w1 is out of a turn at that moment. A refused finish does not touch w1,
so its turn runs on its own time. Two ways led to that, one closed and one open:

- Closed since the failure: on e7c8773 `worker_commits` waited for w1's first idle, which comes
  from its session start, before its task is handed over. w1's turn on the task then ran while
  the test went on. d64bff5c (2026-10-10, a day after the failure, for the sibling test
  `test_supervisor_finishes_a_merged_worker`) made it wait until nothing is unreceived and w1 is
  idle, and left this BACKLOG.md entry as it was.
- Still open: a task typed again. When w1's prompt-submit hook takes longer than the layer's
  first retry step (2 s) on a loaded machine, the sweep types the task a second time; the first
  copy is read and w1 goes idle, `worker_commits` returns, and the second copy starts another
  turn (BACKLOG.md, "A message typed again before its hook confirms it runs twice").

So the failure is rarer than it was, and the read-once stays wrong: the test states "w1 is idle"
as a fact of one instant, where the rest of the file waits for it.

The product is not at fault: an agent that is busy for a moment after a refused finish is
nothing LADO promises otherwise.

Options weighed:

- A (taken): replace the assertion by `wait_status("w1", state.IDLE)`, the file's helper. One
  line, the same statement, with the file's way of saying it; a worker the refused finish had
  ended still fails the test, as `status` then has no agent to read. Long-term cost: none beyond
  the line.
- B: drop the check, as `windows()` on the line before already says w1 lives. No wait, but the
  test no longer says that w1 is still a working agent after the refusal. Long-term cost: a
  weaker test.
- C: close the retyping itself, so a second turn cannot come. That is the product question of
  the BACKLOG.md entry named above (size M, "typed twice beats never"), and this test needs
  none of it. Long-term cost: a design of its own for one test's line.

## What Changes

- `tests/integration/test_agents.py`: `test_unmerged_worker_is_finished_only_with_discard` waits
  for w1 to be idle instead of reading its status once.
- `BACKLOG.md`: the entry "Integration flake: `test_unmerged_worker_is_finished_only_with_discard`
  reads w1 busy" goes, as this change closes it.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md
  line, and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/integration/test_agents.py`, `BACKLOG.md`. Nothing in `src/` or `web/`.

## Out of scope

- `worker_commits`: it cannot know that a second copy of the task is coming, so no stronger wait
  there would close the open way; the wait at the check does.
- BACKLOG.md's "A message typed again before its hook confirms it runs twice": a product
  question of its own, and it stays open.
- BACKLOG.md's "Integration tests take a new worker's first idle as its task done": other tests,
  none of which has failed; the task does not name them.
- Other status reads in other test files: `tests/integration/test_agents.py` has no other
  unwaited one, and the rest have no known failure (AGENTS.md, "Only what is used").
- A rerun plugin or a longer timeout: they hide the race rather than close it.

## Acceptance criteria

- AC-1: `test_unmerged_worker_is_finished_only_with_discard` has `wait_status("w1", state.IDLE)`
  in place of the assertion on w1's status; the rest of the test is unchanged.
- AC-2: The race is shown by hand once: with w1 kept in a turn over the refused finish (the probe
  of task 1.1), the old line fails with `'busy' == 'idle'` and the new one passes. The build
  report quotes both; the probe is not committed.
- AC-3: With the fix, the test passes 20 times in a row alone and the whole file 3 times in a row
  under `-n auto`, each with `-m integration`.
- AC-4: BACKLOG.md no longer holds the entry; the entries around it stay.
- AC-5: `make lint` passes and CI is green.

## Impact

- `tests/integration/test_agents.py` and `BACKLOG.md` only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale tweak: a test-only change of known shape, the fix named by the task; review by precision.
- The task stays wanted though d64bff5c closed the way that failed: the line still reads once,
  and the retyped task keeps the race open.
- Test layer: integration (`-m integration`), the test itself: real tmux and hooks make the race;
  no new test.
- A probe by a message to w1 rather than by slowing a hook: it holds w1 in a turn for sure and
  touches no product code.
