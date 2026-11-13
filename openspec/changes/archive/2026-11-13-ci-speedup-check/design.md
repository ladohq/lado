## Context

LAD-252 is a measurement: did the CI speedup of 2026-11-09 (LAD-248, LAD-249, the GitHub
Team plan, LAD-236) bring a pull request's wait for CI to about 7-8.5 minutes at the
median, and does each part pay for itself. The baseline is the LADO session artifacts
`ci-analysis` and `ci-external` (2026-11-09). The human chose the form (design dialogue,
2026-11-12): a report and a script in `docs/research/` through a pull request with
documents only, as LAD-58 did, plus a Russian artifact and a comment on the task; the
next steps are drafts, created only on a separate "yes, create".

Facts found in the design step: everything the task measures is on `main` (ci.yml: four
UI shards, the job `web`, the browser cache step, `container (<arch>, <k>)`, buildx with
`type=gha` written only by push and schedule from shard 1, timeouts on every job; the
Dockerfile installs the wheel last). Changes after 2026-11-09 that touch the numbers:
the unit job runs Python 3.10 and 3.14 (`4814cf0c`), each test cell uploads its junit
report for 90 days (`3bbd1b70`), `ci-rerun.yml` also restarts runs stuck in GitHub's
queue (LAD-274, `8cd84886`). The Actions cache held 11.06 GB in 398 entries on
2026-11-12, above the 10 GB limit. The tasks of the known flakes (LAD-236, LAD-246,
LAD-188, LAD-245, LAD-210) are done and archived.

## Options for the form

1. **A report and a script in the repository, through a pull request** (chosen). Long-term
   cost: one more folder under `docs/research/`; the measurement can be repeated by one
   command after the next CI change.
2. **Only an artifact and a tracker comment.** Cheaper now; the next measurement starts
   from nothing again, as this one did after `ci-analysis`'s scripts stayed in a
   scratchpad.

The second was the cheaper; the human chose the first.

## Decisions

- **D1. Two windows, one script.** "Before" is 2026-11-05 21:00 to 2026-11-09 12:30 UTC
  (the baseline's "last 3.4 days"), "after" is 2026-11-09 12:30 to 2026-11-13 00:00 UTC.
  Both are measured by `measure.py` with the same definitions, so the comparison does
  not depend on how `ci-analysis` was computed; the baseline artifacts' numbers are
  quoted next to "before" and a difference is explained. Reason: same method on both
  sides.
- **D2. The "after" window holds only runs of the new job set.** A run counts only when
  its jobs include `ui (k)` for k=1..4 and `web`; a pull request run of a branch made
  before PR #262 (old job set) is left out and counted. Reason: such runs measure the old
  CI.
- **D3. Definitions as in the baseline.** Wait = `max(completed_at)` of the first
  attempt's jobs − the run's `created_at`, green first attempts only; queue = a job's
  `started_at − created_at`; concurrent jobs = jobs of any run of the repository running
  at the job's `created_at` (all workflows, as GitHub's limit counts them); a flake = a
  run whose first attempt failed a test job and a later attempt of the same SHA passed;
  no runner = a job cancelled without steps and without `runner_name`. Reason: a
  comparison with `ci-analysis` needs its definitions.
- **D4. The browser cache hit is read from the job log**, not from step timings: a miss
  has `apt-get update` or `Get:` lines in the step `Browser` (the line LAD-248's AC-3
  used). Logs are fetched for every UI job of the window (`gh api .../jobs/<id>/logs`).
  Reason: a fast miss and a slow hit look alike in timings.
- **D5. Docker cache: hit and its gain from the step `Image`.** Per architecture and
  event; a pull request run whose `Image` took more than 60 s, or whose log shows layers
  built rather than `CACHED`, is a miss; eviction is checked against the cache list
  (`gh api repos/ladohq/lado/actions/caches`, the `buildkit-blob` and browser entries
  and their `last_accessed_at`). Whether the cache pays: the seconds saved on the
  critical path (only when a container cell ends the run) against the space it takes
  of 10 GB and what it evicts.
- **D6. The Team plan is judged by the peak of concurrent jobs and the queue above 20.**
  When fewer than 5 % of jobs were created with 20 or more jobs running, the report says
  the plan can go back to Free with the expected queue cost; otherwise it keeps it. The
  macOS limit (5) is reported separately: Team does not change it.
- **D7. Flaky tests from junit reports, else from logs.** The junit artifacts kept since
  `3bbd1b70` give the failed test names; for a job without one, its log. Each failed test
  of the window "after" is looked up in the tracker (`search`) for an open task; one
  with none becomes a proposed task.
- **D8. Language and redaction.** The report in the repository is English (`.lado/sdlc.md`:
  design docs and openspec in English); the artifact `ci-report` and the tracker comment
  are Russian. No token, personal path or e-mail is written; the script reads the token
  only through `gh`.
- **D9. No delta.** The change has no behaviour rule: it is archived with `--skip-specs`;
  the living spec `continuous-integration` stays as it is.

## Tests and checks

No requirement, no test layer: the script is research evidence, run by hand, as LAD-58's
`measure.py`. Checks: `--help` runs; a grep shows no `gh api` with a method other than
GET; `make lint` passes (ruff covers `docs/research/`); the report's numbers against the
script's output; `openspec validate ci-speedup-check --strict`.

## Version

Docs only: no CHANGELOG line, no version bump.
