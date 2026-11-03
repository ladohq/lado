# LAD-179 ci-rerun-runnerless-jobs: review report

Pull request #209 `fix/lad-179-ci-rerun-runnerless` → `main`. Scale: tweak, review depth:
precision. Head reviewed: `fbc22672` (= the remote head). A new workflow
`.github/workflows/ci-rerun.yml` (on `workflow_run` of CI, first attempt, conclusion
`failure`) runs `scripts/ci_rerun.py --rerun`, which reruns the run's failed jobs once
when every unsuccessful job but `ci-ok` was cancelled without a runner with GitHub's
annotation "was not acquired by Runner", and no newer CI run of the same pull request
exists. Delta: two requirements added to `continuous-integration`.

## Rounds

- **Round 1** (local, `origin/main..fbc22672`): precision over the whole diff; the
  workflow, script and tests read against `ci.yml` (triggers, concurrency, the name
  `ci-ok`, `fail-fast: false`); lenses tests, silent failures, comments and security.
  Found F1, F2, F3.
- **External round 1** (Claude Code GitHub Action, 2026-11-03 09:34Z → 09:35Z): read the
  risky files `ci-rerun.yml` and `ci_rerun.py`, not the tests, docs or openspec. Found
  E1–E4.

External rounds used: 1 of 1 (the tweak cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the jobs of attempt 1 and their annotations are read without pagination | declined: CI has 22 jobs; a cut list can only skip a rerun or make a harmless `--failed` one |
| F2 | minor | seconds between the newest-run query and `gh run rerun`: a push then would be cancelled by the rerun through `ci-<pr>` | declined: a window of seconds, the cancelled run is visible and rerun by the Review trap; residual risk |
| F3 | — | `actions/checkout` keeps `persist-credentials` | refuted: the job runs only `main`'s code (`workflow_run`, checkout without `ref`) |
| E1 | minor | the newest run is found by branch name only; forks may share a branch name | declined: errs only towards skipping a rerun (design D4) |
| E2 | minor | a red `CI rerun` on a transient API error is not explained in the docs | declined: the failure is safe (no rerun); agents follow the trap's manual reruns |
| E3 | minor | a closed pull request's run is not excluded | declined: a rerun of it is harmless, only costs macOS minutes |
| E4 | — | pagination | duplicate of F1 |

## Checks

- `make lint`: green.
- `make test`: 4789 passed, 7 skipped; `test_ci_rerun*`, `test_workflow_security`,
  `test_ci_workflow` with `-n0`: 89 passed.
- `openspec validate ci-rerun-runnerless-jobs --strict` valid; tasks 6/6;
  `openspec validate --specs --strict` 56 passed.
- AC-3 rechecked by the reviewer without `--rerun`: 41529673835 would rerun; 41522042790
  (cancelled), 41594402152 (success), 41496744121 (newer run), 41522195315 (container
  amd64 failure) would not.
- CI on head `fbc22672` (run 41611614804): success, `ci-ok` among the checks.
- Not run: the workflow itself on GitHub (`workflow_run` takes `main`'s file, so it runs
  only after the merge; seen live at the next macOS arm64 shortage); live tests (no change
  to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`).

Found on the way: none.
