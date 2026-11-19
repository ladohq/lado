## 1. The test

- [x] 1.1 By hand, before the fix: change the window's command in
  `test_send_text_pastes_multiline_text` to `["sh", "-c", f"sleep 1; cat > {out}"]` and run
  `uv run pytest -n0 "tests/test_tmux.py::test_send_text_pastes_multiline_text"`: it fails with
  `FileNotFoundError` (AC-2). Quote the failure in the build report.
- [x] 1.2 `tests/test_tmux.py`: add `out.touch()` before `tmux.new_session(...)` in
  `test_send_text_pastes_multiline_text` (AC-1). With the probe of 1.1 the test passes; quote
  it, then remove the probe.
- [x] 1.3 The test alone 50 times in a row (the command of 1.1, in a shell loop that stops on
  the first failure) and `uv run pytest -n auto tests/test_tmux.py` 3 times in a row, each run's
  exit status read (not piped); all pass (AC-3). The build report gives the counts.

## 2. Checks

- [x] 2.1 `make lint` passes (AC-4).
- [x] 2.2 `openspec validate multiline-paste-test-waits-for-file --strict` passes.
