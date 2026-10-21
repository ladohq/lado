## Context

`tests/leftovers.py` finds a test's processes by a mark in their environment:
`LADO_HOME` per test (swept by the `isolated` fixtures of the integration, UI, smoke and
live tests) and `LADO_TEST_PID` per pytest process (checked at the run's end). Unit tests
have no `isolated` fixture, so a unit test's leftover is found only at the run's end, by
pid and command, with no word of the test. The one leftover today is the fake git's
`sleep 60` child in the mode `ok` (proposal, Why).

Options weighed for naming the test:

1. **A per-test mark in the environment** (chosen): `LADO_TEST_ID` set around each test,
   read back from the leftover's environment at the run's end. Cost: one environment
   variable set and removed per test; nothing scanned per test. Long-term: one more mark
   beside `LADO_TEST_PID`, read by the same reader.
2. **A leftover check after every unit test**, failing that test: the strongest signal,
   but a scan of all processes per test and a wait for processes still ending (the
   sweep's 10 s budget, or a shorter one that turns slow endings into false reds). Slows
   the unit run and adds a flake source for a defect the run's end already catches.
3. **Only the fake git fix**: the symptom goes, but the next leak again costs a bisection
   by hand; the task asks for the name.

Against AGENTS.md: the change stays in `tests/` (neutral core and providers untouched),
derives the name from the process itself (one source of truth: the environment it was
started with), and drops nothing silently (a process without the mark is still named and
still fails the run).

## Decisions

- **D1. The fake git kills its child and waits for it before `sys.exit(0)` in the mode
  `ok`.** `child.kill()` then `child.wait()`, so no zombie or orphan remains when
  `clone.clone` returns; the other modes keep their child for the cancel tests' check.
- **D2. `LADO_TEST_ID` is set by a `pytest_runtest_protocol` hook wrapper in
  `tests/conftest.py`** to `item.nodeid` before the wrapped protocol and removed after it
  (`os.environ.pop`), so setup, call and teardown, and the fixtures they start, carry it.
  A session- or module-scoped fixture started during a test's setup carries that test's
  id: "started in" is when it started, which is what finding it needs.
- **D3. The report line is `<pid> <command>, started in <node id>`**, in
  `leftovers.describe`, via `Process.get("LADO_TEST_ID")`; without the mark the line is as
  today. The `isolated` fixtures' `fail_if` uses the same `describe`, so their lines name
  the test too (it is the failing test itself there; harmless).
- **D4. The name is `LADO_TEST_ID`**, beside `LADO_TEST_PID`, and like it a mark of the
  test suite only: LADO neither sets nor reads it. `tests/conftest.py` already clears
  LADO's variables at import; this one is set after that.
- **D5. Test layers.** The fake git fix: unit (`tests/test_clone.py`, the child is gone).
  `describe` with and without the mark: unit (`tests/test_leftovers.py`, canned
  `Process`). The mark reaching a child and the run's report naming the test under xdist:
  integration (`tests/integration/test_leftover_processes.py`, a scratch pytest run in a
  temp folder with a test that leaves a `sleep 60`), as it crosses processes.
