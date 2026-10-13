## 1. CI

- [x] 1.1 `tests/test_ci_workflow.py`: a test that collects, in order, the `run` lines of
  jobs `check` and `ui` that start with `uv run pytest` and asserts they are
  `["uv run pytest -n auto", "uv run pytest -m integration -n0"]` and
  `["uv run pytest -m ui -n 2"]`; it fails on main's workflow before 1.2 (AC-2).
- [x] 1.2 `.github/workflows/ci.yml`: job `check`'s integration step `uv run pytest -m
  integration -n0`, job `ui`'s step `uv run pytest -m ui -n 2`; nothing else changes. A
  comment above each step says why (4-vCPU runners, LADO's short test timers). 1.1's test
  passes (AC-1, AC-2).
- [x] 1.3 AGENTS.md, Commands, the paragraph "CI runs …": the unit tests in parallel, the
  integration tests in one process (`-n0`) and the UI tests on two workers (`-n 2`), and
  why (AC-3).
- [x] 1.4 `make lint` and `uv run pytest -n auto tests/test_ci_workflow.py` pass, each
  exit status read, not piped (AC-6).

## 2. Verification on CI

- [x] 2.1 Push the branch and open the pull request; run 1 is the push's. After each green
  run, `gh run rerun <id>` (the whole run, never `--failed`) for runs 2 and 3, each started
  only once the previous one is green. A red run: stop, name its failing test in the build
  report and tell the supervisor; do not rerun it to green (AC-4).
  Done under the human's rule (question #4467), which replaced this one after a red run of
  a unit test outside this change: a run counts when the integration steps (both Pythons)
  and the `ui` job's pytest step are green; a failed unit, vitest or smoke job is rerun
  with `--failed` so those steps run, and each such flake is in the build report. Run
  38399466423, attempts 1, 2 and 3+4 (attempt 4 reran `ui` after a vitest flake in `make
  dist`).
- [x] 2.2 The build report has a table of the times of jobs `check (3.10)`, `check (3.13)`
  and `ui` for each of the three runs (`gh run view <id> --attempt <n> --json jobs`), with
  main's run 38385575828 beside them, and says the `check` jobs stay within 40 minutes
  (AC-5).
