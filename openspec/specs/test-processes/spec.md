# test-processes Specification

## Purpose
The processes a test run starts end with it: each test's processes are found by its
`LADO_HOME` and swept after its tmux server is killed, a session loop must end by itself
within the same budget, and each pytest process marks what it starts with
`LADO_TEST_PID`, so a run reaps what a dead run left and fails when its own processes
outlive it.

## Requirements

### Requirement: A test's processes end with it

The `isolated` fixtures of the integration, UI, smoke and live tests SHALL, after killing
the test's tmux server, wait up to 10 s for every process whose environment holds the
test's `LADO_HOME` (the pytest process itself left out) to end by itself; each still
alive then SHALL be killed, and the test SHALL fail at its teardown, naming each such
process by pid and command.

#### Scenario: Everything ends by itself
- **WHEN** a test's agents, hooks, `lado mcp` servers and session loop end within the wait
  after its tmux server is killed
- **THEN** the teardown passes, and it takes no longer than they took to end

#### Scenario: An agent outlives its tmux server
- **WHEN** a process with the test's `LADO_HOME` ignores SIGHUP and is still alive 10 s
  after the tmux server was killed
- **THEN** the teardown kills it and the test fails, naming its pid and command

#### Scenario: A process started outside tmux
- **WHEN** a test starts `lado server` and its fixture does not stop it
- **THEN** the teardown kills it and the test fails, naming it

### Requirement: A session loop ends by itself after its tmux session

The integration tests' teardown SHALL check that every session loop of the test ends by
itself within 10 s after the test's tmux server is killed, and SHALL fail the test,
naming the sessions whose loop still runs, when one does not; the check SHALL end as soon
as no loop runs, and no test SHALL be retried inside pytest.

#### Scenario: A loop ends late under load
- **WHEN** the machine is loaded and a session loop ends 3 s after the tmux server was
  killed
- **THEN** the teardown passes

#### Scenario: A loop never ends
- **WHEN** a session loop still runs 10 s after the tmux server was killed
- **THEN** the test fails with "session loops still running 10s after the test" and the
  session's name

### Requirement: A test run reaps what a dead run left

Every pytest process of the test suite SHALL set `LADO_TEST_PID` to its own pid in its
environment, so every process it starts inherits it. At its start, a test run SHALL kill
every process of the user whose `LADO_TEST_PID` names a pid that is not alive, and SHALL
remove the `lado-test-*` sockets of the user's tmux folder that no server answers; it
SHALL NOT touch a process whose `LADO_TEST_PID` names a living pid.

#### Scenario: A run was killed from outside
- **WHEN** an earlier run was killed with SIGKILL and left its tmux server, fake agents
  and session loop alive
- **THEN** the next run kills them at its start, and no `lado-test-*` server of that run
  is left

#### Scenario: Another worktree runs its tests
- **WHEN** a test run starts while another run of the machine is still going
- **THEN** none of that run's processes or tmux servers are touched

### Requirement: A test run ends with none of its processes

At its end, each pytest process of the test suite SHALL kill every process still alive
that carries its own `LADO_TEST_PID` (itself left out), and SHALL fail the run, naming
each by pid and command.

#### Scenario: A unit test leaves a subprocess
- **WHEN** a test starts a process that is still alive when the run ends
- **THEN** the run kills it and fails, naming the process

#### Scenario: A clean run
- **WHEN** every test's processes ended with it
- **THEN** the run's result is the tests' own
