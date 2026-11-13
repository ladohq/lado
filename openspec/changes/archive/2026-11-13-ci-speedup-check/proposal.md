Task: LAD-252

## Why

On 2026-11-09 CI was sped up: LAD-248 (job timeouts, Playwright's browser and fonts from
a cache, four UI shards, a job `web`, two container shards per architecture), LAD-249
(Docker layer cache, written only by `main` and the nightly run, LADO's wheel in the
image's last layer), the organisation `ladohq` moved to GitHub Team (60 concurrent jobs
instead of 20), and LAD-236 fixed a flaky test. The goal was a pull request's wait for CI
of about 7-8.5 minutes at the median, from 12.8 (p90 20.4). Nobody has measured yet
whether that happened, nor whether each part pays for itself: the Docker cache (cache
space against seconds saved), the Team plan (queues above 20 jobs), the cache limit of
10 GB (on 2026-11-12 the repository's caches held 11.06 GB in 398 entries, so GitHub is
already evicting).

Since 2026-11-09 12:30 UTC (the merge of PR #262) there are 79 completed pull request
runs, 40 push runs and 3 nightly runs: the task's threshold (at least 20 and 3) is met.
The baseline is the LADO session artifacts `ci-analysis` and `ci-external` (204 runs of
2026-11-05 21:00 to 2026-11-09).

This change measures "before" and "after" with one script and writes up the result with
proposals. It builds nothing users get: the proposals are drafted at the report's end and
created in the tracker only on the human's separate yes.

## What Changes

- A script, `docs/research/ci-speedup-check/measure.py` (standard library, `gh` read-only),
  that prints Markdown tables for a window of CI runs, so the same measurement can be run
  again later:
  1. a pull request's wait: run created → last job of its first attempt done, green runs,
     median and p90;
  2. the critical path: which job ends the run, how often, and its duration;
  3. the browser step of the UI jobs: duration, cache hit or miss (a miss is a step log
     with `apt-get update` or `Get:` lines), tails over 60 s;
  4. the step `Image` of the container jobs per architecture and event (pull request,
     push, schedule), against 76 s amd64 and 66 s arm64; the nightly build from scratch:
     duration and result;
  5. the queue: job created → started, by the number of jobs already running when it was
     created (0-9, 10-19, 20-29, 30-39, 40-59, 60+), and the peak of concurrent jobs;
  6. the Actions cache: space used of 10 GB, by key family (`setup-uv`, `setup-node`,
     browser, `buildkit-blob`/Docker, other), and whether entries the runs need were
     evicted (cache misses of the browser and the Docker layers in pull request runs);
  7. timeouts: jobs ended by `timeout-minutes`, and jobs above 80 % of their limit;
  8. flakes and reruns: share of runs with more than one attempt, why (a test that
     passed on rerun, a runner not acquired), which tests failed, and whether the tests
     of LAD-236, LAD-246, LAD-188, LAD-245 and LAD-210 failed again.
- A research report, `docs/research/ci-speedup-check.md` (English): summary; what changed
  in CI and when; the before/after table of points 1-8; conclusions on the four questions
  of the task (goal reached; does the Docker cache pay; is the Team plan needed; is
  10 GB of cache enough); proposed next tasks.
- The same report in Russian as the run's artifact `ci-report`, and a Russian comment on
  LAD-252 with the before/after table, the conclusions and the proposed tasks.

## Scope

- GitHub Actions history of `ci.yml` in this repository (`gh run list`, `gh api` GET on
  runs, jobs, job logs, caches), two windows measured by the same script.
- Conclusions on: the goal (median ~7-8.5 min), the Docker cache, the Team plan, the
  cache space.
- Proposed next tasks as drafts (title in Russian, what it does, why, size): among the
  task's candidates, the ones the numbers support (skipping heavy jobs for pull requests
  of documentation or the web UI only, `--durations` and cheaper UI tests, open source
  programmes of Blacksmith or Namespace or 8-core runners, a new task per flaky test that
  failed in the window, removing the Docker cache if it does not pay).

## Out of scope

- Any change of `ci.yml`, the Dockerfile, the ruleset, the GitHub plan or `.lado/sdlc.md`:
  the task is a measurement; changes go to the proposed tasks (the human's decision).
- Creating tracker tasks or commenting on other tasks: the drafts are put to the human
  once as a list, and only the ones they answer "yes, create" are created (the human's
  decision). The tasks of the known flakes are done and archived, so a repeated flake
  gets a new task, not a comment there.
- `live.yml`, `windows-shell.yml`, `release.yml`, `claude.yml`: not on a pull request's
  path.
- Process changes (rounds of CI per pull request, merge queue): not asked by the task.

## Acceptance criteria

- AC-1: `python3 docs/research/ci-speedup-check/measure.py --help` runs with the standard
  library only; the script only reads GitHub (`gh run list`, `gh api` without `-X` or
  `--method`, or with GET).
- AC-2: The report's before/after table covers points 1-8 for the window "before"
  (2026-11-05 21:00 to 2026-11-09 12:30 UTC) and "after" (2026-11-09 12:30 to 2026-11-13
  00:00 UTC), each with its sample size and the command that printed it; the numbers agree
  with the script's output; where "before" differs from the baseline artifacts, the report
  says by how much and why.
- AC-3: The report answers each of the four questions with yes or no and the numbers
  behind it, names the job on the critical path after the change, and names the CI changes
  after 2026-11-09 that affect the numbers.
- AC-4: The report ends with proposed tasks, each with what, why (the number behind it)
  and size; a flaky test that failed in the window "after" is either a proposed task or
  named as already covered by an open task.
- AC-5: LAD-252 has a Russian comment with the before/after table, the conclusions and
  the proposed tasks; the run has the artifact `ci-report` in Russian.
- AC-6: No tracker task is created and no other task is commented without the human's
  "yes, create" for that very list.
- AC-7: No token, personal path or e-mail is in the report, the script or the commits.

## Impact

- Docs only: `docs/research/ci-speedup-check.md` and
  `docs/research/ci-speedup-check/measure.py` (new). No code, API, schema, spec or
  CHANGELOG change: nothing users get, no version bump (neither minor nor patch).
