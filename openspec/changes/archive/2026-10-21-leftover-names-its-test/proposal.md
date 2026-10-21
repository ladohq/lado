Task: LAD-121

## Why

`make test` goes red with every test passed: `3614 passed, 1 skipped`, exit 2, under
"processes left by the test run, killed" with one `sleep 60`. A red run with no failing
test hides a real red, and each developer spends a question to the supervisor on it
(BACKLOG.md, P2 "`make test` leaves a `sleep 60` behind and goes red with every test
passed").

Root cause (main, 18cd77d), reproduced: `uv run pytest -n0
tests/test_clone.py -k target_filled_during` passes and the run fails naming one
`sleep 60`; the whole unit suite with that test deselected exits 0 with nothing left.
The fake git of `tests/agent_helpers.py` (`FAKE_GIT`) starts a `sleep 60` child for a
clone or an ls-remote, so the tests of a cancelled clone can check that the clone's
process group dies. In the mode `ok` the clone exits 0 and leaves that child alive:
nothing kills it, as a clone that succeeds is not cancelled. Of the three tests that use
`ok`, only `test_a_target_filled_during_the_clone` (`tests/test_clone.py`) reaches git;
the other two are refused before it. `tests/test_tmux.py`, suspected in the backlog
entry, leaves nothing: its `sleep 60` panes end with their tmux session.

Finding the test took a bisection by hand: the run's check names a leftover by pid and
command only, and every test that uses the fake git starts the same `sleep 60`.

## What Changes

- **The fake git ends its child before it exits 0** (mode `ok`): it kills the `sleep 60`
  and waits for it, so a clone that succeeds leaves nothing. The modes `slow`,
  `slow-clone` and `fail` are as before.
- **`test_a_target_filled_during_the_clone` checks it**: the fake git's logged child is
  gone after the clone, as the cancel tests already check for theirs.
- **The run's leftover check names the test that started each process**: every pytest
  process sets `LADO_TEST_ID` to the node id of the test it runs (setup, call and
  teardown), which every process started meanwhile inherits; a leftover is listed as
  `<pid> <command>, started in <node id>`. A process started outside a test (no such
  mark) is listed as before.
- `docs/testing.md`: the new mark and what the check prints.
- BACKLOG.md: the entry "`make test` leaves a `sleep 60` behind and goes red with every
  test passed" is removed, as this change does what it wants.

## Scope

The test suite only: `tests/agent_helpers.py`, `tests/conftest.py`, `tests/leftovers.py`,
their tests, `docs/testing.md`, BACKLOG.md. No change to LADO itself (`src/`), the CLI,
the UI, the API or the schema. A patch at most (tests and docs only); no CHANGELOG.md
line, as users see nothing.

## Out of scope

- A leftover check after each test that fails the very test: a scan of every process per
  test (about 3600 of them) and a wait for processes that are still ending would slow the
  unit run for a defect the run's end already catches; the mark names the test at no
  cost.
- Starting no child in the mode `ok`: a clone cancelled during its progress in that mode
  would no longer check that the process group dies; ending the child keeps the mode a
  clone that succeeds.
- `tests/test_tmux.py`: it leaves nothing (checked with the run above).
- The `isolated` fixtures' sweep by `LADO_HOME`: it already fails the test that left the
  process, by name.

## Impact

- `tests/agent_helpers.py` (`FAKE_GIT`), `tests/test_clone.py`, `tests/conftest.py`,
  `tests/leftovers.py`, `tests/test_leftovers.py`,
  `tests/integration/test_leftover_processes.py`.
- `docs/testing.md`, BACKLOG.md.
- Modified capability spec `test-processes`.
