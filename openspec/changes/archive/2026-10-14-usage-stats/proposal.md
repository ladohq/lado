Task: LAD-34

## Why

The human cannot see how they use LADO: how many sessions and agents they ran, on which
agent CLIs, how their flow runs and gates went, how often LADO asked them something, and
how reliable each CLI was. Most of it is in `lado.db` already, but only the telemetry
sender counts a part of it (`state.usage_counts`), and only for the maintainers.

Root cause: the counts are derived from rows that do not last. `lado forget` deletes a
session's events, gates and messages, so every count of the past, the telemetry report's
too, shrinks with each forget; and no command shows the counts locally.

## What Changes

- **A local usage table, `usage`, filled as things happen.** SQLite triggers on
  `sessions`, `agents`' events, `gates` and `messages` add one anonymous row per counted
  fact, in the transaction that writes it: its kind, a short key (a role, a flow, a gate
  kind or answer, an error's kind; a role or a flow with its kit, `developer@sdlc`, as two
kits may name them alike), the agent CLI where there is one, whether the human
  agreed with the lead's recommendation, and the time. Never a session or agent name, a
  path, a message, a comment or an error's text. No other code path writes it, `lado
  forget` leaves it alone, so the counts survive any deletion of a session.
- **Backfilled once**: the migration fills `usage` from what `lado.db` holds at that
  moment, so the history starts with the oldest session still kept, not with the upgrade.
  Sessions forgotten before it are gone.
- **`lado stats [--days N | --all]`** prints the counts of a period (the last 30 days by
  default) from `usage` and LADO's error journal on this machine. It sends nothing and
  starts no sender. The counts, chosen with the human:
  - sessions started, resumed;
  - agents started, per agent CLI and per role (`<role>@<kit>`); agents whose process ended by itself, per
    CLI; turns that ended on an error, per CLI and per error kind;
  - flow runs started (per flow, `<flow>@<kit>`), ended, cancelled;
  - gates opened (per kind), closed (per answer), and how often the human's answer was the
    lead's recommended one; questions agents asked the human;
  - messages that failed to be delivered, messages dropped;
  - LADO's own errors (`errors.jsonl`, which keeps only its latest part).
- **The `spawned` event names the role's kit**: `role <r>, kit <k>, provider <p>`
  (`lado log` shows it). Agents spawned before the upgrade are keyed `<role>@?`: their
  kit was not recorded.
- **The telemetry report keeps its fields** (`FIELDS_VERSION` unchanged, no new question
  to the human); `state.usage_counts` counts its numbers from `usage`, so a forgotten
  session stays counted there too.
- Schema 27: the table, its triggers and the backfill.
- Docs: AGENTS.md (`stats.py`, `state.py`'s schema 27 and the rule that a new count or a
  changed event detail needs a migration of the triggers, `lado stats`), docs/telemetry.md
  (the local table, kept also with sending off; the report counts from it), CHANGELOG.md.
- A minor release (a CLI command and a schema migration): 0.38.0.

## Scope

- `src/lado/state.py`: `USAGE`, its triggers, `MIGRATIONS[26]` with the backfill,
  `usage_counts` from `usage`, `usage_summary`, `usage_start`.
- `src/lado/runtime.py`: `_add_agent` passes the role's kit to `state.spawned_detail`.
- `src/lado/stats.py` (new): the period and the lines `lado stats` prints.
- `src/lado/telemetry.py`: `_lado_errors` becomes `lado_errors`; the report unchanged.
- `src/lado/cli.py`: the `stats` parser and `cmd_stats`, and no kick after `stats`.
- Tests: `tests/test_state.py`, `tests/test_usage.py` (new: the triggers and the
  backfill), `tests/test_stats.py` (new), `tests/test_telemetry.py`, `tests/test_cli.py`,
  `tests/agent_helpers.py`, one integration test.

## Out of scope

- **Durations** (how long sessions ran, agents were busy, runs took, agents waited for
  the human): they need totals computed at a session's stop or forget, a second
  mechanism with edge cases of its own (a session that crashed, a wait across a pause).
  A next task, once the counters work.
- **Rework** (a run that comes back to a state it passed): no exact definition yet.
- **The human's own messages, automatic resumes after a transient error, repository
  changes by read-only agents**: little use, by the human's choice.
- **Counts per session** (`lado stats <session>`): not needed, by the human's choice;
  `usage` keeps no session.
- **New fields in the telemetry report**: each needs the consent's question again; a
  separate decision.
- **A view in the UI, `--json`**: no reader yet; LAD-33 changes the UI at the same time.
- **Tokens, cost, models, lines of code, merged pull requests**: LADO does not know them
  without provider-specific work.
- **A bound on `usage`**: a few rows per session and agent (no row per turn), some
  thousand a year; `lado uninstall` deletes it with `LADO_HOME`.

## Impact

- CLI: a new command `lado stats [--days N | --all]`.
- Schema: version 27 (`usage`, its triggers, the backfill), a migration as usual
  (`lado stop --all` first when a session runs; `lado update` backs `lado.db` up).
- Telemetry: the same fields and question; its counts come from `usage`.
- Parallel work: LAD-33 changes `cli.py`, CHANGELOG.md and AGENTS.md too; only textual
  conflicts are expected. If it also bumps the schema, the branch merged second
  renumbers its step.
