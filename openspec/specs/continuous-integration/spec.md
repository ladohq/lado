# continuous-integration Specification

## Purpose
What LADO's CI on GitHub runs and when: the tests in shards, one required check `ci-ok`
that stands for the whole run, the smoke only where it can concern a change, and which
runs a newer one cancels.

## Requirements

### Requirement: One required check ci-ok

CI SHALL end every run with a job `ci-ok` that needs every other job of
`.github/workflows/ci.yml`, runs whatever their results (`if: always()`), and fails
unless each needed job succeeded; the only needed job it MAY see skipped is the smoke,
and only when the job `changes` said the smoke is not needed. The ruleset of `main`
requires `ci-ok` and no other check.

#### Scenario: A shard fails

- **WHEN** an integration shard fails on a pull request
- **THEN** `ci-ok` runs, fails and names that job, and the pull request cannot merge

#### Scenario: The smoke is skipped by its filter

- **WHEN** a pull request changes only files under `web/` and `docs/`
- **THEN** the smoke is skipped and `ci-ok` passes when every other job succeeded

#### Scenario: The smoke is skipped although it was needed

- **WHEN** the job `changes` said the smoke is needed and the smoke is skipped or cancelled
- **THEN** `ci-ok` fails

#### Scenario: A job is added without ci-ok needing it

- **WHEN** ci.yml has a job that `ci-ok` does not list in `needs`
- **THEN** the unit tests fail and name the job

#### Scenario: ci-ok loses if always()

- **WHEN** the job `ci-ok` has no `if: always()`
- **THEN** the unit tests fail

### Requirement: Integration and UI tests run in shards

CI SHALL run the integration tests in 3 jobs per Python version (3.10, 3.13), each with
`-n0`, and the UI tests in 2 jobs, each with `-n 2`, the first of them also running
`make dist`. A test SHALL be in exactly one shard of its layer, chosen by a stable hash
of its node id (`--shard K/N`), so a run never skips or repeats a test.

#### Scenario: Every test in one shard

- **WHEN** the integration tests are collected with `--shard 1/3`, `2/3` and `3/3`
- **THEN** each test is in exactly one of the three, and the same test lands in the same
  shard in every run

#### Scenario: No shard option

- **WHEN** pytest runs without `--shard`
- **THEN** it runs every collected test, as before

### Requirement: The smoke runs where it can concern the change

The smoke jobs SHALL run on every push to `main`, on the daily schedule, on manual
dispatch, and on every pull request except one whose every changed file is under a path
of the skip list: `web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`, `README.md`,
`CHANGELOG.md`, `AGENTS.md`, `BACKLOG.md`, `ROADMAP.md`, `SECURITY.md`,
`.github/dependabot.yml`.

#### Scenario: A pull request that changes LADO's code

- **WHEN** a pull request changes `src/lado/runtime.py` and `docs/design/ui.md`
- **THEN** the smoke runs on Linux and macOS for every provider

#### Scenario: A pull request of the web UI only

- **WHEN** every file a pull request changes is under `web/` or `tests/ui/`
- **THEN** the smoke is skipped and every other job runs

#### Scenario: A new top-level file

- **WHEN** a pull request adds a file that matches no path of the list
- **THEN** the smoke runs

#### Scenario: The daily run

- **WHEN** the schedule starts CI on `main`
- **THEN** every job runs, the smoke included

### Requirement: The smoke's skip list holds no path of code

The smoke MUST be skipped by a condition on its job, never by
filtering the workflow's triggers. No path of the skip list MAY be or contain `src/`,
`scripts/`, `tests/` (but `tests/ui/` and `tests/js/`), `docker/`, `pyproject.toml`,
`uv.lock` or `.github/workflows/`.

#### Scenario: The list gains a path the smoke runs

- **WHEN** someone adds `scripts/` or `tests/integration/` to the skip list in ci.yml
- **THEN** the unit tests fail

#### Scenario: The list gains the image's folder

- **WHEN** someone adds `docker/` to the skip list in ci.yml
- **THEN** the unit tests fail

### Requirement: Only a pull request's superseded runs are cancelled

A new run of a pull request SHALL cancel that pull request's older run still in progress;
a run of any other event (a push to `main`, the schedule, a manual dispatch) MUST never be
cancelled by another run.

#### Scenario: Two pushes to a pull request

- **WHEN** a second push to a pull request starts CI while the first run is in progress
- **THEN** the first run is cancelled and the second one decides `ci-ok`

#### Scenario: Two merges to main in a row

- **WHEN** two pushes to `main` start CI one minute apart
- **THEN** both runs go to their end

### Requirement: CI builds and smoke-tests LADO's image on amd64 and arm64

CI SHALL have a job `container`, one cell per architecture on GitHub's native runners
(`ubuntu-24.04` for amd64, `ubuntu-24.04-arm` for arm64), that builds the web UI's bundle
and the wheel from the run's code, builds `docker/Dockerfile` from that wheel, and runs the
container tests (`tests/container/`, marker `container`) against the image.

#### Scenario: A pull request breaks LADO in the container

- **WHEN** a pull request makes `lado doctor` print a `[FAIL]` in the image
- **THEN** the container job fails on both architectures, and `ci-ok` fails and names it

### Requirement: The container job runs on every CI run and publishes nothing

The job `container` SHALL run on
every CI run, with no condition on the changed files, SHALL publish no image, and `ci-ok`
SHALL need it.

#### Scenario: A pull request of the docs only

- **WHEN** every file a pull request changes is under `docs/`
- **THEN** the smoke is skipped, and the container job still runs

#### Scenario: Nothing is pushed

- **WHEN** the container job runs
- **THEN** it logs in to no registry and pushes no image

### Requirement: A container cell passes only with a pass and no skip

A cell of the job `container` SHALL pass only when pytest exits 0 and its summary has a
pass and no skip, the smoke cell's rule; a failing cell SHALL keep the containers' logs and
LADO's log as an artifact.

#### Scenario: Docker is missing on the runner

- **WHEN** the container tests skip because no `docker` runs
- **THEN** the cell fails
