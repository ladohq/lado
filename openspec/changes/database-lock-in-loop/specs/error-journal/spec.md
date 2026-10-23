## MODIFIED Requirements

### Requirement: Every LADO process writes its unexpected exceptions to one journal

An unexpected exception in a CLI command, a hook, a tool of `lado mcp`, a pass of the
session loop or a request of the UI server SHALL add one JSON line to
`LADO_HOME/errors.jsonl` with the time, LADO's version, where it happened (`cli:<command>`,
`hook:<event>`, `mcp:<tool>`, `loop`, `server:<route template>`), the exception's type and
message, and its traceback; the session and agent, when known, are kept in that line. A
pass of the session loop, or a read of the UI server's change feed, that fails on a locked
lado.db is written only as the requirement "A short lock of lado.db is no error of the
loop" says.

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

#### Scenario: The UI server fails a request
- **WHEN** `GET /api/sessions/{name}/agents` raises an unexpected exception
- **THEN** `errors.jsonl` has a line with `where` `server:/api/sessions/{name}/agents`
  and the response is 500

## ADDED Requirements

### Requirement: A short lock of lado.db is no error of the loop

When a pass of the session loop, or a read of the UI server's change feed, fails with
`sqlite3.OperationalError` "database is locked", the failure SHALL be written to its log
(`loop.log`, `server.log`) as any failing pass is, and SHALL be written to `errors.jsonl`
(and queued for telemetry while sending is on) only when that same error has kept failing
the passes for 60 seconds since the first of them: one line for that run of failures. A
lock that clears sooner SHALL leave `errors.jsonl` as it was.

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
