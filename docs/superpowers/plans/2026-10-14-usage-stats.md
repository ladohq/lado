# Usage stats Implementation Plan

**Goal:** `lado stats` prints this machine's usage counts of a period, sends nothing, and
a forgotten session stays counted, for `lado stats` and the telemetry report alike.

**Architecture:** `state.py` gets the table `forgotten_usage` (schema 27), the copy in
`delete_session`, `usage_counts` over both tables and `usage_start`. A new `stats.py`
builds the lines; `cli.py` only parses and prints, and does not kick the statistics
sender after `stats`. `telemetry._lado_errors` becomes `lado_errors`.

**Tech Stack:** Python 3.10+, SQLite, argparse, pytest (+ xdist).

**Spec:** `openspec/changes/usage-stats/` (proposal, deltas `usage-stats` and
`usage-telemetry`, `design.md` D1-D9) and
`docs/superpowers/specs/2026-10-14-usage-stats-design.md`.

## Global Constraints

- A minor release, 0.38.0: CHANGELOG.md's `## 0.37.1 (unreleased)` becomes
  `## 0.38.0 (unreleased)` (its lines stay).
- No new telemetry field and no change of `telemetry.FIELDS_VERSION`.
- `cli.py` changes only by the parser, `cmd_stats` and the kick's condition (LAD-33 edits
  the same file in parallel).
- One commit per task. Messages in the repo's style: a plain sentence, then `(LAD-34)`.
- Integration tests run with `-m integration`; each exit status read from a log file,
  never through a pipe (`.lado/sdlc.md`, Review traps).
- Edit with the edit tools, not `sed -i` or heredocs.

## Tests per requirement

| Requirement | Tests | Layer |
|---|---|---|
| lado stats prints the usage of a period from this machine's records | `tests/test_stats.py`: default period, `--all`, `--days 90` with a shorter history, providers' order, zero counts and no record, `--days 0`/`x`/`7 --all` exit 2 (through `cli.main`); `tests/integration/test_usage_stats.py` | unit, integration |
| lado stats never goes to the network | `tests/test_stats.py::test_stats_opens_no_socket` (consent `on` via `telemetry_on`, sockets patched to fail, outbox and `sent.json` unchanged); `tests/test_cli.py`: `stats` does not call `telemetry.kick` | unit |
| A forgotten session's usage is kept anonymously | `tests/test_state.py`: counts equal before and after a forget, 7 rows and no session name in `forgotten_usage`, a failing delete rolls the copy back, `usage_start` sees forgotten rows; the migration from schema 26 | unit |
| Statistics are counted when sent, never collected (modified) | `tests/test_telemetry.py::test_report_counts_a_forgotten_session` | unit |

End to end: `tests/integration/test_usage_stats.py` (Task 4). Regression run: Task 6.

## Review Focus

- The copy and the delete in one transaction (`delete_session`): no row counted twice,
  none lost on a failure (Task 1, its own test).
- `forgotten_usage` holds no name, path or detail (Task 1).
- `usage_counts`' return shape unchanged: `telemetry.report` and `lado telemetry show` as
  before (Task 2).
- `lado stats` starts no sender (Task 3).

---

### Task 1: `forgotten_usage`, the copy at forget, both tables counted (D1-D4)

**Files:**
- Modify: `src/lado/state.py` (`SCHEMA_VERSION` 27, `FORGOTTEN_USAGE`, `SCHEMA`,
  `MIGRATIONS[26]`, `USAGE_KINDS`, `delete_session`, `usage_counts`, `usage_start`)
- Modify: `tests/agent_helpers.py` (`schema_before`: assert `MIGRATIONS[26] ==
  [state.FORGOTTEN_USAGE]`, undo with `DROP TABLE forgotten_usage`, `SCHEMA_VERSION == 27`)
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `state.FORGOTTEN_USAGE: str`, `state.USAGE_KINDS: tuple[str, ...]`,
  `state.usage_start() -> str | None`; `usage_counts(since: str) -> dict` unchanged.

- [ ] **Step 1: Failing tests** in `tests/test_state.py`: a session with one
  `session_resume`, two `spawned` (claude, kilo), one `flow_start`, two `gate_open`;
  `usage_counts` of a period holding them before and after `delete_session` are equal;
  `forgotten_usage` has 7 rows and none of its columns holds the session's name; a
  `delete_session` whose `DELETE` raises (patch `connect` to a wrapper that raises on
  `DELETE FROM sessions`) leaves `forgotten_usage` empty; `usage_start` gives the
  forgotten session's `created_at` once it is the oldest; `usage_start()` is None on an
  empty database; `migrate()` from `previous_schema()` makes the table.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_state.py -k "forgotten or usage"`.
  Expected: FAIL.
- [ ] **Step 3: Implement.** The table with `kind TEXT NOT NULL, provider TEXT,
  created_at TEXT NOT NULL`; `delete_session` inserts `('session', NULL, created_at)`
  and the session's events of `USAGE_KINDS` (a `spawned` one with its parsed provider,
  skipped without one) before the delete, in its one `with connect() as db:`;
  `usage_counts` adds `forgotten_usage` per kind and per provider; `usage_start` the
  `MIN(created_at)` of the three sources, as `YYYY-MM-DD HH:MM:SS` (cut the events'
  milliseconds).
- [ ] **Step 4: Run** `uv run pytest tests/test_state.py tests/test_migrations*.py -n auto`
  (and every test that uses `previous_schema`: `grep -rl previous_schema tests`). Expected:
  PASS.
- [ ] **Step 5: Commit** `lado forget keeps an anonymous count of the session's usage (LAD-34)`.

### Task 2: One error counter; the report counts a forgotten session (D3, D6)

**Files:**
- Modify: `src/lado/telemetry.py` (`_lado_errors` → `lado_errors`, its one caller)
- Test: `tests/test_telemetry.py`

- [ ] **Step 1: Failing test** `test_report_counts_a_forgotten_session`: a session with two
  spawned agents after the last report, forgotten; `report(force=True)`'s properties
  count `sessions` 1 and `agents` `{"claude": 2}` (or the providers used).
- [ ] **Step 2: Rename** `_lado_errors` to `lado_errors` (tests that call it too).
- [ ] **Step 3: Run** `uv run pytest tests/test_telemetry.py tests/test_cli_telemetry.py -n auto`.
  Expected: PASS.
- [ ] **Step 4: Commit** `The telemetry report counts forgotten sessions too (LAD-34)`.

### Task 3: `lado stats` (D5, D7, D8)

**Files:**
- Create: `src/lado/stats.py` (`lines(days: int | None, now: datetime | None = None) -> list[str]`)
- Modify: `src/lado/cli.py` (the `stats` parser with a mutually exclusive `--days N` /
  `--all`, `cmd_stats`, `stats` in the condition of `kicks`, with a comment)
- Test: `tests/test_stats.py` (new), `tests/test_cli.py`

- [ ] **Step 1: Failing tests** in `tests/test_stats.py` for each scenario of the
  `usage-stats` delta (records written with `state` functions and explicit
  `created_at`s, `now` fixed): the default period; `--all` with the earliest record;
  `--days 90` with a 5-day history; providers ordered by count then name; zero counts and
  `Earliest record: none yet.` with `--all` on an empty database; `cli.main(["stats",
  "--days", "0"])`, `"x"` and `["stats", "--days", "7", "--all"]` raise `SystemExit(2)`;
  `test_stats_opens_no_socket` (fixture `telemetry_on`; `socket.socket.connect` and
  `socket.create_connection` patched to fail the test; `telemetry/outbox` and
  `telemetry/sent.json` the same after `cli.main(["stats"])`). In `tests/test_cli.py`:
  `cli.main(["stats"])` calls no `telemetry.kick`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_stats.py tests/test_cli.py -k stats`.
  Expected: FAIL.
- [ ] **Step 3: Implement** to the output in `design.md` D5.
- [ ] **Step 4: Run** `uv run pytest tests/test_stats.py tests/test_cli.py
  tests/test_lazy_imports.py -n auto`. Expected: PASS.
- [ ] **Step 5: Commit** `lado stats prints this machine's usage of a period (LAD-34)`.

### Task 4: End to end (integration)

**Files:**
- Create: `tests/integration/test_usage_stats.py`

- [ ] **Step 1: Test.** With the fake agent: `lado start <repo> --provider fake
  --no-attach`, wait until the supervisor is idle, `lado stop`, run `lado stats --all`
  (a subprocess of the CLI) and read its sessions and agents counts (1, 1 with `fake 1`),
  `lado forget <session>`, run `lado stats --all` again: the same lines but the header.
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py > /tmp/lad34-int.log 2>&1; echo $?`.
  Expected: 0.
- [ ] **Step 3: Commit** `An integration test of lado stats across a forget (LAD-34)`.

### Task 5: Docs

- [ ] **Step 1: CHANGELOG.md**: the heading becomes `## 0.38.0 (unreleased)`; add:
  - `lado stats` prints how you used LADO on this machine: sessions, agents per agent
    CLI, flow runs, gates, turn errors and LADO's own errors of the last 30 days
    (`--days N`, `--all`); it sends nothing.
  - `lado forget` keeps an anonymous count of the forgotten session's usage (kind, agent
    CLI, time; no names), so `lado stats` and the statistics report still count it.
- [ ] **Step 2: AGENTS.md**: Layout gets `stats.py`; `state.py`'s schema list gets
  "From schema 27 `forgotten_usage` …"; `telemetry.py`'s list of commands that do not
  kick gets `stats`; a `lado stats` paragraph after `lado telemetry`'s; the `lado forget`
  paragraph says what it keeps.
- [ ] **Step 3: docs/telemetry.md**: the sentence on `lado forget` says a forgotten
  session is counted (from 0.38.0), and that `lado stats` shows the same counts locally.
- [ ] **Step 4: Commit** `Docs of lado stats and the forgotten usage (LAD-34)`.

### Task 6: Regression run

- [ ] **Step 1:** `make lint`, `make test`,
  `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py tests/integration/test_telemetry_processes.py`,
  `openspec validate usage-stats --strict`, `openspec validate --specs --strict`; each
  green, its exit status read from a log file.
- [ ] **Step 2:** By hand with `LADO_HOME=/tmp/lad34-home`: `lado stats`, `lado stats
  --all`, `lado stats --days 7`; quote the output in the build report.
