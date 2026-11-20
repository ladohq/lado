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

### Requirement: A container test run stopped from outside removes what it made

A run of the container tests SHALL treat SIGTERM and SIGHUP as Ctrl-C: the run stops, and
each test's finalizers remove the containers, volumes, compose projects and image tags it
made before the process ends.

#### Scenario: A tool's timeout ends the run
- **WHEN** a container test run gets SIGTERM while a test's container runs
- **THEN** the run ends interrupted, and no container, volume, network or image tag of
  its prefix is left in Docker

### Requirement: A container test run reaps what a dead container run left

While it lives, a run of the container tests SHALL hold an exclusive lock of a file named
by its prefix in a folder of the user's shared by every checkout. At its start it SHALL
remove the containers, volumes, networks and image tags of each prefix whose lock file no
process holds, then that file, and SHALL NOT touch a prefix whose lock is held.

#### Scenario: A run was killed with SIGKILL
- **WHEN** an earlier container run was killed with SIGKILL and left a running container,
  its home volume and a compose network of its prefix
- **THEN** the next container run removes them at its start, and its lock file

#### Scenario: Another worktree runs its container tests
- **WHEN** a container run starts while another run of the machine is still going
- **THEN** none of that run's containers, volumes, networks or tags are touched

### Requirement: A container test run names leftovers of no known run

At its start a run of the container tests SHALL warn, naming each `lado-test-*`
container, volume, network and image tag whose prefix has no lock file, with one command
that removes them all, and SHALL NOT remove them.

#### Scenario: Leftovers of a run before the lock
- **WHEN** Docker holds `lado-test-*` containers and volumes whose prefix has no lock file
- **THEN** the run's start warns with their names and the command that removes them, the
  tests run, and the leftovers are still there

### Requirement: A container test run ends with nothing of its prefix

At its end, a run of the container tests SHALL fail when Docker still holds a container,
volume, network or image tag of its own prefix, naming each.

#### Scenario: A compose network is left
- **WHEN** a test's compose project leaves its network `<project>_default` behind
- **THEN** the run's end fails, naming that network
