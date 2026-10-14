## Context

`state.usage_counts(since)` (LAD-32) counts, from `since` on: sessions started
(`sessions.created_at`) or resumed (`session_resume` events), agents spawned per provider
(`spawned` events, provider parsed from the detail by `state.spawned_provider`), flow runs
started (`flow_start`), gates opened (`gate_open`) and turns ended on an error
(`turn_error`). Only `telemetry.report` calls it; `telemetry._lado_errors(since)` counts
LADO's own errors in `errors.jsonl` and `errors.jsonl.1` (bounded at 1 MiB each).
`state.delete_session` (`lado forget`) deletes the session's row, and its events go by
`ON DELETE CASCADE`: every count of the past shrinks with each forget, the report's too.

Root cause: the counts serve the sender alone, and a forget deletes what they count.

## Options

1. **Count what is left; say that forgotten sessions are missing.** No schema change. Cost:
   totals "of all time" fall with every forget, and the telemetry report stays short for a
   session forgotten within its day. Honest, but the number is wrong exactly for the
   people who tidy up.
2. **Chosen with the human: at forget, keep an anonymous copy of the counted records**
   (`forgotten_usage`: kind, provider, time). One table, one `INSERT … SELECT` in the
   forget's transaction, and `usage_counts` reads both tables. Long-term cost: a schema
   step and a few rows per forgotten session; every count of LADO, local and sent, stays
   right after a forget. A new count later must add its kind to the copy (D2's list is
   the one place).
3. **Counters incremented at each event.** A second source of truth that drifts from
   `events` (a missed increment, a rollback); refused (AGENTS.md, One source of truth).

Held against AGENTS.md's Design principles and ROADMAP: nothing depends on a provider
(neutral core: the provider is a column); one source of truth (the live rows, plus the
copy of rows that no longer exist; no row is counted in both, as the copy and the delete
are one transaction); no silent drops (`lado stats` names its period and the earliest
record, and says the error journal is bounded); only what is used (exactly the report's
counts, no `--json`, no UI). ROADMAP's Stage 7 (desktop app) can show the same counts
through the API later without a change here.

## Decisions

### D1. One table `forgotten_usage`, no session column

`forgotten_usage (kind TEXT NOT NULL, provider TEXT, created_at TEXT NOT NULL)`, made in
`SCHEMA` and by migration step 26 (schema 27). `kind` is `session` for a session's start
or the event's kind; `provider` only for `spawned`. No name, id, detail or path: what is
forgotten stays forgotten, but its count. Not journaled (`changes`): the UI shows nothing
of it. No index: a few rows per session.

### D2. The copy is in `state.delete_session`, in its transaction

Before the `DELETE FROM sessions`, in the same `with connect() as db:`, the session's
`created_at` as one `session` row, and its events of the counted kinds
(`USAGE_KINDS = (SESSION_RESUME, SPAWNED, FLOW_START, GATE_OPEN, TURN_ERROR)`, the one
list) with their `created_at`. A `spawned` event's provider is parsed with
`spawned_provider` in Python; one with none is not kept, as `usage_counts` does not count
it either. A failure rolls both back, so a forget run again copies once.

### D3. `usage_counts` counts both tables, same shape

Each count adds the `forgotten_usage` rows of its kind with `created_at >= since`; the
agents per provider add the rows of `spawned`. The returned dict is unchanged, so
`telemetry.report` changes nothing and its fields and `FIELDS_VERSION` stay (no new
question to the human: no new field).

### D4. `state.usage_start()`: the earliest counted record

The smallest `created_at` of `sessions`, of the events of `USAGE_KINDS` and of
`forgotten_usage`, as `YYYY-MM-DD HH:MM:SS` text, or None. `lado stats` prints its date.

### D5. `stats.py` builds the lines, `cmd_stats` prints them

`stats.lines(days: int | None, now: datetime | None = None) -> list[str]` (None: everything
kept): the period in UTC, `state.usage_counts` with `since` as `YYYY-MM-DD HH:MM:SS`
(`0000-01-01 00:00:00` for `--all`), `telemetry.lado_errors` with
`telemetry.format_time(since)`, `state.usage_start`. `cli.py` gets only the parser and a
three-line `cmd_stats`: `cli.py` is shared with LAD-33's change, so its diff stays small.
The output, labels padded to one column:

```
Usage from 2026-09-14 to 2026-10-14 (UTC, 30 days) on this machine; nothing is sent.
Earliest record: 2026-10-01.
  sessions started or resumed   12
  agents spawned                41  (claude 30, codex 8, kilo 3)
  flow runs started              9
  gates opened                  17
  turns ended on an error        4
  LADO's own errors              2  (errors.jsonl keeps only its latest part)
```

The `Earliest record:` line shows with `--all` always (`none yet` without one), else only
when that date is later than the period's start. `--all` names the period
`Usage of everything kept, to <date> (UTC)`. A `0` agents line has no parentheses.

### D6. `telemetry._lado_errors` becomes `telemetry.lado_errors`

One counter of the journal for the report and `lado stats`; renamed, not copied.

### D7. `lado stats` does not kick the statistics sender

`cli.main` kicks `telemetry.kick()` after a human's command; `stats` joins the commands
that do not, so a command that promises to send nothing starts no sender either. It goes
through `runtime.migrate_if_safe` as `lado ls` does: on an older `lado.db` with a session
running it is refused with the usual `lado stop --all`.

### D8. `--days` is argparse's

`--days N` (`type` a positive int, else argparse's error, exit 2) and `--all` in a mutually
exclusive group; neither: 30.

### D9. Tests

Unit (`tests/test_state.py`, `tests/test_stats.py`, `tests/test_telemetry.py`,
`tests/test_cli.py` for the kick) for every requirement; the network check monkeypatches
`socket.socket.connect` and `socket.create_connection` to fail the test. One integration
test (`tests/integration/test_usage_stats.py`): a real session of the fake agent started,
stopped and forgotten through the CLI, with `lado stats --all` before and after the
forget, since the counted events are written by other processes (the loop, hooks).
`tests/agent_helpers.schema_before` undoes step 26 (`DROP TABLE forgotten_usage`).

## Risks

- The migration (schema 26 → 27) only adds an empty table: no existing row or column
  changes. It runs as LADO's 26 steps before it: in one transaction (`state.migrate`, a
  failure leaves the database as it was), only with no session running
  (`runtime.migrate_if_safe`), and `lado update` backs `lado.db` up first
  (`LADO_HOME/backups/`) and rolls back a bad new version. The one cost: an older LADO
  refuses the migrated database (as for every schema step), so a downgrade takes that
  backup.

- LAD-33 (in parallel) may also bump the schema: then the branch merged second renumbers
  its step and `schema_before`; checked at merge.
- `errors.jsonl` keeps at most about 2 MiB: older errors are not counted; the line says
  so.
