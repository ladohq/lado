# LAD-143 one-database-backup: review report

Pull request #165 `feature/lad-143-one-database-backup` → `main`. Scale: full, reviewed
for breadth. Head reviewed last: `759b0664` (= the remote head), base `5fe98733`.
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
unchanged, so no live tests are needed before the merge.

## Rounds

- **Round 1** (local, breadth, `origin/main...73facea0`): lenses spec, tests, silent
  failures, comments, types, general and the architecture against AGENTS.md; no UI lens
  (no screen changed). F1 important; F2, F3, F4 minor.
- **Round 2** (local, precision, the delta `73facea0..759b0664`) and **external 1**
  (Claude Code GitHub Action, the whole pull request `5fe98733..759b0664`; request comment
  6381190960, "Claude finished" at 07:01:10Z, answer to the threads comment 6381210798):
  F5; E1-E5. The external reviewer read the risky code (`self_update.py` whole,
  `update.py`, `rc_check.py`, `cli.py` and `state.py` by hunks), not the tests, documents
  or openspec files (read locally in round 1).

External rounds used: 1 of 2. The external reviewer is of the same model family, so its
"nothing blocking" weighs less. F1 and F2 were in code changed by the developer's cleanup
before review (cf467a3a).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | a copy `backups/lado.db.schema-<S>` gone between the plan and the restore: `state.copy_db` opened it for writing, left an empty file in `backups/` and overwrote `lado.db` with an empty database; the rollback then restored nothing and said `database: kept` | confirmed | important | fixed in 759b0664: `restore` opens the source `mode=ro&immutable=1`; tests `test_a_copy_gone_before_the_restore_leaves_lado_db_and_backups_as_they_were`, `test_a_copy_gone_before_the_rollbacks_restore_is_a_failed_rollback` |
| F2 | 1 | local | the reason of `rollback_failed` said "its backup is None" | confirmed | minor | fixed in 759b0664; test `test_a_loop_that_does_not_end_in_a_rollback_with_nothing_to_restore_names_no_backup` |
| F3 | 1 | local | after the restore, a rollback to an old-schema version that fails says `database: kept` though the database is already the old copy | confirmed | minor | declined: the spec `update-database` asks for it; the loss was accepted in the plan (#1457) |
| F4 | 1 | local | AC-6 of the proposal promised "no wheel" for an old version of the same schema | confirmed | minor | fixed in 759b0664 (document only) |
| F5 | 2 | local | `docs/design/modules.md:738` still says `self_update.restore` goes through `state.copy_db` | confirmed | minor | declined: a one-line fix, left to the human at the merge gate |
| E1 | 2 | external 1 | a restore giving another schema → the rollback says `database: kept` | confirmed | minor | declined: the class of F3; only with a copy changed by hand (`state.migrate` names the copy by its schema) |
| E2 | 2 | external 1 | `release_schema` opens a URL of any scheme (`file:`, `ftp:`) | refuted | — | the index already decides what the installer installs; the tests use `file://` on purpose |
| E3 | 2 | external 1 | the schema regex refuses another line shape instead of guessing | refuted | — | not a defect: by design (`update.py:155`) |
| E4 | 2 | external 1 | without an installer and without the copy, `plan()` refuses before `print_by_hand` | confirmed | minor | declined: the refusal is right, the old LADO would not open the database; the manual path is in install.md |
| E5 | 2 | external 1 | `rc_check._hand_over` may leave a `.tmp` when the copy fails | confirmed | minor | declined: harmless, the next run overwrites it |

## Checked against the spec

Every requirement and scenario of `update-database`, `schema-migration` and
`release-candidates` is covered by code and a test; every task of `tasks.md` is checked;
the design's decisions hold, nothing beyond the scope. The pull request's description
matches the diff, 759b0664 included.

## Checks

Round 2 on 759b0664: `make lint` 0; `tests/test_self_update.py tests/test_update.py
tests/test_rc_check.py tests/test_state.py` 367 passed; `tests/integration/test_update_process.py`
(`-m integration`) 12 passed; `openspec validate one-database-backup --strict` valid; CI
23/23 pass, `ci-ok` pass. Round 1 on 73facea0: unit 364 passed, integration 12 passed,
`--specs --strict` 47 passed. The developer's `make test`: 4262 passed.

## Not checked

The real 0.42.0 wheel from PyPI (the tests do not download it); the manual check of
docs/release.md 4.4 covers it at 0.43.0rc1.
