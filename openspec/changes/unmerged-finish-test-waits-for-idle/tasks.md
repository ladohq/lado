## 1. The test

- [x] 1.1 By hand, before the fix: in the test, after `worker = worker_commits()`, add
  `runtime.send_message(SESSION, "human", "w1", "sleep 3")` and `wait_status("w1", state.BUSY)`,
  and run it alone, `uv run pytest -m integration -n0
  "tests/integration/test_agents.py::test_unmerged_worker_is_finished_only_with_discard"`: it
  fails with `'busy' == 'idle'` (AC-2). Quote the failure in the build report.
- [x] 1.2 `tests/integration/test_agents.py`: replace
  `assert state.get_agent(SESSION, "w1").status == state.IDLE` by
  `wait_status("w1", state.IDLE)` (AC-1). With the probe of 1.1 the test passes; remove the
  probe.
- [x] 1.3 The test alone 20 times in a row (the command of 1.1) and `uv run pytest -m integration
  -n auto tests/integration/test_agents.py` 3 times in a row, each run's exit status read (not
  piped); all pass (AC-3). The build report gives the counts.

## 2. The backlog

- [x] 2.1 `BACKLOG.md`: the entry "Integration flake:
  `test_unmerged_worker_is_finished_only_with_discard` reads w1 busy" goes, nothing else (AC-4).

## 3. Checks

- [x] 3.1 `make lint` passes (AC-5).
- [x] 3.2 `openspec validate unmerged-finish-test-waits-for-idle --strict` passes.
