Task: LAD-256

## Why

Symptom: after `python3 scripts/rc_check.py rollback` on the human's Mac, `~/.lado-rc/`
holds three files: `lado.db.0.44.0`, `lado.db.0.44.0-shm` (32 KB) and
`lado.db.0.44.0-wal` (0 B); no process holds them (`lsof` is empty). The living spec
("rc_check reads a database no LADO holds") says no such file is left, and the next RC's
check 4.2 expects one file in `~/.lado-rc/`. Found at the manual check of 0.45.0rc1,
2026-11-09 (session artifact `rc-report-0.45.0rc1-c825a281.md`, finding 3).

Cause: since LAD-150 (`rc-check-wal-read`) `_reading()` opens every database with an
ordinary connection and `PRAGMA query_only = ON`. A WAL database opened so gets a `-wal`
and a `-shm` at once, and the promise that they go rests on SQLite's own close: the last
connection checkpoints and deletes both. Linux's SQLite does, which is what the unit tests
see. The SQLite of macOS's `python3` keeps them after the last close (the `-wal`
truncated to 0 bytes, the `-shm` kept: a persistent WAL), which is what the report
shows. The tests could not catch it: they run on Linux and look only after the close.

Options weighed:

- A (taken, with the human's correction at the first `design_ok`): choose the way of
  reading by the database's state, in `_reading()` alone. Without a `-wal` beside it, or
  with an empty one, the WAL holds nothing the main file lacks, so it is read with
  `file:<path>?mode=ro&immutable=1`, which creates no file, changes none and refuses
  writes, on every platform. An empty `-wal` counts as none because macOS's SQLite leaves
  one (with a `-shm`) after every close: in `~/.lado-rc/` now, and in `~/.lado/` after
  LADO stops; a rule on the file's presence alone would read those databases the
  ordinary way and leave the files again. With a non-empty `-wal` (a running LADO), it is
  read as now, its WAL included. One function, one rule; `lado update` reads its backups
  the same way (`self_update.py`). Long-term cost: a narrow race, a LADO that writes its
  first WAL pages between the check and the read is read without them; the plan the
  human confirms is read once, so at worst it misses a session started in that
  instant.
- B: `immutable=1` for the copy in `~/.lado-rc/` only, `lado.db` as now: fixes the
  symptom, but keeps two ways of reading picked by path (LAD-150's reason to reject it)
  and leaves `lado.db-wal` and `-shm` in `~/.lado/` on the Mac after `upgrade`, against
  the same requirement.
- C: delete the `-wal` and `-shm` the connection made, after its close: the files of a
  LADO that started meanwhile would be deleted under it, which can corrupt `lado.db`.

## What Changes

- `scripts/rc_check.py`: `_reading()` opens a database without a `-wal` beside it, or
  with an empty one, with `mode=ro&immutable=1`, one with a non-empty `-wal` as now (ordinary, `query_only`); its docstring
  says why, the claim that SQLite's close removes the files goes.
- `tests/test_rc_check.py`: the reads of a database at rest create no side file even
  while the connection is open (what fails on Linux today and stands for the Mac's
  leftovers); a database with an empty `-wal` and `-shm` beside it (as macOS leaves them)
  is read with no new file and neither of them grown; a database held by another
  connection, with a row only in its WAL, is read
  with that row.
- No CHANGELOG.md line (release tooling, users do not see it); no version bump: the fix
  ships in 0.45.0rc2, a fix release of the frozen 0.45.0.

## Scope

- How `rc_check.py` opens `lado.db` and the kept copy.

## Out of scope

- Cleaning the leftover `-shm` and `-wal` already in `~/.lado-rc/` on the human's Mac:
  the next `upgrade` from a final writes its copy as the only file of the folder
  (`_copy`), which removes them; a rollback before that does not count them as copies
  (`kept()` matches `lado.db.<version>` exactly).
- A test on a real Mac in CI: the unit tests run on Linux; the test that no file appears
  while the connection is open covers the Mac's case without one.
- The other findings of the 0.45.0rc1 report: their own tasks.
