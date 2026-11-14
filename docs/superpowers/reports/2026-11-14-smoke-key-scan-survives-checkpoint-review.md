# LAD-270 smoke-key-scan-survives-checkpoint: review report

Pull request #302 `hotfix/lad-270-smoke-key-scan` → `main`. Scale: hotfix, depth precision.
Head reviewed: `d9823702`. The key scan of the smoke test's `check_refusal` no longer lists
`lado.db*` and reads each listed file while the session still runs: SQLite deleted
`lado.db-shm` between the listing and the read (`FileNotFoundError`, run 43007535491, smoke
macos-latest kilo). A helper `check_no_secret_in_db` in `tests/agent_helpers.py` reads
`lado.db-wal`, `lado.db-shm`, then `lado.db`; a side file that is gone is skipped, a missing
`lado.db` fails. Tests only: nothing users see, no CHANGELOG line.

## Rounds

1. Local, precision (the whole diff `origin/main...d9823702`), with the change checked against
   its proposal, and external 1, Claude Code GitHub Action ("no blocking findings"; raised E1,
   E2). The external reviewer read all three test files, not the openspec files, which the
   local round checked.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: a key written to the WAL after its read and not checkpointed before `lado.db` is read would be missed | declined: a byte scan without a snapshot cannot close it; `check_refusal` calls the scan after the refusal is recorded; the old `glob` loop had the same window |
| E2 | minor | external: `match="lado.db"` in `test_the_db_scan_fails_without_lado_db` is a loose regex | declined: the `FileNotFoundError` comes only from reading `lado.db`, so the test is right |

## Spec check

- AC-1: `check_refusal` calls `agent_helpers.check_no_secret_in_db(state.home(), key)`; order
  wal → shm → db; no `glob("lado.db*")` left in `tests/`.
- AC-2: a missing side file skipped, a missing `lado.db` a failure, a hit fails naming the
  file: three tests plus one parametrized ×3, and a test of the read order (a checkpoint
  simulated mid-scan).
- AC-3: `uv run pytest tests/test_agent_helpers.py -n0` 17 passed (6 new); `make lint` clean.
- AC-4: CI run 43624302791 on `d9823702` success, 27/27; smoke kilo, opencode and claude on
  ubuntu and macOS green.
- The interleavings with a checkpoint (before the WAL read, between it and `lado.db`, after, a
  passive checkpoint resetting the WAL) were walked by hand: with wal → db no key is lost.

## Found on the way

- `tests/conftest.py` does not clear `LADO_LAUNCH_VARS` and `CLAUDE_CODE_TMPDIR`: 1-3 tests of
  `tests/test_temp_dirs.py` red when run from an agent's environment, on `main` too (passed to
  the supervisor by the developer).
- Flaky UI test `test_chat::test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways`
  (ui (2), run 43622855043, passed on rerun); a task proposed to the human.

## Checks

On `d9823702`:
- `make lint`: clean.
- `make test`: 6124 passed (developer's run); the reviewer ran `tests/test_agent_helpers.py`.
- `openspec validate smoke-key-scan-survives-checkpoint --strict` valid.
- CI run 43624302791: success.

Not run locally: smoke tests (they need the real CLIs; CI ran them). No change to
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.

## Residual risk

The race cannot be reproduced deterministically: the fix is proven by a unit simulation and one
green CI run; that the rare flake is gone shows only over time.
