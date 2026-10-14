## ADDED Requirements

### Requirement: CI builds and smoke-tests LADO's image on amd64 and arm64

CI SHALL have a job `container`, one cell per architecture on GitHub's native runners
(`ubuntu-24.04` for amd64, `ubuntu-24.04-arm` for arm64), that builds the web UI's bundle
and the wheel from the run's code, builds `docker/Dockerfile` from that wheel, and runs the
container tests (`tests/container/`, marker `container`) against the image. It SHALL run on
every CI run, with no condition on the changed files, SHALL publish no image, and `ci-ok`
SHALL need it. A cell SHALL pass only when pytest exits 0 and its summary has a pass and no
skip, the smoke cell's rule; a failing cell SHALL keep the containers' logs and LADO's log
as an artifact.

#### Scenario: A pull request breaks LADO in the container

- **WHEN** a pull request makes `lado doctor` print a `[FAIL]` in the image
- **THEN** the container job fails on both architectures, and `ci-ok` fails and names it

#### Scenario: A pull request of the docs only

- **WHEN** every file a pull request changes is under `docs/`
- **THEN** the smoke is skipped, and the container job still runs

#### Scenario: Docker is missing on the runner

- **WHEN** the container tests skip because no `docker` runs
- **THEN** the cell fails

#### Scenario: Nothing is pushed

- **WHEN** the container job runs
- **THEN** it logs in to no registry and pushes no image

## MODIFIED Requirements

### Requirement: The smoke runs where it can concern the change

The smoke jobs SHALL run on every push to `main`, on the daily schedule, on manual
dispatch, and on every pull request except one whose every changed file is under a path
of the skip list: `web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`, `README.md`,
`CHANGELOG.md`, `AGENTS.md`, `BACKLOG.md`, `ROADMAP.md`, `SECURITY.md`,
`.github/dependabot.yml`. The smoke MUST be skipped by a condition on its job, never by
filtering the workflow's triggers. No path of the list MAY be or contain `src/`,
`scripts/`, `tests/` (but `tests/ui/` and `tests/js/`), `docker/`, `pyproject.toml`,
`uv.lock` or `.github/workflows/`.

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

#### Scenario: The list gains a path the smoke runs

- **WHEN** someone adds `scripts/` or `tests/integration/` to the skip list in ci.yml
- **THEN** the unit tests fail

#### Scenario: The list gains the image's folder

- **WHEN** someone adds `docker/` to the skip list in ci.yml
- **THEN** the unit tests fail
