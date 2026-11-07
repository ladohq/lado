## ADDED Requirements

### Requirement: Live tests run weekly and by hand outside ci-ok

The workflow `.github/workflows/live.yml` SHALL run the live tests on a weekly schedule and on
manual dispatch, a cell per provider of Codex, OpenCode and Kilo on Linux, and on no other
event. It MUST NOT be part of `.github/workflows/ci.yml`, so that `ci-ok` never depends on it,
and two of its runs MUST NOT run at once.

#### Scenario: The weekly run

- **WHEN** the schedule starts the workflow on `main`
- **THEN** each of the three cells runs its provider's live tests against the cloud model

#### Scenario: A red live run does not block a merge

- **WHEN** a cell of the live workflow fails
- **THEN** `ci-ok` of every pull request is unchanged, and GitHub mails the run's failure

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

#### Scenario: The job is killed during the tests

- **WHEN** the job reaches its timeout, or the script crashes, while pytest runs
- **THEN** the output folder is empty, and the upload sends nothing

#### Scenario: The tests hang

- **WHEN** pytest is still running after the cell's own limit, shorter than the job's timeout
- **THEN** pytest is ended, the cell is red, and its redacted log and evidence are uploaded

### Requirement: The live tests of Codex, OpenCode and Kilo run only on a remote endpoint

Codex, OpenCode and Kilo's live tests SHALL reach their model only at `LADO_LIVE_ENDPOINT`, which
MUST have no default value, with `LADO_LIVE_API_KEY` and `LADO_LIVE_MODEL` (or the CLI's own
model variable). Without any of them each of these tests SHALL skip and name what to set. No
live test SHALL start or look for LM Studio or a LiteLLM proxy.

#### Scenario: No endpoint on a developer's machine

- **WHEN** `make test-live PROVIDER=kilo` runs with no `LADO_LIVE_ENDPOINT`
- **THEN** the tests skip with a reason naming the three variables

#### Scenario: An endpoint without its key

- **WHEN** `LADO_LIVE_ENDPOINT` is set and `LADO_LIVE_API_KEY` is not
- **THEN** the tests skip with a reason naming the key's variable

#### Scenario: Claude Code

- **WHEN** Claude Code's live test runs with no endpoint
- **THEN** it runs as before, on its own login

### Requirement: A release candidate's live check is the live workflow

The release's live step SHALL be a run of the live workflow on the release candidate's commit
with all three cells green, and Claude Code's live test run locally with the human's yes; a
`make test-live` without the endpoint's variables MUST NOT count as that check.

#### Scenario: The live step of a release candidate

- **WHEN** the commit `Release candidate X.Y.ZrcN` is on `main`
- **THEN** `gh workflow run live.yml` runs on it before the tag is pushed, and a red cell is rerun
  by the flaky rule of the checks
