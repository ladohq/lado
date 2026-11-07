## ADDED Requirements

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
