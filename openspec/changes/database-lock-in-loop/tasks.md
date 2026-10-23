## 1. Commits do not wait for the disk

- [x] 1.1 `src/lado/state.py`, `_open`: `PRAGMA synchronous = NORMAL` after
  `PRAGMA journal_mode = WAL`, with a one-line comment why (WAL: a commit no longer
  fsyncs while it holds the write lock; a power cut may lose the last commits, never the
  database). Check: 1.2.
- [x] 1.2 `tests/test_state.py` (unit): a connection of `state.connect()` answers
  `PRAGMA synchronous` with 1 (NORMAL) and `PRAGMA journal_mode` with `wal`; so does the
  connection `migrate()` uses (through a migration of an older database, as the
  migration tests do, or `_open()` directly). `make test`.

## 2. A short lock is no error of the loop

- [x] 2.1 `src/lado/loop.py`: `LOCK_GRACE = 60.0` beside `REPEAT_NOTE`; `is_locked(exc)`
  (a `sqlite3.OperationalError` whose `str()` is `database is locked`, design D3);
  `RepeatedErrors.failed()` writes its log line as now, and for a lock records nothing at
  the first failure, keeps when the run began, and calls `telemetry.record` once at the
  first repeat `LOCK_GRACE` or more seconds after that start (design D2); the class
  docstring says so. Another error, `worked()` and `flush()` behave as now. Check: 2.2–2.4.
- [x] 2.2 `tests/test_error_journal.py` (unit), beside
  `test_loop_journals_a_repeated_error_once`: a `runtime.sweep` that raises
  `sqlite3.OperationalError("database is locked")` for some passes, then works →
  `loop.log` has the traceback and "passes work again", `errors.jsonl` has no line;
  with `LOCK_GRACE` 0 and passes that keep failing → exactly one line, `where` `loop`,
  the session kept; a `RuntimeError` → its line at once (scenarios of the delta).
- [x] 2.3 `tests/test_loop.py` (unit): `is_locked` is true for that exception only, false
  for `sqlite3.OperationalError("database table is locked")`, another `OperationalError`
  and a `RuntimeError` with the same text.
- [x] 2.4 `tests/test_feed.py` (unit): the feed's `Hub` whose source raises "database is
  locked" logs it to `lado.server` and writes no `errors.jsonl` line while the grace has
  not passed (as the feed's existing failing-read tests drive it).

## 3. The documents

- [x] 3.1 `docs/design/agents.md`, the loop's paragraph: an error in a pass goes once to
  `errors.jsonl`, but a locked lado.db only when it has failed the passes for
  `loop.LOCK_GRACE` (60 s).
- [x] 3.2 `docs/telemetry.md`, "The local error journal": one sentence that a lock of
  lado.db that clears within a minute is written to `loop.log` only.
- [x] 3.3 `docs/design/modules.md`, the `state.py` line: lado.db runs in WAL mode with
  `synchronous = NORMAL`, and why in a few words.
- [x] 3.4 CHANGELOG.md, `## 0.43.0 (unreleased)`, `### Fixed` (add the group when it is
  missing): e.g. "**No more "database is locked" from the session loop on a busy disk.**
  LADO's database no longer waits for the disk on each write; a short lock is no longer
  counted as an error."

## 4. The checks

- [x] 4.1 `make lint`; `make test` (report the counts);
  `openspec validate database-lock-in-loop --strict`; `openspec validate --specs --strict`;
  grep `openspec/specs/` for `errors.jsonl` and `database is locked`: no rule left that
  says a loop's lock is journaled at once.
- [ ] 4.2 Regression: CI green on the pull request (unit, integration, UI, smoke), as
  `.lado/sdlc.md`'s Checks say; `uv run pytest -m integration -n auto tests/integration/`
  is not run locally unless an integration test changes (none does).
