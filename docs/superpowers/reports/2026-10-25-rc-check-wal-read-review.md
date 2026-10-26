# LAD-150 rc-check-wal-read: review report

Pull request #172 `hotfix/lad-150-rc-check-wal` → `main`. Scale: hotfix, reviewed for
precision (release tooling, not the product). Head reviewed last: `59979b18` (= the
remote head), base `9d41c16c`. `scripts/rc_check.py` reads `lado.db` and the kept copy
with an ordinary SQLite connection set to `PRAGMA query_only = ON` (`_reading()`, was
`_read_only()` with `mode=ro`), so a WAL database at rest is read on every platform and
leaves no `-wal` / `-shm`; unit tests in `tests/test_rc_check.py`; the `.env` of
docs/release.md 4.5 names `LADO_GIT_NAME` and `LADO_GIT_EMAIL`. No CHANGELOG line, no
version bump. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
and `tests/live/` unchanged: no live tests needed. Schema migration: no.

## Rounds

- **Round 1** (`9d41c16c..59979b18`, the whole pull request): a local precision pass, a
  check against the spec and against AGENTS.md. The ADDED requirement "rc_check reads a
  database no LADO holds" and its scenarios are covered by
  `test_upgrade_reads_a_wal_lado_db_at_rest_and_leaves_no_side_file`,
  `test_the_plan_reads_wal_databases_at_rest_and_leaves_no_side_file` and
  `test_the_scripts_reads_cannot_write`; the MODIFIED requirement matches its heading in
  the living spec. The supervisor's point (writes refused) checked: `query_only` is set
  and the test was red before. Checks: `make lint` ok; `tests/test_rc_check.py` 71
  passed; both `openspec validate` runs valid (49/49). **External 1** (Claude Code GitHub
  Action, request at 20:32:55Z, "Claude finished" at 20:33:12Z): read
  `scripts/rc_check.py`, `tests/test_rc_check.py`, `docs/release.md`, not the openspec
  texts (checked locally).

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less. CI on `59979b18`: 23/23 green, smoke and container
included.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | an ordinary `sqlite3.connect` creates an empty database when `lado.db` is missing (`_schema(live)` after `lado update` and after the restore) | confirmed | minor | declined: `lado update` does not remove `lado.db`, and "schema is 0, not N" still stops the rollback; `?mode=rw` would fix it cheaply |
| F2 | 1 | local | a changed line of docs/release.md is 123 characters long | confirmed | minor | declined: style, the file has longer lines |
| E1 | 1 | external | a non-empty `-wal` left by a crash makes the read checkpoint into the database despite `query_only` | refuted | — | dropped: no one opens the copy, so it has no `-wal`; for the live database the checkpoint moves committed pages, as the next `lado` run would |
| E2 | 1 | external | `_schema(copy)` in `plan()` is called without checking the file exists | refuted | — | dropped: `kept()` returns existing files only |
| E3 | 1 | external | `side_files` is defined below `make_db`, which uses it | confirmed | minor | declined: taste, resolved at call time |

Found on the way: nothing.

## Not verified (residual risk)

- macOS's error (`unable to open database file`) cannot be reproduced on Linux; the
  tests catch the Linux effect of the same cause (side files left behind). Confirmation
  on a Mac at the manual check of rc2.
- The reviewer did not run the full `make test`; the developer did (4311 passed), and CI.
