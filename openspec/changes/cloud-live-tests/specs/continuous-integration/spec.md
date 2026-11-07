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

Before a live cell ends, it SHALL replace the value of `LADO_LIVE_API_KEY` in every file under
its output folder, the pytest log and the evidence included, by `<redacted>`; the workflow
SHALL upload that folder whether the cell passed or not.

#### Scenario: An agent printed its environment

- **WHEN** a failed test's evidence and the pytest log hold the key's value
- **THEN** the uploaded folder holds `<redacted>` in its place

### Requirement: Codex can reach a remote endpoint through the bridge

With `LADO_LIVE_ENDPOINT` and `LADO_LIVE_CODEX_BRIDGE=1` set, the live tests SHALL start the
LiteLLM bridge with that endpoint as its upstream and point Codex at the bridge; the bridge's
config MUST name the upstream's key only by reference to `LADO_LIVE_API_KEY`. Without
`LADO_LIVE_CODEX_BRIDGE`, Codex SHALL reach the endpoint directly, as before.

#### Scenario: The bridge's config

- **WHEN** the bridge starts for a remote endpoint
- **THEN** its config file holds the endpoint's base URL and `os.environ/LADO_LIVE_API_KEY`, and
  not the key's value

#### Scenario: LM Studio's bridge

- **WHEN** no endpoint is set
- **THEN** the bridge's upstream is LM Studio's `/v1` with no key, as before

#### Scenario: Without the setting

- **WHEN** an endpoint is set and `LADO_LIVE_CODEX_BRIDGE` is not
- **THEN** Codex's config names the endpoint and no bridge starts
