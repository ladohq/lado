## 1. The limit of a UI test

- [x] 1.1 `pyproject.toml`, dev group: add `pytest-timeout` (the version `uv add --dev`
  picks, as a `>=` floor like the other entries); `uv lock`. Check: `uv sync --locked`.
- [x] 1.2 `tests/time_limit.py`: a constant `TEST_TIMEOUT = 120` (seconds) with a comment
  (LAD-271: a hang fails the test instead of the CI job's cancel; the longest UI test
  takes ~13 s in CI), a collection hook `pytest_itemcollected` that gives each item
  `pytest.mark.timeout(TEST_TIMEOUT, method="thread")`, and an autouse fixture that has
  Python's faulthandler write every thread's stack `STACKS_BEFORE = 5` s before the limit
  into the stderr pytest's faulthandler keeps. `tests/ui/conftest.py` imports the hook and
  the fixture (scoped to its folder), not `pyproject.toml`'s `addopts`, so no other layer
  gets them. Revised after review (F1): `signal` raised into Playwright's event loop and
  the page's teardown then hung; pytest-timeout's own stack dump is lost under xdist.
  Check: `uv run pytest -m ui -n 2 tests/ui/test_tabs.py` green.
- [x] 1.3 A unit test, `tests/test_ui_time_limit.py` (`pytest_plugins = "pytester"`, as
  `tests/test_shard.py`):
  - `test_every_ui_test_has_the_limit_and_no_other_layers_test`: collects every layer's
    tests in a subprocess (no marker deselects any) and asserts every item under
    `tests/ui/` has `TEST_TIMEOUT` and no other item has a limit (AC-1, AC-5);
  - `test_a_test_past_its_limit_fails_with_its_stack_and_the_run_goes_on`: a pytester
    suite run with `runpytest_subprocess` (pytest-playwright refuses a run inside a test),
    `-p xdist -n 2` (xdist's default scheduling: `--dist loadfile` runs a crashed test
    again on each new worker), `tests/time_limit.py`'s own hook and fixture with a limit of
    2 s, a test that sleeps 60 s and five that pass: the sleeper fails, named as its
    crashed worker's in the report and as an error in `--junitxml`, the stacks in stderr
    hold its `sleep` line, the others pass, the run ends in well under 60 s (AC-2).
  Check: `make test`; the first test fails with the hook removed (try it, then restore).
- [x] 1.4 `tests/ui/test_time_limit.py` (marker `ui`, the browser): the same run with a
  test that waits forever inside Playwright (`page.wait_for_selector("#never",
  timeout=0)`): it fails and the run goes on, the stacks show Playwright's loop (AC-2).
  Check: red with `signal` (the run hangs), green with `thread`.

## 2. CI

- [x] 2.1 `.github/workflows/ci.yml`, job `ui`: the pytest step gets `timeout-minutes: 12`
  (its p90 is ~5 min) and a comment: a step past its limit ends red with its log kept and
  the junit upload still runs, which a job cancelled by its own limit loses; each test has
  its own 120 s (`tests/time_limit.py`). The job keeps `timeout-minutes: 25`; the upload
  keeps `if: always()`. Check: `make test`.
- [x] 2.2 `tests/test_ci_workflow.py`: a test that the `ui` job's pytest step has a
  `timeout-minutes` and it is under the job's (12 < 25), and that the junit upload is
  `if: always()` (AC-3); the module docstring names it. Check: `make test`; the test fails
  with the step's limit removed (try it, then restore).

## 3. Docs

- [x] 3.1 `docs/testing.md`: in the UI e2e layer, each UI test has 120 s, fixtures
  included (`tests/time_limit.py`, pytest-timeout), and a test past it fails, named, with
  its process's stacks in the log; in the CI paragraph, the `ui` pytest step's 12 minutes under the job's 25 and why
  (a cancelled job keeps no log or junit). Check: read against `ci.yml` and the conftest.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `uv run pytest -m ui -n 2 <changed ui files>` (none
  but the conftest: run `tests/ui/test_tabs.py`), `openspec validate ui-test-time-limit
  --strict` and the trial archive (`.lado/sdlc.md`, Checks).
- [x] 4.2 The pull request's CI: the four `ui (<k>)` cells green; from their junit
  artifacts, name the longest UI test and its time in the build report (AC-4).
