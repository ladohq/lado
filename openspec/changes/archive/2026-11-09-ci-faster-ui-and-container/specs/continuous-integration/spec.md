## MODIFIED Requirements

### Requirement: Integration and UI tests run in shards

CI SHALL run the integration tests in 3 jobs per Python version (3.10, 3.13), each with
`-n0`, and the UI tests in 4 jobs, each with `-n 2`, none of them running `make dist`. A
test SHALL be in exactly one shard of its layer, chosen by a stable hash
of its node id (`--shard K/N`), so a run never skips or repeats a test.

#### Scenario: Every test in one shard

- **WHEN** the integration tests are collected with `--shard 1/3`, `2/3` and `3/3`
- **THEN** each test is in exactly one of the three, and the same test lands in the same
  shard in every run

#### Scenario: No shard option

- **WHEN** pytest runs without `--shard`
- **THEN** it runs every collected test, as before

#### Scenario: The UI tests in four shards

- **WHEN** the UI tests are collected with `--shard 1/4` to `4/4`
- **THEN** each UI test is in exactly one of the four jobs `ui (1)` to `ui (4)`, and each
  of those jobs builds only the web UI's bundle before its tests

### Requirement: CI builds and smoke-tests LADO's image on amd64 and arm64

CI SHALL have a job `container`, two cells per architecture on GitHub's native runners
(`ubuntu-24.04` for amd64, `ubuntu-24.04-arm` for arm64), each of which builds the web UI's
bundle and the wheel from the run's code, builds `docker/Dockerfile` from that wheel, and
runs its shard (`--shard K/2`) of the container tests (`tests/container/`, marker
`container`) against the image.

#### Scenario: A pull request breaks LADO in the container

- **WHEN** a pull request makes `lado doctor` print a `[FAIL]` in the image
- **THEN** the container cell holding that test fails on both architectures, and `ci-ok`
  fails and names it

#### Scenario: Every container test in one shard

- **WHEN** the container cells of one architecture run with `--shard 1/2` and `--shard 2/2`
- **THEN** each container test runs in exactly one of them

## ADDED Requirements

### Requirement: The web UI's checks run beside the browser tests

CI SHALL have a job `web` that runs `make dist` (the web UI's stale-types check, type
check, unit tests and build, and the bundle in both the sdist and the wheel) and the Node
tests (`node --test tests/js/*.test.mjs`), on every run, needed by `ci-ok`; no UI job
SHALL wait for it.

#### Scenario: A vitest test fails

- **WHEN** a pull request breaks a test of `web/src/`
- **THEN** the job `web` fails, the UI jobs run their browser tests to their end, and
  `ci-ok` fails and names `web`

#### Scenario: A Node test of the plugin fails

- **WHEN** a pull request breaks a test of `tests/js/`
- **THEN** the job `web` fails and `ci-ok` fails

### Requirement: Every CI job has a time limit

Every job of `.github/workflows/ci.yml` SHALL set `timeout-minutes`, so a job that hangs
ends red within its limit instead of GitHub's six hours.

#### Scenario: A job without a limit

- **WHEN** a job of ci.yml has no `timeout-minutes`
- **THEN** the unit tests fail and name the job

#### Scenario: A mirror hangs

- **WHEN** a UI job's browser setup hangs on an apt mirror
- **THEN** the job ends red within 25 minutes, and `ci-ok` fails

### Requirement: The UI jobs take the browser from a cache saved by main

A UI job SHALL restore Chromium and the `.deb` files Playwright's `--with-deps` downloads
from a GitHub cache keyed by Playwright's version and the runner image's version. On a hit
it SHALL install them with `dpkg` and Chromium without `--with-deps`, asking no apt mirror;
on a miss it SHALL run `playwright install --with-deps chromium` with apt retries and a
network timeout. Only a run not of a pull request SHALL save the cache.

#### Scenario: A pull request after main saved the cache

- **WHEN** a pull request's UI job starts and main's run saved the cache for the same
  Playwright and runner image
- **THEN** the job installs the cached packages and Chromium, its log has no
  `apt-get update`, and it saves nothing

#### Scenario: Playwright is upgraded

- **WHEN** a pull request changes Playwright's version in `uv.lock`
- **THEN** its UI jobs miss the cache and install with `--with-deps` as before, and the
  push to main after its merge saves the new cache

#### Scenario: The runner image is updated

- **WHEN** GitHub rolls out a new runner image version
- **THEN** the key misses, the packages are installed with `--with-deps`, and the next
  run outside a pull request saves them for that image
