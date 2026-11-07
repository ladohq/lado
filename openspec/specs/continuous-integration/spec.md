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

### Requirement: A smoke cell retries an install whose CLI does not run

A smoke cell (`scripts/smoke_ci.py run <provider> <out>`) SHALL install its provider's
CLI in up to three attempts, an attempt being `npm install` of the pinned package and then
the CLI's `--version`, which succeeds only when both exit 0. After a failed attempt but
the last it SHALL print a GitHub warning annotation naming the provider and the attempt,
uninstall the package and try again. After the third failed attempt the cell SHALL fail
and run no test.

#### Scenario: npm dropped the CLI's binary once
- **WHEN** the first install exits 0 but the CLI's `--version` fails, and the second
  attempt works
- **THEN** the cell runs its smoke tests, and its log has one `::warning::` line for
  attempt 1 of 3 and one uninstall before the second install

#### Scenario: The install fails once
- **WHEN** the first `npm install` exits non-zero and the second attempt works
- **THEN** the cell runs its smoke tests after one warning and one uninstall

#### Scenario: The CLI never runs
- **WHEN** the CLI's `--version` fails after each of three installs
- **THEN** the cell fails with `<cli> --version failed after the install` and runs no
  test

#### Scenario: The install works at once
- **WHEN** the first attempt works
- **THEN** the cell installs once, uninstalls nothing and prints no warning

### Requirement: A run whose jobs got no runner is rerun once

When a CI run completes with `failure` on its first attempt, the workflow
`.github/workflows/ci-rerun.yml` SHALL rerun the run's failed jobs once if and only if
every job that did not succeed, `ci-ok` aside, was cancelled without a runner with
GitHub's annotation "was not acquired by Runner", and no newer CI run of the same pull
request exists; it SHALL print why it reruns or does not.

#### Scenario: A macOS cell got no runner on main

- **WHEN** a push to `main` ends with the smoke cell `smoke macos-latest opencode`
  cancelled with no step, no runner and the annotation "was not acquired by Runner", every
  other job but `ci-ok` succeeded
- **THEN** the run's failed jobs are rerun once and the run's second attempt decides
  `ci-ok`

#### Scenario: A real failure beside a runner-less cell

- **WHEN** a run has a cell cancelled without a runner and a unit job that failed
- **THEN** nothing is rerun

#### Scenario: The second attempt fails the same way

- **WHEN** the rerun attempt again has a cell that got no runner
- **THEN** nothing is rerun; the run stays red for the Review trap's manual reruns

#### Scenario: A superseded run

- **WHEN** a pull request's run was cancelled because a newer push started a new run
- **THEN** nothing is rerun

#### Scenario: A newer run of the same pull request

- **WHEN** a pull request's run failed only by a runner-less cell, and a newer CI run of
  that pull request exists
- **THEN** nothing is rerun, so the newer run is not cancelled by the old one's rerun

### Requirement: The rerun workflow runs no code of the pull request

The workflow `.github/workflows/ci-rerun.yml` MUST NOT check out or run a pull request's
code, and SHALL hold no permission beyond `actions: write`, `checks: read` and
`contents: read`.

#### Scenario: A pull request changes the rerun script

- **WHEN** a pull request changes `scripts/ci_rerun.py` and its CI run fails
- **THEN** the rerun workflow runs the script of `main`, not the pull request's

### Requirement: Live tests run weekly and by hand outside ci-ok

The workflow `.github/workflows/live.yml` SHALL run the live tests on a weekly schedule and on
manual dispatch, a cell per provider of LADO, each with its model, on Linux, and on no other
event. It MUST NOT be part of `.github/workflows/ci.yml`, so that `ci-ok` never depends on it,
and two of its runs MUST NOT run at once.

#### Scenario: The weekly run

- **WHEN** the schedule starts the workflow on `main`
- **THEN** each cell runs its provider's live tests against its cloud model

#### Scenario: A red live run does not block a merge

- **WHEN** a cell of the live workflow fails
- **THEN** `ci-ok` of every pull request is unchanged, and GitHub mails the run's failure

#### Scenario: A provider without a cell

- **WHEN** LADO gains a provider and `live.yml`'s matrix lacks it
- **THEN** the unit tests fail

#### Scenario: A trigger is added

- **WHEN** `live.yml` gains a `pull_request`, `pull_request_target` or `push` trigger
- **THEN** the unit tests fail

#### Scenario: A second run while one is going

- **WHEN** the workflow is dispatched while its scheduled run is in progress
- **THEN** the second waits, and neither is cancelled

### Requirement: The live key reaches only main and tags

The key of the live tests SHALL be a secret of the GitHub environment `live`, whose deployment
rule admits only the branch `main` and tags `v*`, and only the live workflow's cell job MAY name
that environment. The key MUST reach only the step that runs the tests; the job's token SHALL
hold no permission beyond `contents: read`, and the checkout MUST keep no credentials.

#### Scenario: A dispatch on another branch

- **WHEN** someone dispatches the live workflow on a branch other than `main`
- **THEN** GitHub refuses the environment and the job gets no key

#### Scenario: A pull request changes the workflow

- **WHEN** a pull request adds a trigger to `live.yml` or names the secret in `ci.yml`
- **THEN** the unit tests fail, and a run of the pull request's ref gets no secret of `live`

### Requirement: A live cell passes only with a pass and no skip

A live cell (`scripts/smoke_ci.py live <provider> <out>`) SHALL install its provider's CLI at
its pin as a smoke cell does, run that provider's live tests without
`tests/live/test_codex_login.py`, and pass only when pytest exits 0 and its summary has a pass
and no skip.

#### Scenario: The key is missing

- **WHEN** the environment gives no key and the live tests skip
- **THEN** the cell fails

#### Scenario: The image test skips

- **WHEN** `LADO_LIVE_IMAGE` is unset and the image test skips
- **THEN** the cell fails

### Requirement: What a live cell uploads holds no key

A live cell SHALL write everything outside its output folder while the tests run, and only then
replace the value of `LADO_LIVE_API_KEY` in every file by `<redacted>` and move the files into
the output folder; the output folder MUST hold no file before that replacement. The workflow
SHALL upload the output folder whether the cell passed or not.

#### Scenario: An agent printed its environment

- **WHEN** a failed test's evidence and the pytest log hold the key's value
- **THEN** the uploaded folder holds `<redacted>` in its place

#### Scenario: A window wrapped the key

- **WHEN** an agent's screen or the pytest log holds the key's value with spaces, line ends or a
  CLI's frame between its characters
- **THEN** the uploaded folder and the job's log hold `<redacted>` in its place

#### Scenario: Evidence with a dangling link

- **WHEN** a red cell's evidence holds a link to a file that does not exist
- **THEN** the cell's log and the rest of the evidence are uploaded

#### Scenario: The job is killed during the tests

- **WHEN** the job reaches its timeout, or the script crashes, while pytest runs
- **THEN** the output folder is empty, and the upload sends nothing

#### Scenario: The tests hang

- **WHEN** pytest is still running after the cell's own limit, shorter than the job's timeout
- **THEN** pytest is ended, the cell is red, and its redacted log and the evidence of the tests
  that ended before it are uploaded

### Requirement: Every provider's live tests run only on a remote endpoint

Each provider's live tests SHALL reach their model only at `LADO_LIVE_ENDPOINT`, which MUST have
no default value, with `LADO_LIVE_API_KEY` and `LADO_LIVE_MODEL` (or the CLI's own model variable),
set up by that provider's one entry in `tests/live_models.py`. Without any of them each test SHALL
skip and name what to set. No live test but `tests/live/test_codex_login.py` SHALL use a person's
login or config, and none SHALL start or look for LM Studio or a LiteLLM proxy.

#### Scenario: No endpoint on a developer's machine

- **WHEN** `make test-live PROVIDER=kilo` runs with no `LADO_LIVE_ENDPOINT`
- **THEN** the tests skip with a reason naming the three variables

#### Scenario: An endpoint without its key

- **WHEN** `LADO_LIVE_ENDPOINT` is set and `LADO_LIVE_API_KEY` is not
- **THEN** the tests skip with a reason naming the key's variable

#### Scenario: Claude Code on the endpoint

- **WHEN** Claude Code's live test starts with `LADO_LIVE_ENDPOINT` ending in `/v1`
- **THEN** it has `ANTHROPIC_BASE_URL` without the `/v1`, the key as `ANTHROPIC_AUTH_TOKEN`, a
  `CLAUDE_CONFIG_DIR` of the test and no other login variable

#### Scenario: A person's subscription is logged in

- **WHEN** the machine's Claude Code is logged in and no endpoint is set
- **THEN** Claude Code's live tests skip, and they do not use that login

#### Scenario: The agents ran on another model

- **WHEN** a Claude Code agent's transcript names a model other than the test's
- **THEN** the test fails

### Requirement: A release candidate's live check is the live workflow

The release's live step SHALL be a run of the live workflow with every cell green whose head commit
is the release candidate's; a `make test-live` without the endpoint's variables MUST NOT count as
that check.

#### Scenario: The live step of a release candidate

- **WHEN** the commit `Release candidate X.Y.ZrcN` is on `main`
- **THEN** `gh workflow run live.yml` runs before the tag is pushed, `gh run list --workflow
  live.yml` shows that commit's SHA on the run, and a red cell is rerun by the flaky rule of the
  checks

#### Scenario: A run of another commit

- **WHEN** the last green run's SHA is not the release candidate's
- **THEN** the step is not done
