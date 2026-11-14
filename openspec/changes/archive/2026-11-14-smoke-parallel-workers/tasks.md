## 1. The smoke cell's command

- [x] 1.1 In `tests/test_smoke_ci.py`, a test that `smoke_ci.run(<provider>, out)` (install
  and `cell` replaced, as the live cell's tests do) hands `cell` exactly `["uv", "run",
  "pytest", "-m", "smoke", "-n", "3", "--dist", "worksteal", "-v", "-k", <provider>]`.
  Check: it fails on today's code (`-n0`).
- [x] 1.2 `scripts/smoke_ci.py`: `run` uses that command; its docstring says it (and that
  `make test-smoke` stays serial). Check: 1.1 passes; `make lint`; `make test`.
- [x] 1.3 `docs/testing.md`: the CI smoke cell's command and why it runs on three workers
  (each test isolated; the step mostly waits on CLIs); `make test-smoke` serial. Check: a
  grep of `docs/` and `openspec/specs/` for `pytest -m smoke` finds no stale `-n0` for the
  cell.

## 2. Trial in CI

- [x] 2.1 Push and open the pull request; then push two empty commits, one after the
  other's run ended, so three runs of the branch exist (no `gh run rerun` of a whole run). Check
  (AC-2): every smoke cell green each time, tests passed per cell 21 / 16 / 14 / 14, no skip.
- [x] 2.2 Record each macOS cell's test step duration of the three runs in the build
  report. Check (AC-3, as the human set it on 2026-11-14): per macOS cell, the median of
  the three at most 270 s and each under 396 s. If a run is red on a smoke test that
  passes serially, or AC-3 is not met, stop and bring the numbers to the human; the code
  is not changed on its own (`-n 2` is not tried: fewer workers cannot shorten the step).
- [x] 2.3 `openspec validate smoke-parallel-workers --strict` passes.
