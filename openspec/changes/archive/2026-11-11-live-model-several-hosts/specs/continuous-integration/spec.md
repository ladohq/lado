## MODIFIED Requirements

### Requirement: Live tests run weekly and by hand outside ci-ok

The workflow `.github/workflows/live.yml` SHALL run the live tests on a weekly schedule and on
manual dispatch, a cell per provider of LADO, each with its model, on Linux, and on no other
event. A cell's model MUST be served on OpenRouter by more than one host and declare tools and
images. The workflow MUST NOT be part of `.github/workflows/ci.yml`, so that `ci-ok` never depends on it,
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

#### Scenario: A model with one host

- **WHEN** a cell's model is chosen and OpenRouter serves a candidate from one host only
- **THEN** that candidate is not taken, however cheap, as its host's quota can fail every run
