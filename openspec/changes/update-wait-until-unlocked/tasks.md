## 1. Reproduce

- [x] 1.1 Inject a delay (e.g. `time.sleep(3)`) in `self_update.run` after `done.run()`
  returns and before the lock is released; run
  `uv run pytest -m integration -n0 -k rolls_back tests/integration/test_update_process.py`
  and see it fail on `info["running"]`. Not committed; quote the failure in the build
  report (AC-3).

## 2. The fix

- [x] 2.1 `web/src/SystemPanel.tsx`: `finished()` returns false while `update.running`
  is true; its comment says so. vitest in `web/src/SystemPanel.test.tsx`: the three
  scenarios of spec `ui-update-wait` (result written, lock held → false; lock released
  → true; not started with `running` false → true, with `running` true → false)
  (AC-1). `make web` passes.
- [x] 2.2 `tests/integration/test_update_process.py`: `update_from_the_ui`'s `back()`
  also waits for `info[1]["running"]` false; its docstring says so. With the delay of 1.1
  still in place the test passes; then remove the delay (AC-2, AC-3).
- [x] 2.3 `docs/design/ui.md`, The wait (U2): the end condition names `running` false.
  CHANGELOG.md, under `0.39.0 (unreleased)`: after an update from the UI, the System
  panel no longer says an update is running and keeps its Update… button.

## 3. Acceptance

- [ ] 3.1 20 runs in a row of `test_the_ui_update_rolls_back_when_the_new_version_is_wrong`
  (`-m integration -n0`, a loop) and of `SystemPanel.test.tsx`, counted in the build
  report (AC-4).
- [ ] 3.2 `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_update_process.py`, `make web` pass; `ci-ok` green on the pull
  request (AC-5).
