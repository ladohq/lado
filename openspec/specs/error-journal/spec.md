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
message, and its traceback; the session and agent, when known, are kept in that line. The
line SHALL also hold the exception's scrubbed form, as `telemetry.scrub` makes it: `chain`
(its causes' types), `stack` (LADO's frames as `lado/<file>:<function>:<line>`, others as
`<external>`), `fingerprint` and `provider` (the agent CLI of a failing hook, else null). The
file SHALL be readable by its owner only. Writing the line SHALL never raise: a failure to
write leaves the process's own handling as it was. LADO's refusals that it prints as
reasons (the CLI's known errors, the errors `lado mcp` passes on to the agent) and
`state.SchemaError` SHALL NOT be written. Each process SHALL go on handling the exception
as before (the CLI's traceback, the hook's exit 0 and `hooks.log` line, the tool's error,
the loop's `loop.log` line, the server's 500).

#### Scenario: A hook fails
- **WHEN** a hook of agent `w1` raises a `KeyError` while it handles a turn's end
- **THEN** `errors.jsonl` has one line with `where` `hook:turn_end`, type `KeyError`, the
  traceback, LADO's version and agent `w1`, `hooks.log` has its line as before, and the
  hook exits 0

#### Scenario: The line holds the scrubbed form
- **WHEN** a hook of a Claude Code agent raises a `KeyError` in `lado/hooks.py`
- **THEN** its line in `errors.jsonl` has `provider` `claude`, a `stack` whose LADO frames
  read `lado/hooks.py:<function>:<line>`, `chain` and a `fingerprint`, besides its message
  and traceback

#### Scenario: A CLI command fails unexpectedly
- **WHEN** `lado ls` raises a `TypeError`
- **THEN** `errors.jsonl` has a line with `where` `cli:ls`, and the command ends with the
  traceback as before

#### Scenario: An MCP tool fails unexpectedly
- **WHEN** `send_message` raises an exception that is not one of LADO's refusals
- **THEN** `errors.jsonl` has a line with `where` `mcp:send_message`, and the agent gets
  the tool's error as before

#### Scenario: A refusal is no error
- **WHEN** `lado start` is refused because the folder is not a git repository
- **THEN** `errors.jsonl` gets no line

#### Scenario: The loop's repeated error
- **WHEN** a pass of the session loop fails with the same error five times in a row
- **THEN** `errors.jsonl` gets one line for it, not five

#### Scenario: The UI server fails a request
- **WHEN** `GET /api/sessions/{name}/agents` raises an unexpected exception
- **THEN** `errors.jsonl` has a line with `where` `server:/api/sessions/{name}/agents`
  and the response is 500

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
