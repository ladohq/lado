## ADDED Requirements

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
