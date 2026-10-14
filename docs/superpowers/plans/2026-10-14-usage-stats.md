# Usage stats Implementation Plan

**Goal:** Each counted fact of LADO's work is recorded as it happens in an anonymous local
table that outlives its session; `lado stats` prints its counts of a period and sends
nothing; the telemetry report counts from the same table with the same fields.

**Architecture:** `state.py` gets `usage` (schema 27), filled only by SQLite triggers on
`sessions`, `events`, `gates` and `messages`, and once by the migration from the rows
there. `usage_counts` (the report's) and `usage_summary` (`lado stats`') read it. A new
`stats.py` builds the lines; `cli.py` only parses and prints, and does not kick the
statistics sender after `stats`.

**Tech Stack:** Python 3.10+, SQLite triggers, argparse, pytest (+ xdist).

**Spec:** `openspec/changes/usage-stats/` (proposal, deltas `usage-stats` and
`usage-telemetry`, `design.md` D1-D11) and
`docs/superpowers/specs/2026-10-14-usage-stats-design.md`.

## Global Constraints

- A minor release, 0.38.0: CHANGELOG.md's `## 0.37.1 (unreleased)` becomes
  `## 0.38.0 (unreleased)` (its lines stay).
- No new telemetry field, no change of `telemetry.FIELDS_VERSION` or of the report's
  properties.
- `usage` is written by triggers only: no Python `INSERT INTO usage` outside the
  migration's backfill (a test greps `src/`).
- No row of `usage` holds a session or agent name, a path, a message, a comment or an
  error's details.
- `cli.py` changes only by the parser, `cmd_stats` and the kick's condition (LAD-33 edits
  the same file in parallel).
- One commit per task. Messages in the repo's style: a plain sentence, then `(LAD-34)`.
- Integration tests run with `-m integration`; each exit status read from a log file,
  never through a pipe (`.lado/sdlc.md`, Review traps).
- Edit with the edit tools, not `sed -i` or heredocs.

## Tests per requirement

| Requirement | Tests | Layer |
|---|---|---|
| Usage is recorded as it happens, anonymously, and outlives its session | `tests/test_usage.py`: one test per trigger (session, resume, agent with role and provider, agent_ended, turn_error kind, run start/end/cancel with flow, gate_open kind, gate_close answer and agrees, question, message failed and dropped); every column of every row free of the session's and agents' names and the error's details; a rolled-back transaction leaves no row; `delete_session` leaves `usage` unchanged; D3's comparison with `spawned_detail` and `base.error_line`; the grep for `INSERT INTO usage`; `tests/integration/test_usage_stats.py` | unit, integration |
| The migration fills usage from the history kept | `tests/test_usage.py::test_migration_fills_usage` (a schema-26 database from `previous_schema` with two sessions, five agents, three answered gates, a failed and a dropped message) | unit |
| lado stats prints the usage of a period from this machine's records | `tests/test_stats.py`: the default period, `--all`, `--days 90` with a 5-day history, agreement 2 of 3, breakdown order, zeros and `none yet`, bad options exit 2 (through `cli.main`) | unit |
| lado stats never goes to the network | `tests/test_stats.py::test_stats_opens_no_socket` (`telemetry_on`, a report due, `socket.socket.connect` and `socket.create_connection` patched to fail, outbox and `sent.json` unchanged); `tests/test_cli.py`: `stats` calls no `telemetry.kick` | unit |
| Statistics are counted when sent, never collected (modified) | `tests/test_telemetry.py::test_report_counts_a_forgotten_session`; the report's properties of an existing test unchanged | unit |

End to end: `tests/integration/test_usage_stats.py` (Task 4). Regression run: Task 6.

## Review Focus

- Each trigger's condition: a gate's close only from NULL; a message's state only when it
  changes; a session's add only when the row is new (`ON CONFLICT DO NOTHING` fires no
  insert trigger: a test).
- The SQL parse of the `spawned` detail and of an error's kind against the Python
  formats (D3).
- The backfill and the triggers give the same rows for the same facts (Task 1: one
  history recorded live, then rebuilt by the backfill, compared).
- `usage_counts`' return shape unchanged: `telemetry.report` and `lado telemetry show` as
  before (Task 2).
- `lado stats` starts no sender (Task 3).

---

### Task 1: The table, its triggers and the backfill (D1-D4, D10)

**Files:**
- Modify: `src/lado/state.py` (`SCHEMA_VERSION` 27, `USAGE`, `USAGE_TIME`, the
  `USAGE_*` kinds and `USAGE_KINDS`, `USAGE_TRIGGERS`, `usage_from_history`, `SCHEMA`,
  `MIGRATIONS[26] = [USAGE, USAGE_TIME, usage_from_history, *USAGE_TRIGGERS]`)
- Modify: `tests/agent_helpers.py` (`schema_before`: assert `MIGRATIONS[26]`, undo it by
  dropping the triggers, the index and the table; `SCHEMA_VERSION == 27`)
- Test: `tests/test_usage.py` (new)

**Interfaces:**
- Produces: `state.USAGE_KINDS: tuple[str, ...]`, `state.USAGE_TRIGGERS: list[str]`,
  `state.usage_from_history(conn: sqlite3.Connection) -> None`.

- [ ] **Step 1: Failing tests** in `tests/test_usage.py`, one per trigger and per rule of
  the requirement (see the table above), writing the facts through `state`'s own functions
  (`add_session`, `add_event`, `add_run`/`update_run`, the gate and question functions,
  the message state changes) so the tests see what LADO writes. The anonymity check reads
  every column of every row and asserts no session or agent name and no error details.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_usage.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the table, index and triggers (D2) and the backfill (D4).
  Each trigger's time from its row; the provider and flow by subquery (D2); the role,
  provider and error kind by `substr`/`instr` (D3).
- [ ] **Step 4: Live and backfill agree.** A test records a history live (triggers),
  copies the facts' rows into a fresh schema-26 database (`previous_schema`), migrates it,
  and compares the two `usage` tables (ordered, without times of dropped messages).
- [ ] **Step 5: Run** `uv run pytest tests/test_usage.py tests/test_state.py -n auto` and
  every test that uses `previous_schema` (`grep -rl previous_schema tests`). Expected:
  PASS.
- [ ] **Step 6: Commit** `LADO records each counted fact of its work as it happens (LAD-34)`.

### Task 2: Reading the table; the report counts from it (D5, D6, D9)

**Files:**
- Modify: `src/lado/state.py` (`usage_counts` from `usage`, `usage_summary`,
  `usage_start`), `src/lado/telemetry.py` (`_lado_errors` → `lado_errors`)
- Test: `tests/test_usage.py`, `tests/test_telemetry.py`

- [ ] **Step 1: Failing tests:** `usage_counts` gives the same dict as before for the same
  facts (an existing test of it keeps passing unchanged); `usage_summary`'s counters for
  each kind and the agreement; `usage_start` is None on an empty table and the oldest row
  cut to seconds; `test_report_counts_a_forgotten_session` (two agents, forgotten before
  `report(force=True)`, still counted).
- [ ] **Step 2: Implement.** `usage_summary` is one `GROUP BY kind, key, provider, agrees`
  query; rename `_lado_errors` with its callers and tests.
- [ ] **Step 3: Run** `uv run pytest tests/test_usage.py tests/test_state.py
  tests/test_telemetry.py tests/test_cli_telemetry.py -n auto`. Expected: PASS.
- [ ] **Step 4: Commit** `The telemetry report counts from the usage table (LAD-34)`.

### Task 3: `lado stats` (D7, D8)

**Files:**
- Create: `src/lado/stats.py` (`lines(days: int | None, now: datetime | None = None) -> list[str]`)
- Modify: `src/lado/cli.py` (the `stats` parser with a mutually exclusive `--days N` /
  `--all`, `cmd_stats`, `stats` in the condition of `kicks`, with a comment)
- Test: `tests/test_stats.py` (new), `tests/test_cli.py`

- [ ] **Step 1: Failing tests** for each scenario of the two `lado stats` requirements
  (rows of `usage` written by its triggers through `state`'s functions, with explicit
  times; `now` fixed), the exact output of D7 for one seeded history, and the network and
  kick checks.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_stats.py tests/test_cli.py -k stats`.
  Expected: FAIL.
- [ ] **Step 3: Implement** to the output in `design.md` D7.
- [ ] **Step 4: Run** `uv run pytest tests/test_stats.py tests/test_cli.py
  tests/test_lazy_imports.py -n auto`. Expected: PASS.
- [ ] **Step 5: Commit** `lado stats prints this machine's usage of a period (LAD-34)`.

### Task 4: End to end (integration)

**Files:**
- Create: `tests/integration/test_usage_stats.py`

- [ ] **Step 1: Test.** With the fake agent: `lado start <repo>` (the fake provider, as
  the other integration tests start it), wait until the supervisor is idle, have it spawn a
  worker (its `spawn_worker` command), wait until the worker is idle, `lado stop`, run
  `lado stats --all` as a subprocess and read its Sessions and Agents lines (1 started, 2
  agents with their roles), `lado forget <session>`, run `lado stats --all` again: the
  same lines.
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py > /tmp/lad34-int.log 2>&1; echo $?`.
  Expected: 0.
- [ ] **Step 3: Commit** `An integration test of lado stats across a forget (LAD-34)`.

### Task 5: Docs

- [ ] **Step 1: CHANGELOG.md**: the heading becomes `## 0.38.0 (unreleased)`; add:
  - `lado stats` prints how you used LADO on this machine in the last 30 days (`--days
    N`, `--all`): sessions, agents per agent CLI and role, turn errors, flow runs, gates
    and how often you answered as the lead advised, questions, undelivered messages and
    LADO's own errors. It sends nothing.
  - LADO now keeps an anonymous local record of these counts (no names, paths or texts),
    filled from your existing history at the upgrade, so `lado forget` no longer makes
    them smaller; the statistics report counts from it with the same fields.
- [ ] **Step 2: AGENTS.md**: Layout gets `stats.py`; `state.py`'s schema list gets "From
  schema 27 `usage` …, written only by `USAGE_TRIGGERS` …; a new count or a changed
  `spawned` detail or `base.error_line` form is a migration of its trigger"; the
  `telemetry.py` paragraph says the report counts from `usage`, and its list of commands
  that do not kick gets `stats`; a `lado stats` paragraph after `lado telemetry`'s.
- [ ] **Step 3: docs/telemetry.md**: the paragraph on the counts says they come from a
  local table LADO keeps for `lado stats` also with sending off, so a forgotten session
  is counted (from 0.38.0).
- [ ] **Step 4: Commit** `Docs of lado stats and the usage table (LAD-34)`.

### Task 6: Regression run

- [ ] **Step 1:** `make lint`, `make test`,
  `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py tests/integration/test_telemetry_processes.py`,
  `openspec validate usage-stats --strict`, `openspec validate --specs --strict`; each
  green, its exit status read from a log file.
- [ ] **Step 2:** By hand: copy a real schema-26 `lado.db` into `/tmp/lad34-home`, run
  `LADO_HOME=/tmp/lad34-home uv run lado stats --all`, `lado stats`, `lado stats --days
  7`; quote the output and the time the migration took in the build report.
