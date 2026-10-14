## ADDED Requirements

### Requirement: lado stats prints the usage of a period from this machine's records

`lado stats` SHALL print, for a period that ends now, the counts that `state.usage_counts`
gives from `lado.db` (sessions started or resumed, agents spawned in all and per agent
CLI, flow runs started, gates opened, turns ended on an error) and the count of LADO's own
errors in `errors.jsonl` and its `.1`, each on a line of its own, a count of 0 printed as
`0`. The period SHALL be the last 30 days by default, the last N days with `--days N`
(N a positive whole number), and everything kept with `--all`; `--days` and `--all`
together, or an N that is not a positive whole number, SHALL exit 2. The first line SHALL
name the period by its UTC dates and say that the counts come from this machine and
nothing is sent; when the earliest record (`state.usage_start`) is later than the period's
start, or with `--all`, a line SHALL name that record's UTC date. The agents' line SHALL
list the agent CLIs by count, the larger first, then by name. The errors' line SHALL say
that `errors.jsonl` keeps only its latest part. With no record at all the counts are `0`
and the line of the earliest record says there is none yet.

#### Scenario: The default period
- **WHEN** `lado.db` holds two sessions started 3 and 40 days ago, the first with three
  claude agents and one codex agent spawned, and the human runs `lado stats`
- **THEN** the output names the last 30 days, counts 1 session, 4 agents `(claude 3,
  codex 1)`, and exits 0

#### Scenario: Everything kept
- **WHEN** the human runs `lado stats --all` on the same records
- **THEN** it counts 2 sessions and names the date of the session started 40 days ago as
  the earliest record

#### Scenario: A period longer than the history
- **WHEN** the earliest record is 5 days old and the human runs `lado stats --days 90`
- **THEN** the output names the 90 days and the date of that record

#### Scenario: Bad options
- **WHEN** the human runs `lado stats --days 0`, `lado stats --days x` or
  `lado stats --days 7 --all`
- **THEN** it exits 2 with argparse's usage line

### Requirement: lado stats never goes to the network

`lado stats` SHALL read only `lado.db` and LADO's error journal, SHALL send nothing,
whatever the human's telemetry choice, and SHALL open no network connection of its own.

#### Scenario: Statistics switched on
- **WHEN** the human said yes to sending statistics and runs `lado stats`
- **THEN** the command opens no socket, and the telemetry outbox and `telemetry/sent.json`
  are as they were before it

### Requirement: A forgotten session's usage is kept anonymously

`lado forget` SHALL, in the transaction that deletes the session's rows, keep one row in
`forgotten_usage` per counted record of the session: its start (`sessions.created_at`),
each `session_resume`, each `spawned` event with its provider, each `flow_start`, each
`gate_open` and each `turn_error` event, with only its kind, the provider (spawned only)
and its time. No session or agent name, path, detail or text SHALL be kept.
`state.usage_counts` and `state.usage_start` SHALL count these rows with the live ones,
so a forget changes no count of any period.

#### Scenario: Forget keeps the counts
- **WHEN** a stopped session with one resume, two spawned agents (claude, kilo), one flow
  run and two gates is forgotten
- **THEN** `state.usage_counts` of a period that holds them gives the same counts before
  and after the forget, and `forgotten_usage` holds 7 rows with no name of the session

#### Scenario: A forget that fails keeps nothing twice
- **WHEN** the delete of the session's rows fails after the copy
- **THEN** the transaction is rolled back, `forgotten_usage` holds none of its rows, and a
  forget run again copies each record once
