Task: LAD-60

## Why

Since LAD-41 a CI run takes 9.7 min in the median (12.5 at p90), against 4.0 before: the
integration tests run in one process (`-n0`), about 6 min on each Python, after the unit
tests in the same job `check`. A task waits for CI two to three times
(docs/research/merge-path.md, sections 3.1-3.2). The research recommends R1 (shard the
integration and UI tests), R2's aggregate check `ci-ok` (taken in part: no skip of heavy
jobs for documentation-only pull requests, the human's decision), R3 (no smoke for pull
requests it cannot concern, a daily smoke on `main`) and R4 (cancel a pull request's
superseded runs). The external review of that research (PR #39, a comment in LAD-60)
adds: the smoke is skipped by a job-level `if`, not `paths-ignore` (E1); where the daily
smoke runs and who sees it fail (E2); runs outside pull requests are grouped by
`github.run_id`, so they are never cancelled (E3); `ci-ok` has `if: always()`, held by a
test (E4).

The ruleset of `main` requires `check (3.10)`, `check (3.13)`, `js` and `ui`. Once the
jobs are sharded, `check (3.10)` and `ui` no longer report, so the ruleset must require
`ci-ok` instead before this pull request can merge.

## What Changes

- `.github/workflows/ci.yml`:
  - job `unit` per Python (3.10, 3.13): `ruff format --check`, `ruff check`,
    `uv run pytest -n auto`;
  - job `integration` per Python and shard 1-3: `uv run pytest -m integration -n0
    --shard K/3`;
  - job `ui` per shard 1-2: `uv run pytest -m ui -n 2 --shard K/2`; shard 1 runs
    `make dist` (the bundle in the sdist and the wheel), shard 2 only builds the web UI;
  - job `js` as it is;
  - job `changes`: whether the smoke is needed (always outside a pull request; on a pull
    request unless every changed file is under a path of the list R3 names);
  - job `smoke` as it is, with `needs: changes` and a job-level `if` on its answer;
  - job `ci-ok`: needs every other job, `if: always()`, red unless each succeeded, the
    smoke being allowed to be skipped only when `changes` said it is not needed;
  - triggers: also `schedule` (daily, 03:47 UTC: the whole CI, the smoke with it) and
    `workflow_dispatch`;
  - `concurrency`: a pull request's group is its number with `cancel-in-progress`; any
    other run's group is its `github.run_id`, never cancelled.
- `tests/conftest.py`: an option `--shard K/N` that keeps the tests whose node id falls
  in shard K by a stable hash; usable locally too.
- `scripts/smoke_ci.py`: a command `needed` that answers the smoke question from the
  changed files and the list; `scripts/ci_ok.py`: the verdict of `ci-ok` from the needed
  jobs' results.
- `tests/test_ci_workflow.py`: the pinned commands of the shards, the triggers, the
  concurrency rule, `ci-ok` needing every other job with `if: always()`, the smoke's
  `needs` and `if`, and the guard of the skip list.
- AGENTS.md (Commands, Testing) and `.lado/sdlc.md` ("What CI proves") say what CI runs
  now.
- The ruleset of `main` ("main: PR and green CI") requires `ci-ok` only: switched right
  before this pull request merges, once `ci-ok` is green on it, with the human's yes;
  then `ci-ok` is checked green on `main` after the merge.

## Scope

`.github/workflows/ci.yml`, `tests/conftest.py`, `scripts/smoke_ci.py`,
`scripts/ci_ok.py` (new), `tests/test_ci_workflow.py`, `tests/test_smoke_ci.py`,
`tests/test_ci_ok.py` (new), a unit test of `--shard`, AGENTS.md, `.lado/sdlc.md`
("What CI proves" only: LAD-61 changes its other sections in parallel). A new
capability `continuous-integration`. No version bump and no CHANGELOG line: nothing a
user of LADO sees changes. `make check` and every local command stay as they are.

## Out of scope

- Skipping the heavy jobs for a documentation-only pull request (R2's other half): the
  human's decision, its gain was 1 pull request of 38 and its risk medium
  (docs/research/merge-path.md, R2).
- A separate workflow for the daily smoke: it would need a second copy of the smoke's
  matrix to keep equal to `PINS`; a `schedule` in ci.yml runs it with the rest.
- A notification channel for a red daily run beyond GitHub's own mail (to whoever last
  changed the cron line) and the Actions tab: the human's decision.
- Keeping the old job names (`check (3.10)`, `ui`) so the old ruleset still matches: until
  the switch a pull request could merge with a red integration shard.
- Measuring the gain with `docs/research/merge-path/measure.py`: it needs a week of runs
  after the merge, so it is done then, outside this pull request.
- The flake policy and the integrator's reliance on CI (R5, R6): LAD-61.
- Balancing the shards by measured durations: a stable hash first; the measurement
  shows whether one shard is slower.

## Impact

- CI: more jobs (12 to 21 per run on a pull request with smoke), wall time ~9.7 min to
  ~4-5 min expected; one required check `ci-ok`.
- Repository settings: the ruleset of `main`.
- Spec: new capability `continuous-integration`.
