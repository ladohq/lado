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

- [ ] 2.1 Push and open the pull request; then push two empty commits, one after the
  other's run ended, so three runs of the branch exist (no `gh run rerun` of a whole run). Check
  (AC-2): every smoke cell green each time, tests passed per cell 21 / 16 / 14 / 14, no skip.
- [ ] 2.2 Record each macOS cell's test step duration of the three runs in the build
  report. Check (AC-3): each at most 210 s. If a run is red on a smoke test that passes
  serially, or a step exceeds 210 s, try `-n 2` once (1.1-1.3 changed alike); if that
  fails too, stop and report `redesign` with the numbers.
- [ ] 2.3 `openspec validate smoke-parallel-workers --strict` passes.
