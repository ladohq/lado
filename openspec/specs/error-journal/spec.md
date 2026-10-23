# error-journal Specification

## Purpose
One local account of LADO's own failures: every unexpected exception of every LADO
process is written to one bounded journal with LADO's version, and LADO's logs stay
bounded in size.

## Requirements

### Requirement: Every LADO process writes its unexpected exceptions to one journal

An unexpected exception in a CLI command, a hook, a tool of `lado mcp`, a pass of the
session loop or a request of the UI server SHALL add one JSON line to
`LADO_HOME/errors.jsonl` with the time, LADO's version, where it happened (`cli:<command>`,
`hook:<event>`, `mcp:<tool>`, `loop`, `server:<route template>`), the exception's type and
message, and its traceback; the session and agent, when known, are kept in that line.

#### Scenario: A hook fails
- **WHEN** a hook of agent `w1` raises a `KeyError` while it handles a turn's end
- **THEN** `errors.jsonl` has one line with `where` `hook:turn_end`, type `KeyError`, the
  traceback, LADO's version and agent `w1`, `hooks.log` has its line as before, and the
  hook exits 0

#### Scenario: A CLI command fails unexpectedly
- **WHEN** `lado ls` raises a `TypeError`
- **THEN** `errors.jsonl` has a line with `where` `cli:ls`, and the command ends with the
  traceback as before

#### Scenario: An MCP tool fails unexpectedly
- **WHEN** `send_message` raises an exception that is not one of LADO's refusals
- **THEN** `errors.jsonl` has a line with `where` `mcp:send_message`, and the agent gets
  the tool's error as before

#### Scenario: The loop's repeated error
- **WHEN** a pass of the session loop fails with the same error five times in a row
- **THEN** `errors.jsonl` gets one line for it, not five

#### Scenario: The loop meets a locked lado.db
- **WHEN** a pass of the session loop, or a read of the UI server's change feed, fails
  with "database is locked"
- **THEN** `errors.jsonl` gets its line only as the requirement "A short lock of lado.db
  is no error of the loop" says

#### Scenario: The UI server fails a request
- **WHEN** `GET /api/sessions/{name}/agents` raises an unexpected exception
- **THEN** `errors.jsonl` has a line with `where` `server:/api/sessions/{name}/agents`
  and the response is 500

### Requirement: The journal's line holds the exception's scrubbed form

The line SHALL also hold the exception's scrubbed form, as `telemetry.scrub` makes it: `chain`
(its causes' types), `stack` (LADO's frames as `lado/<file>:<function>:<line>`, others as
`<external>`), `fingerprint` and `provider` (the agent CLI of a failing hook, else null).

#### Scenario: The line holds the scrubbed form
- **WHEN** a hook of a Claude Code agent raises a `KeyError` in `lado/hooks.py`
- **THEN** its line in `errors.jsonl` has `provider` `claude`, a `stack` whose LADO frames
  read `lado/hooks.py:<function>:<line>`, `chain` and a `fingerprint`, besides its message
  and traceback

### Requirement: A failing scrub still writes the line and queues nothing of it

When `telemetry.scrub` itself raises, the line SHALL still be written, without `chain`,
`stack`, `fingerprint` and `provider` (as LADO 0.37 wrote it), and nothing of that
exception SHALL be queued for sending.

#### Scenario: The scrub fails
- **WHEN** a hook raises a `KeyError` at `hook:turn_end`, sending is on, and
  `telemetry.scrub` raises a `TypeError` for that `KeyError`
- **THEN** `errors.jsonl` has the `KeyError`'s line with its time, version, `where`, type,
  message, traceback, session and agent and without `chain`, `stack`, `fingerprint` and
  `provider`, and a `TypeError` line at `telemetry:scrub` with its scrubbed form; only the
  `TypeError` is queued

### Requirement: A scrub's failure is recorded once as an error of its own

When `telemetry.scrub` itself raises, the scrub's failure SHALL then be recorded as an
error of its own at `where` `telemetry:scrub` (its line with its scrubbed form, queued
while sending is on, except for the sender's own failure, which queues nothing), once: when
scrubbing that failure fails too, its line is written without the scrubbed fields and
nothing more is recorded.

#### Scenario: The scrub fails on its own failure too
- **WHEN** `telemetry.scrub` raises for every exception
- **THEN** `errors.jsonl` gets the error's line and one line at `telemetry:scrub`, neither
  with the scrubbed fields, nothing is queued, and the process goes on as before

### Requirement: The journal is readable by its owner only

The file SHALL be readable by its owner only.

#### Scenario: Another user reads the journal
- **WHEN** an error has been written to `errors.jsonl` and another user of the machine
  reads the file
- **THEN** the read is refused: only the file's owner can read it

### Requirement: Writing the journal never changes how a process handles its exception

Writing the line SHALL never raise: a failure to
write leaves the process's own handling as it was. Each process SHALL go on handling the
exception as before (the CLI's traceback, the hook's exit 0 and `hooks.log` line, the
tool's error, the loop's `loop.log` line, the server's 500).

#### Scenario: The journal cannot be written
- **WHEN** a hook raises an exception and `errors.jsonl` cannot be written
- **THEN** the hook writes its `hooks.log` line and exits 0, as before

### Requirement: LADO's refusals are not written to the journal

LADO's refusals that it prints as
reasons (the CLI's known errors, the errors `lado mcp` passes on to the agent) and
`state.SchemaError` SHALL NOT be written.

#### Scenario: A refusal is no error
- **WHEN** `lado start` is refused because the folder is not a git repository
- **THEN** `errors.jsonl` gets no line

### Requirement: LADO's logs are bounded in size

`errors.jsonl`, `hooks.log` and `loop.log` SHALL each be renamed to `<name>.1`
(replacing an older one) before a write that finds them over 1 MiB, so each keeps at most
its bound plus one rotated file. `server.log` SHALL be renamed to `server.log.1` when the
UI server starts and finds it over the same bound, and, while the server runs, SHALL be
copied to `server.log.1` and emptied in place when it passes the bound (checked at least
every 10 minutes; the server keeps appending to the same file).

#### Scenario: The journal passes its bound
- **WHEN** an error is written while `errors.jsonl` is 1.1 MiB and `errors.jsonl.1` exists
- **THEN** the old `errors.jsonl.1` is gone, the 1.1 MiB file is `errors.jsonl.1`, and
  `errors.jsonl` holds only the new line

#### Scenario: A server that runs for weeks
- **WHEN** a UI server's output makes `server.log` pass 1 MiB while it runs
- **THEN** within 10 minutes its content is `server.log.1`, `server.log` is empty again,
  and the server's next lines go to `server.log`

#### Scenario: The server starts with a large log
- **WHEN** `lado ui` starts a server while `server.log` is 2 MiB
- **THEN** that file is `server.log.1` and the new server writes a new `server.log`

### Requirement: A short lock of lado.db is no error of the loop

A failure of a session loop's pass, or of a read of the UI server's change feed, with
`sqlite3.OperationalError` "database is locked" SHALL be written to `errors.jsonl` only
once that error has kept failing the passes for 60 seconds, as one line for that run of
failures; its log (`loop.log`, `server.log`) SHALL get it as any failing pass.

#### Scenario: A lock that clears within a minute
- **WHEN** the passes of a session's loop fail with "database is locked" for 20 seconds,
  then a pass works
- **THEN** `loop.log` has the error with its traceback and "passes work again", and
  `errors.jsonl` has no line for it

#### Scenario: A lock that lasts
- **WHEN** the passes of a session's loop keep failing with "database is locked" for 60
  seconds and more
- **THEN** `errors.jsonl` gets one line for it, with `where` `loop` and the session, once
  the 60 seconds are over, and no second line while the failures go on

#### Scenario: Another error is written at once
- **WHEN** a pass of the session loop fails with a `RuntimeError`
- **THEN** `errors.jsonl` gets its line at that pass, as before
