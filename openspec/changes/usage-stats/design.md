## Context

`state.usage_counts(since)` (LAD-32) counts from `events` and `sessions`: sessions started
or resumed, agents spawned per provider (`state.spawned_provider` parses the `spawned`
detail, `role <r>, provider <p>`), flow runs started, gates opened, turns ended on an
error. Only `telemetry.report` calls it; `telemetry._lado_errors(since)` counts LADO's own
errors in `errors.jsonl` and `.1` (1 MiB each). `state.delete_session` (`lado forget`)
deletes the session's rows, and its events, gates and messages go by `ON DELETE CASCADE`.
LADO already writes rows by trigger: the UI's `changes` journal (`JOURNALED`,
`JOURNAL_WHEN`), whose conditions stay in `lado.db` as they were made.

The facts the human chose to count, and where each is written today:

| Fact | Written by | What the trigger reads |
|---|---|---|
| a session added | `state.add_session` (`INSERT … ON CONFLICT DO NOTHING`) | `NEW.created_at` |
| a resume | event `session_resume` | the event |
| an agent spawned | event `spawned`, detail `role <r>, provider <p>`; from this change `role <r>, kit <k>, provider <p>` (D12) | `<r>@<k>` and the provider from the detail |
| an agent's process ended by itself | event `ended` | `agents.provider` of the agent |
| a turn ended on an error | event `turn_error`, detail `<kind>[: <details>]` (`base.error_line`) | the kind, `agents.provider` |
| a run started, ended, cancelled | events `flow_start`, `flow_end`, `flow_cancel` (run column set) | `runs.flow` and `runs.kit`'s name: `<flow>@<kit>` |
| a gate opened | `gates` insert | `NEW.kind` |
| a gate closed | `gates.answer` set from NULL (an option, `overridden`, `cancelled`) | `NEW.answer`, `NEW.recommended_choice` |
| a question to the human | `messages` insert with `kind = 'question'` | the row |
| a message failed, dropped | `messages.state` becomes `failed`, `dropped` | the row |

Root cause: the counts are derived from rows a forget deletes.

## Options

1. **Count what is left; say forgotten sessions are missing.** No schema change; totals
   fall with every forget. Refused with the human.
2. **Copy the counted rows into a table at forget.** One `INSERT … SELECT` in
   `delete_session`; but forget must know every count, and any other deletion later
   (a cleanup of old events) loses them again. Designed in the first visit, then replaced
   at the human's suggestion.
3. **Chosen with the human: record each counted fact as it happens, by trigger.** One
   anonymous row in `usage` per fact, in the writer's transaction. No code path can forget
   it, forget and any later cleanup leave it, and every count reads one table. Long-term
   cost: a schema step; a trigger stays in `lado.db` as it was made, so a new count, or a
   changed event detail the trigger parses, is a migration of its trigger (the same rule as
   `JOURNAL_WHEN`'s).
4. **Counters incremented in code at each place.** Ten places to keep in step with
   `events`; refused (AGENTS.md, One source of truth).

Held against AGENTS.md's Design principles and ROADMAP: neutral core (the provider is a
column; an error's kind is whatever the provider's `error_line` puts first); one source of
truth (`usage` is written only by triggers on the rows that are the facts, in their
transaction, and is the one thing `lado stats` and the report count); no silent drops
(`lado stats` names its period and the earliest row, and says the error journal is
bounded); only what is used (the human's list, no durations, no per-session view, no
`--json`, no UI). ROADMAP's Stage 7 (desktop app) can serve the same counts through the
API later.

## Decisions

### D1. One table `usage`, no session column

`usage (kind TEXT NOT NULL, key TEXT, provider TEXT, agrees INTEGER, created_at TEXT NOT
NULL)`, in `SCHEMA` and made by `MIGRATIONS[26]` (schema 27). The kinds are constants of
`state.py` (`USAGE_SESSION = "session"`, …) listed in one tuple, `USAGE_KINDS`. No
session, agent, id or detail column: what is forgotten stays forgotten, but its count. Not
journaled (`changes`): the UI shows nothing of it. An index on `created_at`
(`usage_time`): every read is by period.

### D2. Triggers, one per source, in `USAGE_TRIGGERS`

`AFTER INSERT ON sessions`, `AFTER INSERT ON events WHEN NEW.kind IN (...)` (one trigger,
a `CASE` per kind), `AFTER INSERT ON gates`, `AFTER UPDATE OF answer ON gates WHEN
OLD.answer IS NULL AND NEW.answer IS NOT NULL`, `AFTER INSERT ON messages WHEN NEW.kind =
'question'`, `AFTER UPDATE OF state ON messages WHEN NEW.state IN ('failed', 'dropped')
AND OLD.state IS NOT NEW.state`. Named `usage_<source>`, kept in one list next to
`JOURNALED`. Each takes its time from the row (`NEW.created_at`, `NEW.answered_at`;
`strftime('%Y-%m-%d %H:%M:%f', NEW.failed_at, 'unixepoch')` for a failed message; `now`
for a dropped one). The provider of `ended` and `turn_error` is
`(SELECT provider FROM agents WHERE session = NEW.session AND name = NEW.agent)`; the flow
of a run's event `(SELECT flow || '@' || json_extract(kit, '$.name') FROM runs WHERE
session = NEW.session AND name = NEW.run)`. A message that fails, goes back to the queue and fails again counts twice: two
failed hand-overs.

### D3. The `spawned` detail and the error's kind parsed in SQL, pinned by a test

The trigger cuts the role between `role ` and `, kit `, the kit between `, kit ` and `,
provider `, and keys the row `<role>@<kit>`; a detail with no `, kit ` (written before
this change) gives `<role>@?`, the role cut before `, provider `. The provider is the
text after `, provider ` (one with none gets a NULL provider and is still an agent), and an error's kind before
its first `: ` (the whole text when there is none). A unit test runs the same details
through `spawned_detail`/`spawned_provider` and `base.error_line` and through the trigger
and compares them, so a change of either format fails it (and needs a migration, D10).

### D4. The backfill is a callable step of the migration

`usage_from_history(conn)`, after the table and before the triggers in `MIGRATIONS[26]`:
one `INSERT … SELECT` per source by the triggers' rules over the rows there, each with its
own time; a dropped message with its `created_at` (no time of the drop is kept). Every
`spawned` event there predates D12, so its key is `<role>@?`: the role's kit was not
recorded, and guessing it from the session's kits would be wrong where two kits name it
alike. A run's flow is exact: `runs.kit` has always been kept. In the
migration's one transaction.

### D5. `usage_counts` reads `usage`; the report's shape stays

`usage_counts(since)` returns the same dict as before (sessions = `session` + `resume`,
agents per provider, runs = `run_start`, gates = `gate_open`, turn_errors), from `usage`.
`telemetry.report` does not change, nor its fields or `FIELDS_VERSION`.

### D6. `state.usage_summary(since)` and `state.usage_start()`

`usage_summary(since) -> dict[str, Counter]`: per kind, a `collections.Counter` of keys
(with `None` for none), plus per-provider counters for `agent`, `agent_ended` and
`turn_error`, and for `turn_error` per provider and kind; and the agreement (`agrees` 1
and not NULL; NULL also for a gate closed by no answer of the human, `cancelled` or
`overridden`, which counts as closed but never in the agreement). One query, `GROUP BY kind, key, provider, agrees`. `usage_start()`: the
smallest `created_at` of `usage`, cut to seconds, or None.

### D7. `stats.py` builds the lines, `cmd_stats` prints them

`stats.lines(days: int | None, now: datetime | None = None) -> list[str]` (None: all): the
period in UTC, `state.usage_summary` with `since` as `YYYY-MM-DD HH:MM:SS`
(`0000-01-01 00:00:00` for `--all`), `telemetry.lado_errors(telemetry.format_time(since))`,
`state.usage_start`. `cli.py` gets the parser and a short `cmd_stats` only: LAD-33 edits
`cli.py` too. The output, labels padded to one column, a breakdown after the count, a
group with no counts still printed with `0`s:

```
Usage from 2026-09-14 to 2026-10-14 (UTC, 30 days) on this machine; nothing is sent.
Earliest record: 2026-10-01.

Sessions
  started                       8
  resumed                       4
Agents
  started                      41  claude 30, codex 8, kilo 3
  by role                          developer@sdlc 15, supervisor@default 12,
                                   reviewer@sdlc 12, developer@? 2
                                   (@?: kit not recorded, before 0.38.0)
  ended by themselves           2  claude 1, kilo 1
  turns ended on an error       4  claude 3 (overloaded 2, rate_limit 1), kilo 1 (APIError 1)
Flow runs
  started                       9  task@sdlc 7, hotfix@sdlc 2
  ended                         6
  cancelled                     1
Gates and questions
  gates opened                 17  approval 15, choice 1, loop 1
  gates closed                 16  approve 12, reject 3, cancelled 1
  answered as the lead advised 12 of 14 with a recommended choice
  questions to you             23
Messages
  failed to deliver             1
  dropped                       5
LADO
  own errors                    2  (errors.jsonl keeps only its latest part)
```

A breakdown longer than the line wraps under itself; the `@?` note shows only when a
`@?` key is shown. `--all` names the period `Usage of everything kept, to <date> (UTC)` and always prints
`Earliest record: <date>.` or `Earliest record: none yet.`. With no recommended choice in
the period the agreement line says `no recommended choice`.

### D8. `lado stats` does not kick the statistics sender; argparse's options

`stats` joins the commands after which `cli.main` does not call `telemetry.kick()`, so a
command that promises to send nothing starts no sender. It goes through
`runtime.migrate_if_safe` as `lado ls` does. `--days N` (a positive int type, else exit 2)
and `--all` in a mutually exclusive group; neither: 30.

### D9. `telemetry._lado_errors` becomes `telemetry.lado_errors`

One counter of the journal, renamed, not copied.

### D10. A new count or a changed detail is a migration

AGENTS.md (`state.py`, schema 27) says: `usage` is written only by `USAGE_TRIGGERS`; a
new count, or a change of the `spawned` detail or of `base.error_line`'s form, adds a
migration step that drops and makes the trigger again (D3's test fails until then).

### D11. Tests

Unit: `tests/test_usage.py` (each trigger with its row, the anonymity check on every
column, a rollback, forget keeps the rows, D3's comparison (both detail forms), one role
and one flow name in two kits counted apart, the backfill from a schema-26
database built by `previous_schema`), `tests/test_stats.py` (each scenario of the
`lado stats` requirements, the socket and kick checks), `tests/test_telemetry.py` (the
report counts a forgotten session), `tests/test_state.py` (`usage_counts`' shape).
Integration, `tests/integration/test_usage_stats.py`: the counted facts are written by
other processes (hooks, `lado mcp`, the loop), so a fake-agent session started, a worker
spawned, stopped and forgotten through the CLI, with `lado stats --all` before and after
the forget. `tests/agent_helpers.schema_before` undoes step 26 (drop the triggers and the
table).


### D12. A role and a flow are keyed with their kit

Two kits may name a role or a flow alike (`developer` of `sdlc` and of another kit; a
kit's names are unique only within a session), so a key without the kit would add up
different things. A flow's kit is the run's `kit` (`{"name", "version", "source"}`), kept
since runs exist. A role's kit is known only at the spawn (`kits.AgentDef.kit`, the
built-in lead's `default`): `state.spawned_detail(role, kit, provider)` writes
`role <r>, kit <k>, provider <p>`, which `lado log` shows as before with the kit in it.
`state.spawned_provider` still takes the text after `, provider `, so the telemetry
report reads old and new details alike. By kit name, not version: a kit's next version
is the same role. A gate's answer is not qualified: its words (`approve`, `reject`,
`continue`, `cancel`, a choice's outcome) are counted as words.

## Risks

- The migration adds a table, an index, triggers and their rows: no existing row or
  column changes. It runs in one transaction (`state.migrate`; a failure leaves the
  database as it was), only with no session running, and `lado update` backs `lado.db` up
  first (`LADO_HOME/backups/`). An older LADO refuses the migrated database, as for every
  schema step, so a downgrade takes that backup.
- A trigger's extra insert costs microseconds per counted fact (no row per status change
  or message hand-over).
- LAD-33 (in parallel) may also bump the schema: the branch merged second renumbers its
  step and `schema_before`; checked at merge.
- `lado log`'s `spawned` line gains `kit <k>`: the tests that pin it
  (`tests/test_log.py`, `tests/test_runtime.py`, `tests/integration/test_agents.py`)
  change with it.
- `errors.jsonl` keeps about 2 MiB: older errors are not counted; the line says so.
