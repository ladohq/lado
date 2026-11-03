Task: LAD-179

## Why

Smoke cells on `macos-latest` (macOS arm64) are now and then cancelled before they get a
runner: no step runs, no runner is named, and after 13-23 minutes the job ends
`cancelled` with GitHub's annotation "The job was not acquired by Runner of type hosted
even after multiple attempts", next to the notice "Due to capacity constraints, jobs
targeting macOS arm64 runners may experience longer queue times". Our
`timeout-minutes: 20` plays no part (it counts from a runner's start), nor does the
concurrency rule (a superseded run's job carries "Canceling since a higher priority
waiting request for ci-<n> exists" instead).

Over 255 CI runs with macOS cells from 2026-10-22 to 2026-11-03 (1068 macOS jobs) this
happened to 7 jobs in 5 runs: PR runs 40713637396, 41496744121, 41521506385, 41522195315
and the push to `main` 41529673835, four of them on the evening of 2026-11-02. A cancelled
cell fails `ci-ok`; a rerun of the failed jobs passed every time. On pull requests the
agents rerun by the Review trap of `.lado/sdlc.md`, but a red run of `main` or of the
daily schedule waits until someone notices it (41529673835 stayed red for ten hours).

## What Changes

- A new workflow `.github/workflows/ci-rerun.yml`, started when a CI run completes with
  `failure` on its first attempt. Its script `scripts/ci_rerun.py` reruns the run's failed
  jobs once (`gh run rerun <id> --failed`) when every job that did not succeed, `ci-ok`
  aside, was cancelled without a runner and carries GitHub's annotation "was not acquired
  by Runner"; it reruns nothing when any other job failed, or when a pull request's run
  has a newer CI run of the same pull request (a rerun would cancel that newer run through
  the concurrency group).
- `docs/testing.md` names the cause and the workflow; `.lado/sdlc.md`'s Review trap on
  CI jobs red with no cause in the work tells the agent waiting for CI to wait for the
  automatic second attempt instead of rerunning such a cell itself.

## Acceptance criteria

- AC-1: A CI run whose only unsuccessful jobs are cells cancelled with the annotation "was
  not acquired by Runner" (and `ci-ok`) is rerun once, its failed jobs only, without a
  person or an agent.
- AC-2: A run with any other failed or cancelled job, a run already on its second or later
  attempt, a run cancelled as a whole (superseded), and a pull request's run with a newer
  CI run of that pull request are not rerun; the workflow's log says why.
- AC-3: The script, run by hand without `--rerun` on run 41529673835, says it would
  rerun it; on 41522042790 (superseded) and on a green run, that it would not.
- AC-4: `docs/testing.md` names the cause (GitHub's macOS arm64 capacity, the annotation)
  and the rerun workflow; the Review trap in `.lado/sdlc.md` says to wait for the
  automatic attempt.
- AC-5: `ci.yml`, `ci-ok` and its rule are unchanged; the new workflow checks out no code
  of the pull request and has only the permissions it needs.

## Scope

- `.github/workflows/ci-rerun.yml`, `scripts/ci_rerun.py`, their unit tests,
  `docs/testing.md`, the one Review trap of `.lado/sdlc.md`, the living spec
  `continuous-integration`.
- Already done at the human's word during design: run 41529673835 of `main` rerun by hand.

## Out of scope

- Intel macOS runners (`macos-15-intel`): the capacity notice is for arm64 only, but it is
  GitHub's last Intel image and LADO's users run Apple silicon; the smoke would stop
  testing their machines.
- One macOS job for all four providers: four times fewer runner requests, but a longer run
  and no result per provider.
- A higher `timeout-minutes` or a job-level retry in `ci.yml`: the timeout does not cover
  the wait for a runner, and GitHub Actions has no retry of a job.
- More than one automatic attempt: a second "not acquired" is left to the Review trap's
  manual reruns, so a long outage of GitHub's macOS fleet does not loop.
- A CHANGELOG line and a version bump: nothing LADO's users see changes.

## Impact

- CI only: a new workflow and script, active once merged into `main` (`workflow_run`
  runs the default branch's file). No code of LADO, no schema, no CHANGELOG line.
