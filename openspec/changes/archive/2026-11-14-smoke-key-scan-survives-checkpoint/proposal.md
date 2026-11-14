Task: LAD-270

## Why

The smoke test `test_a_provider_s_refusal_ends_the_turn_within_the_cli_s_repeats[429-kilo]`
failed once in CI (run 43007535491, cell smoke macos-latest kilo) with
`FileNotFoundError: .../lado-home/lado.db-shm`, and passed when the failed jobs were rerun.

`check_refusal` (tests/smoke/test_smoke.py), shared by the refusal tests of every provider,
ends by proving the refused key is in none of LADO's database files: it lists
`state.home().glob("lado.db*")` and reads each listed file. It does so while the session
still runs: the session loop, the agents' `lado mcp` servers and their hooks open and close
connections to `lado.db` all the time. lado.db is in WAL mode (`state.py`), and SQLite
checkpoints the WAL into `lado.db` and deletes `lado.db-wal` and `lado.db-shm` when the last
connection closes. When that happens between the listing and the read, the read fails. The
defect is in the test, not in LADO: the files are SQLite's own and may come and go.

## Options

1. **Read in a fixed order and skip a side file that is gone** (chosen): read `lado.db-wal`
   and `lado.db-shm` first, each skipped when it no longer exists, then `lado.db`, which must
   exist. A checkpoint moves the WAL's pages into `lado.db`, which is read last, so a key
   that was in a vanished WAL is still seen. Long-term cost: a helper of a few lines with a
   unit test; it does not depend on what the other processes do or when they stop.
2. **Scan after `stop_session`**: the session's processes are gone, so in most runs only
   `lado.db` is left. But `stop_session` waits for the loop only; an agent's dying hook or
   MCP process may still close its connection a moment later, so the race shrinks but stays;
   and the scan would leave `check_refusal` for each caller to place after its own stop.
3. **Read through SQLite** (`sqlite3` over the tables) instead of the bytes: no race, but it
   proves less: the byte scan also covers freed pages and the WAL that a query never shows.

## What Changes

- A helper in `tests/agent_helpers.py` that asserts a secret is in none of LADO's database
  files, reading `lado.db-wal`, `lado.db-shm`, then `lado.db`, a missing side file skipped
  (no existence check before the read: a `FileNotFoundError` on a side file is the skip),
  a missing `lado.db` a failure.
- `check_refusal` uses it in place of its `glob("lado.db*")` loop.
- A unit test of the helper in `tests/test_agent_helpers.py`.

## Scope

- The key scan of `check_refusal`, which serves the refusal tests of kilo, opencode and
  claude.

## Out of scope

- Other byte scans of a folder (`tests/test_agent_helpers.py`, `tests/test_cli.py`,
  `keep_evidence`): they run on a folder no live LADO process writes, so they do not race.
- Any change of LADO's database handling (WAL mode, checkpoints): the behaviour is SQLite's
  and correct; only the test assumed the files stay.
- The `hooks.log` check of `check_refusal`: the file is only appended to, never deleted.

## Acceptance criteria

- AC-1: `check_refusal` no longer lists `lado.db*` and reads each listed file; it calls the
  helper, which reads `lado.db-wal`, `lado.db-shm` and `lado.db` in that order.
- AC-2: The helper passes when `lado.db-wal` or `lado.db-shm` is missing and neither of the
  files there holds the secret; it fails, naming the file, when any file read holds it; it
  fails when `lado.db` is missing.
- AC-3: The unit tests of the helper pass in `make test`; `make lint` passes.
- AC-4: The smoke cells that run `check_refusal` (kilo, opencode, claude) pass in the pull
  request's CI.

## Impact

- Tests only: `tests/agent_helpers.py`, `tests/smoke/test_smoke.py`,
  `tests/test_agent_helpers.py`. No code, spec, API, schema or CHANGELOG change, no version
  bump (neither minor nor patch): nothing users see.
