Task: LAD-248

## Why

A pull request waits for a green CI run 12.8 minutes at the median and 20.4 at p90
(204 runs of 2026-11-05..09; three weeks before, 7.3). The run ends with its longest job,
and that is now nearly always a UI shard: `pytest -m ui` takes 8-11 minutes per shard
since the UI suite doubled (235 to 473 tests in four days), and shard 1 also runs
`make dist` (types, vitest, the build; 92 s) before its tests. Next comes the container
job: 7.5-8.2 minutes per architecture, 64 tests in one process.

The browser setup has a long tail: `playwright install --with-deps chromium` runs
`apt-get update` and downloads nine font packages (21 MB) from the Ubuntu mirror on every
UI job. The mirror sometimes serves 27 KB/s or hangs: 6.4 % of UI jobs spent more than five
minutes there in three weeks, and on 2026-10-31 `ui (1)` hung six hours, GitHub's default
job limit, because `unit`, `integration`, `js`, `ui`, `changes` and `ci-ok` set no
`timeout-minutes`. Chromium itself comes from Playwright's CDN in a few seconds.

The root causes are the configuration, not the tests: two shards for a suite that
doubled, a check that needs no browser on the browser job's critical path, a network
download from a slow mirror on each run, one container cell per architecture, and no time
limit. The analysis is in the LADO session artifacts `ci-analysis` and `ci-external`.

## What Changes

- Every job of `ci.yml` has `timeout-minutes`: `unit` 15, `integration` 15, `ui` 25,
  `web` 15, `changes` 5, `ci-ok` 5; `smoke` 20 and `container` 30 as before.
- The UI tests run in four shards (`-n 2 --shard K/4`), each building only the web UI's
  bundle. `make dist` leaves the UI shards for a new job `web`, which also runs the Node
  tests (`node --test tests/js/*.test.mjs`); the job `js` goes.
- The UI jobs take Chromium and the system packages `--with-deps` downloaded from a GitHub
  cache keyed by Playwright's version and the runner image's version: on a hit they install
  the cached `.deb` files with `dpkg` and run `playwright install chromium`, touching no
  Ubuntu mirror; on a miss they run `playwright install --with-deps chromium` as today,
  with apt retries and a short network timeout, and keep what apt downloaded. Only runs
  outside pull requests (push to main, schedule, dispatch) save the cache; pull requests
  read it.
- The container tests run in two shards per architecture (`container (<arch>, <k>)`, four
  cells), each building the image and passing only with a pass and no skip;
  `scripts/smoke_ci.py container <out> [K/N]` passes the shard to pytest.
- `ci-ok` needs every job, the new ones included, with the same rule.
- `tests/test_ci_workflow.py`, `tests/test_smoke_ci.py`, `docs/testing.md` and the line
  "What CI proves" of `.lado/sdlc.md` follow.

## Acceptance criteria

- AC-1: Every job of `ci.yml` has a `timeout-minutes` (the values above), and the unit
  tests fail when a job lacks one.
- AC-2: The UI tests run in four shards on two workers each; no UI job runs `make dist`,
  vitest or tsc; the job `web` runs `make dist` and the Node tests; every UI test is in
  exactly one shard.
- AC-3: A UI job whose cache key hits installs the browser and its system packages
  without a request to an Ubuntu mirror (no `apt-get update`, no `Get:` line in the step's
  log) in at most 15 s; a miss installs them with `--with-deps` as today and, outside a
  pull request, saves the cache. Shown by two `workflow_dispatch` runs on the pull
  request's branch: the first misses and saves, the second hits.
- AC-4: The container tests run in two shards on each of amd64 and arm64; each cell is
  red unless its pytest passed with a pass and no skip; each test runs in exactly one
  shard per architecture.
- AC-5: `ci-ok` needs every other job, runs whatever their results and is green only when
  all of them succeeded (the smoke skipped by its filter aside); the pull request's CI is
  green.
- AC-6: In the pull request's own green run, no UI job and no container cell takes more
  than 7 minutes (today 11.1 and 8.2 at the median); the build report gives each job's
  time next to the baseline.
- AC-7: No test file changes its tests; the commands that run them are those of today but
  for the shard counts.

## Scope

- `.github/workflows/ci.yml`; `scripts/smoke_ci.py` (the container cell's shard);
  `tests/test_ci_workflow.py`, `tests/test_smoke_ci.py`; `docs/testing.md` (CI);
  `.lado/sdlc.md`, the line "What CI proves" only; the living spec
  `continuous-integration`.

## Out of scope

- `docker/Dockerfile` and the Docker layer cache in CI: LAD-249 does them. Both change the
  job `container`; the pull request merged second takes the other's change in.
- The GitHub Team plan (60 parallel jobs instead of 20), larger or third-party runners:
  the task asks for configuration of the free standard runners. The run grows from 23 to
  27 jobs, which on the free plan's 20 can queue a second pull request's run longer; the
  `js` job folded into `web` keeps one slot back.
- Skipping the heavy jobs by the changed files, as the smoke is: a separate decision on
  what each change may leave unchecked.
- Fixing flaky tests, cheaper UI tests, `--durations` in CI: they change tests or their
  output; tasks of their own.
- A third-party action for the apt cache (`cache-apt-pkgs-action`) or the Playwright
  container image: a new party with access to CI of a public repository, or a different
  environment for the UI tests; `actions/cache` with apt's own files does the same.
- A CHANGELOG line and a version bump: nothing LADO's users see changes.

## Impact

- CI only. No code of LADO, no schema, no CHANGELOG line.
- The cache: one entry of about 0.3 GB per (Playwright version, runner image version),
  saved by `main`, beside the uv and npm caches (2.4 GB of 10 GB used) and LAD-249's
  Docker cache.
