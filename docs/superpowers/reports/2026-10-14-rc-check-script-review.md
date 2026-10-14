# LAD-51 rc-check-script: review report

Pull request #32 `feature/lad-51-rc-check` → `main`. Scale: full, no version bump and no
CHANGELOG line (the script and the docs do not ship in the package). Head reviewed last:
`bff20be` (= the remote head); the archive commit follows it. `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change, so live
tests are not needed before the merge.

## Rounds

- **Round 1** (`origin/main...26fd2a8`, the whole pull request): local breadth pass
  (lenses spec, tests, silent failures, comments, types, general, and the architecture
  against AGENTS.md; the UI lenses skipped, the UI did not change). F1 important, F2-F4
  minor. No external round requested.
- **Round 2**: local precise pass over `26fd2a8..bff20be` (no new findings) and external
  round 1 by the Claude Code Action (request at 07:02:31 UTC, "Claude finished" at
  07:03:46 UTC, delta comment 6162831676): no blocker or important; E1-E3 minor, E4
  unverifiable, E5 refuted.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | `upgrade` decided on the copy of the final's database by `lado update`'s exit code; a `partial` update (RC installed, a session did not resume, exit 1) made no copy, and the next update deleted the final's backup | confirmed | important | fixed in `bff20be`: decided by `lado --version`; `test_an_update_that_installed_the_rc_but_failed_after_keeps_the_copy`; spec and D5 updated |
| F2 | 1 | local | `_stopped` said "your sessions are stopped" also when `lado stop --all` itself failed | confirmed | minor | fixed in `bff20be`, `test_a_failed_stop_does_not_say_the_sessions_are_stopped` |
| F3 | 1 | local | the checklist takes only `- ` items, `release_notes.ITEM` also `*`, `+`, `1.` | confirmed | minor | declined: CHANGELOG.md is written with `- ` only |
| F4 | 1 | local | Ctrl-C in `rollback` after `stop --all` exits 130 without the commands that resume the sessions | confirmed | minor | declined: outside the spec, a rare path; the plan above already named the sessions |
| E1 | 2 | external | `_copy` unlinks everything in `~/.lado-rc`; a subfolder there is an `IsADirectoryError` after the update | confirmed | minor | declined: only the script writes that folder |
| E2 | 2 | external | without `~/.lado/lado.db` the plan says "its schema 0 is the copy's" | confirmed | minor | declined: a message only, the database is not touched |
| E3 | 2 | external | the uninstall check reads any non-zero `tmux list-sessions` as "server gone", also a tmux that cannot run (127) | confirmed | minor | declined: the same tmux has just run the sandbox's session |
| E4 | 2 | external | `mode=ro` on a WAL database without `-shm` may raise `sqlite3.OperationalError`, a traceback instead of `RcError` | unverifiable | — | residual risk: it fails at the plan, before any change |
| E5 | 2 | external | compatibility with python3 3.9 | refuted | — | `removeprefix` and `is_relative_to` are 3.9+, `from __future__` covers the annotations; a real run on 3.9.6 |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 4 (F1-F4) | 0 | 0 |
| external, Claude Code Action | 3 (E1-E3) | 1 (E5) | 1 (E4) |

## Checks

- Reviewer on `bff20be`: `make lint` clean; `make test` 2873 passed;
  `tests/test_rc_check.py`, `test_release_notes.py`, `test_telemetry.py` 134 passed;
  `openspec validate rc-check-script --strict` valid; `openspec validate --specs
  --strict` 17 passed.
- CI on `bff20be` green: check (3.10, 3.13), ui, js, smoke × 8 (Linux, macOS).
- Every task of `tasks.md` checked.

## Found on the way

None.

## Not checked

- `upgrade` and `rollback` never ran against a real LADO (D10); their first real run is
  the next RC. In particular the assumption that `lado update <final>` from the RC exits 0
  while no session and no UI run.
- E4 on a live WAL database.
- Restoring `lado.db` by the backup API was checked on real SQLite files in the tests, not
  on a live `~/.lado`.
- The external reviewer is the same model family.

## Result

Converged after round 2 (1 of 2 external rounds).
