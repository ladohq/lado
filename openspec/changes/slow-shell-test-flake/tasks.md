## 1. The test

- [x] 1.1 By hand, before the fix: put `sleep 1;` before `echo stuck >&2` in the rc of
  `test_a_slow_shell_times_out` and run it alone (`uv run pytest -n0
  tests/test_agent_env.py -k slow_shell`): it fails on `assert "stuck" in ...` (AC-2).
  Do not commit the probe; quote the failure in the build report.
- [x] 1.2 `tests/test_agent_env.py`, `test_a_slow_shell_times_out`: the rc lines become
  `echo stuck >&2; : > <marker>; sleep 30 & wait` (the marker in `tmp_path`); the test
  wraps `agent_env._read_until` with `monkeypatch.setattr`: the wrapper waits for the
  marker (polling, at most 30 s, else `pytest.fail` naming it), then returns the
  original's result for the same `fd`, `end` and `deadline`. `TIMEOUT` stays 0.5 and both
  assertions stay. A comment says why: the deadline runs from the shell's start, and under
  load the shell may not print its line within 0.5 s (AC-1).
- [x] 1.3 The probe of 1.1 again with the fix: it passes; then without the probe, the test
  alone 20 times in a row (`uv run pytest -n0 tests/test_agent_env.py -k slow_shell`,
  each run's exit status read, not piped) (AC-2, AC-3).
- [x] 1.4 `make lint` and `make test` pass; the build report gives the counts (AC-3,
  AC-4).
