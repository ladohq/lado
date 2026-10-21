## 1. The leak

- [ ] 1.1 `tests/agent_helpers.py` (`FAKE_GIT`): in the mode `ok`, kill the child and
  wait for it before `sys.exit(0)` (D1); update the comment above `FAKE_GIT`.
- [ ] 1.2 `tests/test_clone.py::test_a_target_filled_during_the_clone`: read the fake
  git's call and assert `gone(call["child"])` after the clone. Check: `uv run pytest -n0
  -p no:cacheprovider tests/test_clone.py -k target_filled_during` exits 0 with no
  "processes left by the test run"; with 1.1 reverted, it fails naming the test.

## 2. The test's name

- [ ] 2.1 `tests/conftest.py`: a `pytest_runtest_protocol` hook wrapper sets
  `LADO_TEST_ID` to the item's node id and removes it after (D2, D4); comment beside
  `LADO_TEST_PID`'s.
- [ ] 2.2 `tests/leftovers.py`: `describe` adds `, started in <node id>` when the process
  carries `LADO_TEST_ID` (D3); the module docstring names the mark.
- [ ] 2.3 `tests/test_leftovers.py` (unit): `describe` of a process with the mark and of
  one without it. Check: `uv run pytest -n0 tests/test_leftovers.py`.
- [ ] 2.4 `tests/integration/test_leftover_processes.py` (marker `integration`): a
  scratch pytest run with two workers in a temp folder (as
  `test_a_run_with_workers_does_not_take_them_for_its_leftovers`) whose test starts a
  `sleep 60` and leaves it: the run exits 1, its output names the process and the
  test's node id, and the process is gone after. Check: `uv run pytest -m integration
  -n auto tests/integration/test_leftover_processes.py`.

## 3. Docs and backlog

- [ ] 3.1 `docs/testing.md`: `LADO_TEST_ID` and the "started in" of the run's report, in
  the paragraph of `LADO_TEST_PID`.
- [ ] 3.2 BACKLOG.md: remove the entry "`make test` leaves a `sleep 60` behind and goes
  red with every test passed".

## 4. Regression

- [ ] 4.1 `make lint`; `make test` exits 0 three times in a row with no "processes left
  by the test run" (numbers of each run in the build report).
- [ ] 4.2 `openspec validate leftover-names-its-test --strict`.
