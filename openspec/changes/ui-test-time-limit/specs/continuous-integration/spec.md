## ADDED Requirements

### Requirement: A hung UI test fails and names itself

Each UI test (marker `ui`, under `tests/ui/`) SHALL have a time limit of 120 s, its
fixtures' setup and teardown included, set in one place for `make test-ui` and CI alike;
a test past it MUST fail with the stack of where it waited while the run goes on. The
pytest step of a CI job `ui` SHALL have a `timeout-minutes` under its job's, so a hang
outside a test ends the step with its log and the junit upload kept.

#### Scenario: A UI test hangs in CI

- **WHEN** a UI test of shard 1 waits forever on its page
- **THEN** after 120 s it fails with a traceback of where it waited, the shard's other
  tests run, and the job's log and its junit report name that test

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
