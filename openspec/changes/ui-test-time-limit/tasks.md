## 1. The limit of a UI test

- [x] 1.1 `pyproject.toml`, dev group: add `pytest-timeout` (the version `uv add --dev`
  picks, as a `>=` floor like the other entries); `uv lock`. Check: `uv sync --locked`.
- [x] 1.2 `tests/ui/conftest.py`: a constant `TEST_TIMEOUT = 120` (seconds) with a comment
  (LAD-271: a hang fails the test with its stack instead of the CI job's cancel; the
  longest UI test takes ~13 s in CI), given to every item collected under `tests/ui/` as
  `pytest.mark.timeout(TEST_TIMEOUT)` by a collection hook of that conftest (scoped to its
  folder, e.g. `pytest_itemcollected`), not in `pyproject.toml`'s `addopts`, so no other
  layer gets it. pytest-timeout's default method (`signal` on Linux and macOS) and its
  default of counting fixtures. The module docstring names the limit. Check:
  `uv run pytest -m ui -n 2 tests/ui/test_tabs.py` green.
- [x] 1.3 A unit test, `tests/test_ui_time_limit.py` (`pytest_plugins = "pytester"`, as
  `tests/test_shard.py`):
  - `test_every_ui_test_has_the_limit`: collects the real `tests/ui` with `-m ui --collect-only`
    (in a subprocess when an in-process collection clashes with the running session) and
    asserts every item's `timeout` marker is
    `TEST_TIMEOUT`, and that there are items (AC-1);
  - `test_a_test_past_its_limit_fails_with_its_stack_and_the_run_goes_on`: a pytester
    suite run with `runpytest_subprocess` (pytest-playwright refuses a run inside a test),
    `-p xdist -n 2`, the same hook as 1.2 with a limit of 1 s, one test that sleeps 30 s
    and one that passes: the sleeper fails with `Timeout` and a traceback through its
    `sleep` line, the other passes, the run ends in well under 30 s, and `--junitxml`
    names the sleeper as failed (AC-2). Share the hook so the test runs the conftest's own
    code (e.g. the hook reads the limit from the module, and the test imports the hook as
    `tests/test_shard.py` imports `shard`), not a copy.
  Check: `make test`; the first test fails with the hook removed (try it, then restore).

## 2. CI

- [x] 2.1 `.github/workflows/ci.yml`, job `ui`: the pytest step gets `timeout-minutes: 12`
  (its p90 is ~5 min) and a comment: a step past its limit ends red with its log kept and
  the junit upload still runs, which a job cancelled by its own limit loses; each test has
  its own 120 s (`tests/ui/conftest.py`). The job keeps `timeout-minutes: 25`; the upload
  keeps `if: always()`. Check: `make test`.
- [x] 2.2 `tests/test_ci_workflow.py`: a test that the `ui` job's pytest step has a
  `timeout-minutes` and it is under the job's (12 < 25), and that the junit upload is
  `if: always()` (AC-3); the module docstring names it. Check: `make test`; the test fails
  with the step's limit removed (try it, then restore).

## 3. Docs

- [x] 3.1 `docs/testing.md`: in the UI e2e layer, each UI test has 120 s, fixtures
  included (`tests/ui/conftest.py`, pytest-timeout), and a test past it fails with its
  stack; in the CI paragraph, the `ui` pytest step's 12 minutes under the job's 25 and why
  (a cancelled job keeps no log or junit). Check: read against `ci.yml` and the conftest.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `uv run pytest -m ui -n 2 <changed ui files>` (none
  but the conftest: run `tests/ui/test_tabs.py`), `openspec validate ui-test-time-limit
  --strict` and the trial archive (`.lado/sdlc.md`, Checks).
- [x] 4.2 The pull request's CI: the four `ui (<k>)` cells green; from their junit
  artifacts, name the longest UI test and its time in the build report (AC-4).
