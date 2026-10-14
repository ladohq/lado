Task: LAD-34

## Why

The human cannot see how they use LADO: how many sessions they ran, which agent CLIs they
started, how many flow runs and gates they went through, how often turns ended on an
error. All of it is in `lado.db` already (the daily telemetry report of LAD-32 counts it
with `state.usage_counts`), but only the maintainers' report reads it, and only with the
human's yes to sending.

Root cause: the counts exist as a function of the telemetry sender alone, with no command
that shows them locally; and `lado forget` deletes a session's rows, so every count of the
past, the telemetry report's too, silently shrinks with each forget.

## What Changes

- **`lado stats`**: a new command that prints the usage counts of a period, read from
  `lado.db` and `errors.jsonl` on this machine. It sends nothing and never goes to the
  network. The period is the last 30 days by default, `--days N` for another number of
  days, `--all` for everything kept. The counts are exactly the daily report's:
  sessions started or resumed, agents spawned (in all and per agent CLI), flow runs
  started, gates opened, turns ended on an error, and LADO's own errors (with a note that
  `errors.jsonl` keeps only its latest part). The header names the period (UTC dates) and,
  when the earliest record is later than the period's start, that date.
- **A forgotten session is still counted.** `lado forget` keeps, in the same transaction
  as the delete, one anonymous row per counted event of the session (its start, each
  resume, each spawned agent with its provider, each flow run started, each gate opened,
  each turn error): only the kind, the provider and the time, never a name, path or
  text. `state.usage_counts` adds them, so `lado stats` and the telemetry report count
  the same, also after a forget. Sessions forgotten before this LADO stay uncounted.
- Schema 27: the table `forgotten_usage`.
- Docs: AGENTS.md (`stats.py`, `state.py`'s schema 27, the `lado stats` paragraph, the
  forget paragraph), docs/telemetry.md (a forgotten session is counted), CHANGELOG.md.
- A minor release (a CLI command and a schema migration): 0.38.0.

## Scope

- `src/lado/state.py`: the table, the migration, the copy in `delete_session`,
  `usage_counts` reading both tables, `usage_start` (the earliest record).
- `src/lado/stats.py` (new): the period and the lines `lado stats` prints.
- `src/lado/telemetry.py`: `_lado_errors` becomes public (`lado_errors`), no other change.
- `src/lado/cli.py`: the `stats` parser and `cmd_stats`, which only prints.
- Tests: `tests/test_state.py`, `tests/test_stats.py` (new), `tests/test_telemetry.py`,
  `tests/agent_helpers.py`, one integration test.

## Out of scope

- **A view in the UI**: it needs its own mock-up and screen design, and session lad-33
  changes the UI at the same time (LAD-33); a later task can serve the same counts.
- **`--json`**: no reader of it yet (Only what is used).
- **Counts per session, kit or flow, or new metrics** (messages, run outcomes, time spent):
  the human chose exactly the report's counts; a new count is a new task, and for the
  report a new field with the consent's re-ask.
- **Counts kept by a counter that each event increments**: a second source of truth that
  can drift from `events`; refused with the human.
- **Sessions forgotten before this LADO**: their rows are gone and cannot come back.
- **A bound on `forgotten_usage`**: a few rows per session (a heavy year is some thousand
  rows of three short columns); `lado uninstall` deletes it with `LADO_HOME`.

## Impact

- CLI: a new command `lado stats [--days N | --all]`.
- Schema: version 27 (`forgotten_usage`), a migration as usual (`lado stop --all` first
  when a session runs).
- Telemetry: the report's fields and `FIELDS_VERSION` stay; its counts include forgotten
  sessions from now on. No new question to the human.
- Parallel work: LAD-33 changes `cli.py`, CHANGELOG.md and AGENTS.md too; only textual
  conflicts are expected, resolved at merge by the branch merged second.
