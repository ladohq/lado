# usage-stats Specification

## Purpose
How LADO was used on this machine, kept and shown locally: an anonymous `usage` table in
`lado.db` that triggers fill as things happen and `lado forget` leaves alone, and `lado
stats`, which prints a period's counts from it and LADO's error journal and sends nothing.

## Requirements

### Requirement: Usage is recorded as it happens, anonymously, and outlives its session

`lado.db` SHALL hold a table `usage` with one row per counted fact, written by SQLite
triggers in the transaction that writes the fact, and by no other code; the counted facts
SHALL be only those the requirements "Usage counts …" of this spec name. A row SHALL hold
only its kind, key, provider, agreement and time,
never a session or agent name, a path, a message, a comment or an error's details.
Deleting a session (`lado forget`) SHALL NOT delete or change any row of `usage`.

#### Scenario: Forget keeps the counts
- **WHEN** a stopped session with one resume, two agents, one flow run and two gates is
  forgotten
- **THEN** `usage` has the same rows before and after the forget

#### Scenario: A rolled-back write records nothing
- **WHEN** a transaction that adds an event of a counted kind is rolled back
- **THEN** `usage` has no row of it

### Requirement: Usage counts sessions, agents and turn errors

The counted facts of `usage` SHALL include: a session added
(`session`), a `session_resume` event (`resume`), a `spawned` event (`agent`, key the
role with its kit, with its provider), an `ended` event (`agent_ended`, with the agent's provider), a
`turn_error` event (`turn_error`, key the error's kind: its text before the first `: `,
with the agent's provider).

#### Scenario: A worker's life
- **WHEN** a session is started, a worker of role `developer` of kit `sdlc` on `kilo` is
  spawned, one of its turns ends on the error `overloaded: try later`, and its process
  ends by itself
- **THEN** `usage` has rows `session`, `agent` (`developer@sdlc`, `kilo`, and one for the
  supervisor), `turn_error` (key `overloaded`, `kilo`) and `agent_ended` (`kilo`), and no
  row holds the session's or the agent's name or `try later`

### Requirement: Usage counts gates with the lead's recommendation

The counted facts of `usage` SHALL include: a gate added (`gate_open`,
key its kind), a gate's answer set (`gate_close`, key the answer, and whether it is the
lead's recommended choice, none without one and none for a gate closed by no answer of
the human: `cancelled` with its run, `overridden` by `lado flow-set`).

#### Scenario: A gate answered as the lead recommended
- **WHEN** an approval gate opens, the lead recommends `approve`, and the human approves
- **THEN** `usage` has a `gate_open` row with key `approval` and a `gate_close` row with
  key `approve` that agrees

### Requirement: Usage counts flow runs, questions and failed and dropped messages

The counted facts of `usage` SHALL include: a `flow_start`, `flow_end` or `flow_cancel` event
(`run_start`, `run_end`, `run_cancel`, key the run's flow with its kit), a question added
(`question`), and a
message whose state becomes `failed` (`message_failed`) or `dropped`
(`message_dropped`).

#### Scenario: A run, a question and a failed message
- **WHEN** a run of the flow `task` of kit `sdlc` starts and is cancelled, an agent asks
  the human a question, and a message's state becomes `failed`
- **THEN** `usage` has rows `run_start` and `run_cancel` (key `task@sdlc`), `question`
  and `message_failed`

### Requirement: Usage keys roles and flows with their kit

A role and a flow SHALL be keyed with the kit they come from,
`<role>@<kit>` and `<flow>@<kit>`, since two kits may name a role or a flow alike: the
role's kit is written into the `spawned` event's detail (`role <role>, kit <kit>,
provider <provider>`), the flow's is the run's `kit`.

#### Scenario: One role name in two kits
- **WHEN** one session spawns a `developer` of kit `sdlc` and another a `developer` of kit
  `acme`, and each starts a run of a flow `task` of its kit
- **THEN** `usage` keys them `developer@sdlc`, `developer@acme`, `task@sdlc` and
  `task@acme`, and `lado stats` counts them apart

### Requirement: The migration fills usage from the history kept

The migration to schema 27 SHALL fill `usage` once from the rows `lado.db` holds then, by
the same rules as the triggers and with each fact's own time (a failed message's
`failed_at`; a dropped message, which keeps no time of its drop, its `created_at`; a
`spawned` event written before this change, whose detail names no kit, the key
`<role>@?`), so
that every count of a period before the upgrade is what the rows still kept give.

#### Scenario: An upgrade with history
- **WHEN** a schema-26 `lado.db` holds two sessions with five spawned agents and three
  answered gates, and LADO migrates it
- **THEN** `usage` holds 2 `session`, 5 `agent` and 3 `gate_close` rows with the times of
  their sessions, events and answers

### Requirement: lado stats prints the usage of a period from this machine's records

`lado stats` SHALL print, for a period that ends now, the counts of `usage` in that period
and the count of LADO's own errors in `errors.jsonl` and its `.1`. A count of 0 SHALL be
printed as `0`, and a breakdown
SHALL list its parts by count, the larger first, then by name.

#### Scenario: The default period
- **WHEN** `usage` holds two sessions started 3 and 40 days ago, the first with three
  claude agents and one codex agent, and the human runs `lado stats`
- **THEN** the output names the last 30 days, counts 1 session started and 4 agents
  `claude 3, codex 1`, and exits 0

### Requirement: lado stats counts sessions, agents, turns, runs, questions and messages

The counts of `lado stats` SHALL be: sessions started and
resumed; agents started, per provider and per role; agents ended by themselves, per
provider; turns ended on an error, per provider and per error kind; flow runs started (per
flow), ended and cancelled; roles and flows by
their kit-qualified keys, with a note that `@?` marks a role whose kit was not recorded
when one is shown; questions asked of the
human; messages failed and dropped.

#### Scenario: A role whose kit was not recorded
- **WHEN** `usage` holds in the period an `agent` row keyed `developer@?`
- **THEN** the agents per role list `developer@?`, with a note that `@?` marks a role
  whose kit was not recorded

### Requirement: lado stats counts gates and the agreement with the lead

The counts of `lado stats` SHALL also be: gates opened (per kind), closed (per answer) and how many
closes agreed with the lead of the human's answers that had a recommended choice (a gate
closed by no answer of the human counts as closed, never in the agreement).

#### Scenario: Agreement with the lead
- **WHEN** in the period four gates closed, three with a recommended choice, two of them
  answered as recommended
- **THEN** the output says 2 of 3 agreed with the lead

#### Scenario: A gate closed by no answer of the human
- **WHEN** a gate with the lead's recommended choice is closed because its run was
  cancelled, and another because the human set its run past it with `lado flow-set`
- **THEN** both count among the gates closed (`cancelled 1, overridden 1`) and neither
  counts in the agreement with the lead

### Requirement: lado stats takes its period from its options

The period of `lado stats` SHALL be the
last 30 days by default, the last N days with `--days N` (N a positive whole number), and
everything kept with `--all`; `--days` and `--all` together, or an N that is not a
positive whole number, SHALL exit 2.

#### Scenario: Bad options
- **WHEN** the human runs `lado stats --days 0`, `lado stats --days x` or
  `lado stats --days 7 --all`
- **THEN** it exits 2 with argparse's usage line

### Requirement: lado stats names its period and where its counts come from

The first line of `lado stats` SHALL name the period by its UTC dates
and say that the counts come from this machine and nothing is sent; with `--all`, or when
the earliest row of `usage` is later than the period's start, a line SHALL name that row's
UTC date, or say there is none yet. The errors' line SHALL say that `errors.jsonl` keeps
only its latest part.

#### Scenario: Everything kept
- **WHEN** the human runs `lado stats --all` on the same records
- **THEN** it counts 2 sessions and names the date of the session started 40 days ago as
  the earliest record

#### Scenario: A period longer than the history
- **WHEN** the earliest row is 5 days old and the human runs `lado stats --days 90`
- **THEN** the output names the 90 days and the date of that row

### Requirement: lado stats never goes to the network

`lado stats` SHALL read only `lado.db` and LADO's error journal, SHALL send nothing,
whatever the human's telemetry choice, SHALL open no network connection and SHALL start
no statistics sender.

#### Scenario: Statistics switched on
- **WHEN** the human said yes to sending statistics, a report is due, and the human runs
  `lado stats`
- **THEN** the command opens no socket, starts no `lado telemetry send`, and the
  telemetry outbox and `telemetry/sent.json` are as they were before it
