## Context

GitHub cancels a job it could not hand to a hosted runner "after multiple attempts"; for
`macos-latest` (arm64) this happens when GitHub lacks macOS arm64 capacity (its notice on
the same job says so). The job has no steps, an empty `runner_name`, conclusion
`cancelled`, and a check-run annotation of level `failure`: "The job was not acquired by
Runner of type hosted even after multiple attempts". `ci-ok` then fails (a cancelled job
fails it, `scripts/ci_ok.py`), and the run's conclusion is `failure`. A run cancelled by
the concurrency rule instead ends `cancelled` as a whole, its jobs with the annotation
"Canceling since a higher priority waiting request for ci-<n> exists".

## Decisions

- D1. A separate workflow on `workflow_run` (`workflows: [CI]`, `types: [completed]`),
  not a step in `ci.yml`: only a finished run can be rerun (`gh run rerun` refuses one in
  progress), and `ci-ok`, the last job, is still running at its own end. The workflow runs
  the default branch's files, so a pull request cannot change what it does.
- D2. Its job's `if`: `github.event.workflow_run.conclusion == 'failure' &&
  github.event.workflow_run.run_attempt == 1`. Superseded runs end `cancelled` and are
  never looked at; the rerun is attempt 2, so the workflow can never loop.
- D3. The verdict in `scripts/ci_rerun.py`, standard library only like `ci_ok.py`, with
  `gh api` for the facts (the job's `GH_TOKEN` is `github.token`): the run's jobs of attempt
  1, and for each job not `success`/`skipped` but `ci-ok`, its check-run annotations. Rerun
  only when that set is non-empty and each job in it is `cancelled`, has no steps, no runner
  and an annotation containing "was not acquired by Runner". The annotation is the proof;
  the other three keep a job that started from counting. A pure function
  `verdict(run, jobs, annotations, newest_run_id)` returns (rerun?, reason) so the unit
  tests need no network.
- D4. For a `pull_request` run, the newest CI run with the same event and head branch
  (`actions/workflows/ci.yml/runs?event=pull_request&branch=<head_branch>&per_page=1`) must
  be this run; otherwise no rerun. A rerun joins the concurrency group `ci-<pr>` and, with
  `cancel-in-progress`, would cancel the newer run. A fork's branch sharing the name can
  only make it skip, never rerun wrongly.
- D5. `scripts/ci_rerun.py <run-id>` prints its verdict and reason and changes nothing;
  `--rerun` also runs `gh run rerun <id> --failed`. The workflow passes `--rerun`; a
  developer checks the verdict on past runs by hand (AC-3). The workflow checks out the
  default branch only for the script (`actions/checkout`, pinned as in `ci.yml`).
- D6. Permissions: `actions: write` (rerun), `checks: read` (annotations), `contents:
  read` (checkout); nothing else.
- D7. Tests: unit tests of `verdict` (each scenario of the delta, plus a green run and a
  job that started and was cancelled), and of the workflow file in
  `tests/test_ci_workflow.py` or a sibling: trigger, `if`, permissions, the `--rerun`
  command, no checkout of `head_sha`/`head_branch`. No integration layer: nothing of LADO's
  processes is involved. The real path (a runner-less cell on GitHub) cannot be forced; it
  is proven by the verdict on the five recorded runs (AC-3) and seen live the next time
  GitHub lacks capacity.
- D8. `.lado/sdlc.md`: the Review trap "A CI job red with no cause in the work" gains one
  sentence: a cell cancelled with "not acquired by Runner" is rerun by `ci-rerun.yml`;
  wait for the run's second attempt, and only when that one fails so too, rerun by the
  trap. Not counted as a flake of a test: it is no test's fault.
