## 1. The test

- [ ] 1.1 By hand, before the fix: `make web` (the tree has no bundle yet), then in the test,
  before `page.goto`, hold back the response of the session's `GET …/agents` with `page.route`
  (a sleep of a few seconds, then `route.continue_()`) and run the test alone: it fails with
  `ValueError: not enough values to unpack (expected 2, got 0)` (AC-2). Do not commit the
  probe; quote the failure in the build report.
- [ ] 1.2 `tests/ui/test_status_marks.py`: before `supervisor, w1 = team.get_by_role("button").all()`
  add `expect(team.get_by_role("button")).to_have_count(2)`, with a comment that `.all()` does
  not wait (AC-1). With the probe of 1.1 the test passes; remove the probe.
- [ ] 1.3 The test alone 20 times in a row, `uv run pytest -m ui -n0
  tests/ui/test_status_marks.py`, and `uv run pytest -m ui -n auto
  tests/ui/test_status_marks.py` 5 times in a row, each run's exit status read (not piped);
  all pass (AC-3). The build report gives the counts.

## 2. The backlog

- [ ] 2.1 `BACKLOG.md`: the entry "UI e2e test of the status marks reads the Team buttons
  before they render" goes, nothing else (AC-4).

## 3. Checks

- [ ] 3.1 `make lint` passes (AC-5).
- [ ] 3.2 `openspec validate status-marks-test-waits-for-team --strict` passes.
