Task: LAD-129

## Why

The session loop's pass sometimes fails with `sqlite3.OperationalError: database is
locked`: lado.db stayed write-locked longer than a connection's busy timeout (10 s,
`state._open`). The loop survives and the next pass retries, but the pass's work is late,
and every such failure is a line in `errors.jsonl` and an error event in telemetry: 16 of
the 20 LADO errors in PostHog from 13.10 to 22.10, on 3 installs (0.38.0 to 0.42.0).

**Symptom.** On the install of the 19.10 burst (0.41.0), `loop.log` shows the loops of four
sessions failing in the same second (18:03:10) and working again in the same second
(18:03:12), and the same at 18:06, 18:09–18:10 and 18:12: the whole database was
write-locked for 25–40 s, for every process at once, not one session's transaction. In the
same hour `hooks.log` has "git took longer than 2 s": the machine's disk was saturated.

**Cause.** No transaction in `state.py` does slow work inside it (no tmux, git, network or
callback that does; only `state.py` opens lado.db for writing). lado.db runs in WAL mode
with Python's default `synchronous = FULL`, so every COMMIT waits for an fsync of the WAL
while it holds the write lock. When the disk is busy (agents' test runs, clones, Docker
Desktop's virtual disk), an fsync takes seconds, and the queue of writers (each loop every
2 s, every hook, `lado mcp`) outgrows the 10 s timeout. Measured in LADO's container: under
one background write with fsync (`dd … conv=fsync`), a commit with `FULL` held the lock up
to 1027 ms; with `NORMAL`, at most 0.1 ms.

## What Changes

- **`state._open`**: every connection sets `PRAGMA synchronous = NORMAL`, SQLite's
  recommended setting for WAL: a commit no longer waits for the disk (only checkpoints
  fsync), so the write lock is held for microseconds. The database cannot be corrupted by
  any crash; a power cut or an OS crash (not a crash of LADO) may lose the last commits.
  The human accepted that trade (question #994).
- **The loop's error journal** (`loop.RepeatedErrors`): a failing pass whose error is a
  locked lado.db is still written to `loop.log` as now, but it goes to `errors.jsonl` (and
  so to telemetry) only when the same error has repeated for 60 s (`loop.LOCK_GRACE`):
  once per streak. A lock that clears sooner is no error of LADO (question #994). The
  same rule holds for the UI server's change feed, which uses the same class.
- **Docs**: `docs/design/agents.md` (the loop's paragraph), `docs/telemetry.md` (the local
  error journal), `docs/design/modules.md` (state.py: WAL with `synchronous = NORMAL`).
- **CHANGELOG.md**: one line under `## 0.43.0 (unreleased)`, `### Fixed`.

## Scope

`src/lado/state.py` (`_open`), `src/lado/loop.py` (`RepeatedErrors`, `LOCK_GRACE`),
`tests/test_state.py` or the state tests, `tests/test_loop.py`, `tests/test_feed.py`, the
spec `error-journal` (delta), the three documents above, CHANGELOG.md.

## Out of scope

- A retry of every write in `state.py`, or one long-lived connection per process: a large
  rework that would also hide a real long holder of the lock; with commits no longer
  waiting for the disk, nothing needs it now.
- The busy timeout (10 s) and the other callers that may meet a locked database (hooks,
  `lado mcp`'s `send_message`, the CLI): they keep their handling; the cause fixed here is
  theirs too, and a hook or tool that waits longer delays the agent.
- Running `PRAGMA journal_mode = WAL` only when the database is not in WAL yet (the
  0.38.0 frames in `_open`): on a WAL database it is a cheap no-op read, and the read it
  needs would be the same.
- Finding the holder of a lock at the moment it happens (lsof, fuser): not portable, and
  the evidence above already names the cause.

## Impact

- Commits of lado.db stop waiting for the disk; a power cut or an OS crash may lose the
  last seconds of LADO's state (never the database itself).
- `errors.jsonl` and telemetry stop counting a lock that clears within a minute; a longer
  one is still one error, so a real long holder stays visible.
- No schema change, no new command, option or MCP tool. Version: patch (a fix), one
  CHANGELOG line.
