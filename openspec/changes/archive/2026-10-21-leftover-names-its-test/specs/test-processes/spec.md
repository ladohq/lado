## MODIFIED Requirements

### Requirement: A test run ends with none of its processes

At its end, each pytest process of the test suite SHALL kill every process still alive
that carries its own `LADO_TEST_PID` (itself left out), and SHALL fail the run, naming
each by pid and command and, when the process carries a `LADO_TEST_ID`, by the node id of
the test that started it.

#### Scenario: A unit test leaves a subprocess
- **WHEN** a test starts a process that is still alive when the run ends
- **THEN** the run kills it and fails, naming the process and the test's node id

#### Scenario: A process started outside a test
- **WHEN** a process without `LADO_TEST_ID` but with the run's `LADO_TEST_PID` is still
  alive when the run ends
- **THEN** the run kills it and fails, naming it by pid and command alone

#### Scenario: A run with workers
- **WHEN** a test run under xdist workers has a test that leaves a process
- **THEN** the controller's report names that process and the test's node id

#### Scenario: A clean run
- **WHEN** every test's processes ended with it
- **THEN** the run's result is the tests' own

## ADDED Requirements

### Requirement: Each test marks the processes it starts

Every pytest process of the test suite SHALL set `LADO_TEST_ID` in its environment to the
node id of the test it runs, from the start of the test's setup to the end of its
teardown, so every process started meanwhile inherits it, and SHALL remove it between
tests.

#### Scenario: A process started in a test's fixture
- **WHEN** a test's setup, call or teardown starts a process
- **THEN** the process carries `LADO_TEST_ID` with that test's node id

#### Scenario: Between tests
- **WHEN** a pytest process has finished a test's teardown and not yet started the next
  test's setup
- **THEN** its environment has no `LADO_TEST_ID`

### Requirement: A fake git's clone that succeeds leaves no process

The fake git of the unit tests (`tests/agent_helpers.py`), in the mode where a clone
succeeds, SHALL end the child process it started and wait for it before it exits 0.

#### Scenario: A clone that succeeds
- **WHEN** a test clones through the fake git in the mode where the clone succeeds
- **THEN** the fake git's logged child is gone once the clone returns, and the run's end
  finds no process of that test
