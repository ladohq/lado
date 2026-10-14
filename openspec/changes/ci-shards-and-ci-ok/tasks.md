## 1. Shards

- [ ] 1.1 Unit tests first, `tests/test_shard.py` (layer 1, pytester): with `--shard
  K/3` over a generated module of tests, the three runs together hold every test exactly
  once and two runs give the same split; without `--shard` all run; `--shard 0/3`,
  `4/3`, `1/0` and `x` are usage errors.
- [ ] 1.2 `tests/conftest.py`: `--shard K/N` (D1). `make lint`, `make test`; locally
  `uv run pytest -m integration --collect-only -q --shard K/3` for K = 1..3 add up to the
  full count.

## 2. The smoke question and ci-ok's verdict

- [ ] 2.1 Unit tests first, `tests/test_smoke_ci.py`: `needed` is true for a push,
  schedule and dispatch; on a pull request false only when every changed file is on the
  list (folder prefix and exact path), true for an empty diff, a new top-level file, a
  file under `src/` beside docs; an empty list is refused; the output line is
  `smoke=true|false`.
- [ ] 2.2 `scripts/smoke_ci.py needed` (D4).
- [ ] 2.3 Unit tests first, `tests/test_ci_ok.py`: all success passes; a failure,
  a cancelled job or a skipped non-smoke job fails and names the job; smoke skipped
  passes only with `changes` saying `false`.
- [ ] 2.4 `scripts/ci_ok.py` (D5). `make lint`, `make test`.

## 3. The workflow

- [ ] 3.1 `tests/test_ci_workflow.py` first: the pinned pytest commands of `unit`,
  `integration` (matrix 3.10, 3.13 × 1-3, `--shard ${{ matrix.shard }}/3`) and `ui`
  (1-2, `--shard ${{ matrix.shard }}/2`, `make dist` only in shard 1); the triggers
  (push to main, pull_request, the schedule, workflow_dispatch); the concurrency rule
  (D7); `smoke` needs `changes` with its `if`; `ci-ok` needs every other job and has `if:
  always()`; the skip list equals the test's own and none of its paths is or contains a
  path the smoke runs (the requirement's list); the docstring.
- [ ] 3.2 `.github/workflows/ci.yml` (D2-D7); every `uses:` pinned as before
  (`tests/test_workflow_security.py`). `make lint`, `make test`.

## 4. Documents

- [ ] 4.1 AGENTS.md: Commands (the CI paragraph: the shards, `ci-ok`, the smoke's filter
  and daily run, the concurrency; `tests/test_ci_workflow.py` pins) and Testing (layer 4
  "in CI", layer 5 "in CI on Linux and macOS" with the filter). `.lado/sdlc.md`, "What
  CI proves" only: the full suite on every pull request, the smoke on `main`, daily and
  on pull requests beyond the skip list; a green `ci-ok` is the full `make check` plus,
  but for those pull requests, the smoke.

## 5. In CI

- [ ] 5.1 Push the branch: every job green on the pull request; `ci-ok` green; the
  integration shards' times in the build report (each shard's test count and minutes,
  against 6 min before).
- [ ] 5.2 Check the filter on the pull request's own run (it changes `scripts/`, so the
  smoke runs) and, by `scripts/smoke_ci.py needed` locally on a docs-only commit range,
  that it would skip.
- [ ] 5.3 At merge (integrator, D8): the ruleset to `ci-ok` only with the human's yes,
  merge, `ci-ok` green on `main`.
