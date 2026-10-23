## Context

The cause and its evidence are in `proposal.md`: lado.db's commits wait for an fsync while
they hold the write lock (WAL with `synchronous = FULL`), and a saturated disk stretches
that past every other writer's 10 s busy timeout. The fix shortens the lock at its source
and stops counting a short lock as LADO's error.

Options weighed (the human chose B, question #994):

- **A. `synchronous = NORMAL` only.** One line; removes the cause. Long-term cost: none
  in code; a power cut or OS crash may lose the last commits (never the database).
- **B. A, and the loop journals a lock only after 60 s.** A little code in one class
  both loops already share. Long-term cost: one constant and one rule in the spec
  `error-journal`; a real long holder still shows up as one error.
- **C. A retry around every write, or one connection per process.** Touches every
  function of `state.py` and every caller's process model; a retry would also hide a
  real long holder. Long-term cost: high, for nothing A does not already fix.

Against AGENTS.md: the change is below `providers/` and the same for every agent CLI
(neutral core); the lock rule lives in the one class both loops use (one source of truth);
a lock that lasts is still written, once (no silent drop); no field, option or setting is
added (only what is used). ROADMAP's coming stages (projects, more sessions in one LADO)
only add writers, so the shorter lock helps them too.

## Decisions

### D1. `synchronous = NORMAL` on every connection `state._open` makes

`synchronous` is a setting of the connection, not of the file, so `_open` runs
`PRAGMA synchronous = NORMAL` after `journal_mode = WAL`, for every connection, the
migration's too. The read-only connections (`schema_version`, `pending_migration`, the
UI feed's `?mode=ro`, `uninstall`) write nothing and stay as they are; `copy_db`'s backup
target is written once and closed, and stays as it is.

### D2. The lock rule lives in `loop.RepeatedErrors`

Both the session loop and the UI server's change feed (`lado.server.feed.Hub`) journal
their failing passes through `RepeatedErrors`, so the rule goes there once: the feed reads
lado.db too and can meet the same lock. `failed()` keeps writing the log line as now; for
a lock it does not call `telemetry.record` at the first failure, remembers when the run
of failures began (`time.monotonic()`), and records the current exception once, at the
first repeat at least `LOCK_GRACE` seconds after that start. `worked()`, another error or
`flush()` end the run as now; nothing is recorded for a run that ended before the grace.

### D3. What a lock is

An exception that is a `sqlite3.OperationalError` whose `str()` is `database is locked`
(a helper `loop.is_locked(exc)`). Not "database table is locked" (`SQLITE_LOCKED`, a
conflict inside one connection, a bug worth reporting at once) and no other
`OperationalError`.

### D4. `LOCK_GRACE = 60.0` seconds, a module constant

The human's number (question #994). A constant beside `REPEAT_NOTE`, so tests set it with
`monkeypatch`; no environment variable or setting (only what is used).

### D5. The test layer is unit

The pragma is read back from a connection `state._open` makes (`tests/test_state.py`);
the journal rule is in-process logic of `RepeatedErrors`, driven through `loop.run` with a
`runtime.sweep` that raises, as the loop's tests already do (`tests/test_loop.py`,
`tests/test_error_journal.py`), and through the feed's `Hub` (`tests/test_feed.py`). No
behaviour crosses processes in a new way, so no integration test is added; the regression
run includes the existing integration tests through CI.

### D6. Version: patch

A fix with no schema change, no command, option or MCP tool; its CHANGELOG line goes
under `## 0.43.0 (unreleased)`, `### Fixed` (main is that version's line).
