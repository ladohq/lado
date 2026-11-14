Task: LAD-271

## Why

A CI cell `ui (<k>)` sometimes hangs in its pytest step until GitHub cancels the whole job
at its `timeout-minutes`: `ui (2)` of run 42890628200 (2026-11-10) and `ui (1)` of run
43005984528 (2026-11-11), each green on a rerun of the failed jobs. A job cancelled by its
time limit keeps neither the pytest step's log nor the junit report (the upload step does
not run), so nobody knows which test hung, and each hang costs the job's full 25 minutes
(30 at the time) and a rerun by hand.

The root cause of the blindness: only the job has a time limit. Neither a UI test nor the
pytest step has one, so a hang always ends in a cancelled job, never in a failed test.
For scale, the longest UI test of a green run on main (run 43620517182) takes 13 s, and a
shard's pytest step about 5 minutes.

The cause of the hang itself is not known and cannot be found without that log; this
change makes the next hang name its test and stack.

## Options

1. **pytest-timeout with a limit per UI test, and a limit on the pytest step** (chosen).
   A UI test (its fixtures included) that runs past 120 s fails, named in the log and the
   junit report; the shard's other tests run on and the report is uploaded. The method is
   pytest-timeout's `thread`, which ends the test's xdist worker (xdist names the test and
   starts a new worker): its `signal` raises into whatever runs, which in a wait of
   Playwright is Playwright's event loop, and the page's teardown then hangs with no limit
   (found in review). The stacks go to the log through Python's faulthandler, into the
   stderr pytest's own faulthandler keeps, 5 s before the limit: pytest-timeout's own dump
   goes to the worker's terminal, which xdist drops. A wait inside Playwright shows
   Playwright's event loop there, not the test's line (the test waits in another greenlet);
   a wait in plain Python shows the test's line. An ended worker runs no teardown, so the
   hung test's lado server and tmux server stay behind (a CI runner is thrown away). The
   step's own `timeout-minutes: 12` catches a hang outside a test (pytest itself, xdist),
   and a step timeout keeps the log. Long-term cost: one dev dependency, none in LADO's
   package, and a reach into pytest's private `fault_handler_stderr_fd_key`.
2. **Python's faulthandler only** (pytest's built-in `faulthandler_timeout`) with the
   step's limit: no dependency, but the hung test is never ended: the stack is printed,
   the shard waits out the step's 12 minutes, the rest of its tests never run, and no
   junit report is written.
3. **A watchdog of our own in the UI conftest** (a thread that dumps every stack and ends
   the worker): the same as option 1, written and kept by hand.

## What Changes

- `pyproject.toml` (dev group) and `uv.lock`: `pytest-timeout`.
- `tests/time_limit.py`: one constant, 120 s, the time limit of each UI test, its
  collection hook and the fixture that dumps the stacks; `tests/ui/conftest.py` imports
  them, so every test collected under `tests/ui/` has the limit, in `make test-ui` and in
  CI alike. The limit lives in that module, not in the conftest, so its tests run the same
  code with a short limit (the conftest brings in the browser tests' fixtures).
- `.github/workflows/ci.yml`, job `ui`: the pytest step gets `timeout-minutes: 12`, with a
  comment saying why (a step timeout keeps the log, and the junit upload still runs).
  The job's 25 minutes stay.
- `tests/test_ci_workflow.py`: the pytest step of `ui` has a limit shorter than its job's.
  A unit test of the UI limit and a UI test of a hang inside Playwright (see `tasks.md`).
- `docs/testing.md`: the UI layer and the CI paragraph name both limits.
- The living spec `continuous-integration`: a requirement that a hung UI test ends as a
  failed test that names itself.

## Acceptance criteria

- AC-1: Every test collected under `tests/ui/` carries a time limit of 120 s, set in one
  place (`tests/time_limit.py`, given by `tests/ui/conftest.py`); a unit test fails when a
  UI test is collected without it.
- AC-2: A test that runs past its limit under `-n 2` fails, its name appears in the report
  and the junit file, the stacks of its process's threads are in the log (with the test's
  line for a wait in plain Python), and the other tests of the run still run and pass;
  shown with a short limit by a unit test (a sleep) and by a UI test (a wait inside
  Playwright, with a real browser).
- AC-3: In ci.yml the job `ui`'s pytest step has `timeout-minutes: 12`, under the job's 25;
  the junit upload step keeps `if: always()`; a unit test fails when the step's limit is
  missing or not under the job's.
- AC-4: The pull request's four `ui (<k>)` cells are green, and no UI test of their junit
  reports comes near the limit (the longest is named in the build report).
- AC-5: `make test-ui` (and `uv run pytest -m ui`) applies the same limit locally; no other
  layer (unit, integration, smoke, live, container) gets a per-test limit.

## Scope

- `pyproject.toml`, `uv.lock`, `tests/time_limit.py`, `tests/ui/conftest.py`,
  `.github/workflows/ci.yml` (job `ui`), `tests/test_ci_workflow.py`, a unit test and a UI
  test of the limit, `docs/testing.md`, the living spec `continuous-integration`.

## Out of scope

- Finding and fixing the cause of the hang: it needs the stack this change brings. When a
  hang is caught, a new task is filed with the test and the stack; this pull request
  closes LAD-271 (the human's decision).
- A per-test limit for the integration jobs: no integration job was cancelled by its time limit
  in CI's runs of 2026-10-25 to 2026-11-14; they keep only their job limit.
- Changing the job `ui`'s 25 minutes: still the backstop for the steps before pytest.
- A CHANGELOG line and a version bump: nothing LADO's users see changes (CI and tests
  only).

## Impact

- Tests and CI only; no code of LADO, no schema, no MCP tool or CLI change: neither a minor
  nor a patch bump of its own, no CHANGELOG line.
- A UI test that hangs now fails in at most 2 minutes, and its shard goes on; a
  developer's local `make test-ui` gets the same limit.
