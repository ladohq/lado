Task: LAD-41

## Why

Symptom: on 2026-10-13 CI failed five different ways on timing, mostly on Python 3.10, and
each failing test passes alone:

- `tests/integration/test_agents.py::test_messages_in_the_turn_end_output_are_delivered_once_confirmed`
  (`[fake]`, `[fake-stop]`): the batch ends `typed` instead of `hook_output`;
- `tests/integration/test_agent_liveness.py::test_stopping_a_session_tells_no_one_and_counts_what_it_dropped`:
  its 30 s wait times out;
- `tests/integration/test_terminal_socket.py::test_control_takes_input_and_resize`: input
  is lost;
- `tests/ui/test_gates.py::test_the_humans_answer_is_the_runs_move_at_the_bottom_with_its_comment`:
  the element is not in the viewport;
- `web/src/Launch.test.tsx:216` (vitest, inside `make dist`).

Cause: CI runs every pytest layer with `-n auto`, which on GitHub's public
`ubuntu-latest` (4 vCPU) is 4 workers. An integration test runs its own tmux server, fake
agents, hooks, `lado mcp` and session loop with LADO's timers cut short
(`LADO_LOOP_INTERVAL=0.25`, `LADO_RETRY_DELAYS=2,0.5,0.5`, 30 s waits): four of them at
once on four cores starve each other's processes past those timers. A UI test adds a
Chromium and a `lado server` to that. The unit tests run in process and do not race.

The flakes block 0.37.0rc2: main is frozen for 0.37.0, and the final must be the code of
its last RC (docs/release.md), so the fix lands on main before rc2.

## What Changes

- `.github/workflows/ci.yml`, job `check`: `uv run pytest -m integration -n0` (one
  process) in place of `-n auto`; the unit tests stay `uv run pytest -n auto`.
- `.github/workflows/ci.yml`, job `ui`: `uv run pytest -m ui -n 2` in place of
  `-n auto`.
- `tests/test_ci_workflow.py`: a test that pins the three pytest commands of jobs `check`
  and `ui`, so a later edit does not bring `-n auto` back unnoticed.
- AGENTS.md, Commands: the CI paragraph says how many workers each layer gets in CI and
  why.

## Scope

CI's worker counts for the integration and UI tests, the test that pins them, and the
AGENTS.md line about CI.

## Out of scope

- Fixing the flaky tests themselves (their waits, timers, the viewport): this change only
  makes them rarer; their stabilisation is a later task of its own.
- `web/src/Launch.test.tsx:216`: vitest inside `make dist`, which no pytest worker count
  touches; it stays a known flake for that later task.
- The Makefile's `PYTEST_ARGS ?= -n auto` (`make test`, `make test-integration`, `make
  test-ui`, `make check`): a developer's machine has more cores and the check lock keeps
  one heavy run per machine; the task asks for CI only.
- Larger runners, or a matrix that splits the integration tests into parallel jobs: a
  paid runner, or a second list of test files that drifts from the folder (AGENTS.md,
  "One source of truth"); serial is enough within CI's 40-minute ceiling.
- A rerun plugin (pytest-rerunfailures) or longer timers under CI: they hide timing
  races rather than remove the load that causes them.
- A `workflow_dispatch` trigger or empty commits for the verification runs (see Decisions).

## Acceptance criteria

- AC-1: In `.github/workflows/ci.yml` job `check` runs `uv run pytest -n auto` and
  `uv run pytest -m integration -n0`, and job `ui` runs `uv run pytest -m ui -n 2`;
  nothing else in the workflow changes.
- AC-2: `tests/test_ci_workflow.py` has a test that fails when any of those three commands
  differs, and it passes.
- AC-3: AGENTS.md's CI paragraph names the unit tests in parallel, the integration tests
  in one process and the UI tests on two workers, with the reason (4-vCPU runners, LADO's
  short timers).
- AC-4: Three CI runs in a row of the pull request's head are green with no failed job
  rerun: the first from the push, the next two by `gh run rerun <id>` of the whole run,
  each started after the previous one is green. A red run is not rerun to green: the build
  report names its failing test and the developer tells the supervisor.
- AC-5: The build report gives the times of jobs `check (3.10)`, `check (3.13)` and `ui`
  of each of the three runs, and of main's run 38385575828 (`-n auto`) beside them; the
  `check` jobs stay within CI's 40-minute ceiling.
- AC-6: `make lint` and `uv run pytest -n auto tests/test_ci_workflow.py` pass.

## Impact

- `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, AGENTS.md.
- No code in `src/` or `web/`; no API, schema, MCP, CLI or UI change; no CHANGELOG.md line
  (nothing users see) and no version bump: a fix for the release candidate 0.37.0rc1.
- CI takes longer: the integration step from about 2¼ minutes to an expected 8-9, job
  `check` to about 12 minutes; job `ui` about a minute more.

## Decisions for the record

- Scale tweak: a CI change of known shape, given by the task; review by precision.
- Root cause is CPU load on 4-vCPU runners against LADO's shortened test timers; the
  fix removes the load in CI, not the timers (see Out of scope).
- `-n0`, not `-n 1`: one process with no xdist worker, as `make test-live` and the smoke
  runs do; `-n 1` would still start a worker process for nothing.
- `-n 2` for the UI tests, as the task says: a Chromium and a server per worker on four
  cores leave room for both; serial UI would add several minutes for little.
- The unit tests keep `-n auto`: in-process, no timers that race.
- The pinning test reads the workflow's YAML as `tests/test_ci_workflow.py` already does
  for the job `smoke`, and compares the `run` lines of jobs `check` and `ui` that start
  with `uv run pytest` as a list, so an added or reordered pytest step fails it too.
- Verification by `gh run rerun` of the whole run (the human's choice of how to count
  "three in a row without reruns"): no trigger added for it and no empty commits in
  main's history.
- Test layer: unit (`tests/test_ci_workflow.py`) for the commands; CI itself for the
  effect.
- No delta spec: no behaviour rule of LADO changes; the change is archived with
  `--skip-specs`.
