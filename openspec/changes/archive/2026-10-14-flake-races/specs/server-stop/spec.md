## ADDED Requirements

### Requirement: A stop returns once the server's process has ended

`server_run.stop` SHALL return only when the UI server's process no longer exists, not
when its lock is free: after SIGTERM it SHALL wait for the lock and then for the
process, both within `STOP_TIMEOUT`, and SHALL reap the process when it is its own
child. When the process is still there at the timeout, it SHALL raise the error it
raises for a server that does not end. Every caller (`lado server stop`, `lado update`,
`lado uninstall`, the UI tests' fixture) SHALL get that wait.

#### Scenario: The server is gone when stop returns
- **WHEN** a UI server started with `lado ui` is stopped with `server_run.stop()`
- **THEN** right after it returns, signal 0 to the server's pid fails with "no such
  process"

#### Scenario: A server of the caller's own
- **WHEN** the caller started the server as its own child process and stops it
- **THEN** `stop()` reaps it and returns, and no zombie of it is left

#### Scenario: A process that outlives its lock
- **WHEN** the server's lock is free but its process does not end within `STOP_TIMEOUT`
- **THEN** `stop()` raises `the LADO server (pid <pid>) did not end in <n>s`

### Requirement: A server's exit writes nothing under LADO_HOME

The command `lado server` SHALL NOT start the statistics sender (`telemetry.kick`) when
it ends: the running server kicks it every `KICK_EVERY`. So a server that ends after
`lado uninstall` deleted `LADO_HOME` SHALL NOT make it again.

#### Scenario: The server ends after an uninstall
- **WHEN** `lado server` ends, its `LADO_HOME` having been deleted meanwhile
- **THEN** `LADO_HOME` does not exist after its process has ended
