## ADDED Requirements

### Requirement: A hung UI test fails and names itself

Each UI test (marker `ui`, under `tests/ui/`) SHALL have a time limit of 120 s, its
fixtures included, set in one place for `make test-ui` and CI alike; a test past it MUST
fail, named, with its process's thread stacks in the log, while the run goes on. The
pytest step of a CI job `ui` SHALL have a `timeout-minutes` under its job's, so a hang
outside a test ends the step with its log and the junit upload kept.

#### Scenario: A UI test hangs in CI on its page

- **WHEN** a UI test of shard 1 waits forever inside Playwright
- **THEN** after 120 s it fails, the shard's other tests run, the job's log and its junit
  report name that test, and the log holds the stacks of its process's threads
  (Playwright's event loop, not the test's line)

#### Scenario: A UI test hangs in plain Python

- **WHEN** a UI test waits forever outside Playwright (a sleep, a process)
- **THEN** it fails the same way, and the stacks in the log show the test's line

#### Scenario: The pytest step hangs outside a test

- **WHEN** the pytest step of `ui (2)` hangs outside any test
- **THEN** the step ends red after 12 minutes, its log is kept, and the junit upload runs

#### Scenario: A UI test without the limit

- **WHEN** a test under `tests/ui/` is collected without the time limit
- **THEN** the unit tests fail

#### Scenario: The step's limit goes

- **WHEN** the pytest step of the job `ui` has no `timeout-minutes`, or one not under the
  job's
- **THEN** the unit tests fail
