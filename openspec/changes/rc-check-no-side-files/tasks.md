## 1. Tests first (unit, `tests/test_rc_check.py`)

- [x] 1.1 Scenario "no side file while the script reads": a test that makes the copy with
  `make_db(..., wal=True)` and asserts `side_files(copy) == []` inside
  `with rc._reading(copy)` and after it. Red before 2.1 (Linux's SQLite makes both files
  while the ordinary connection is open).
- [x] 1.2 Scenario "empty side files left by macOS stay as they are": a test that makes
  the copy with `make_db(..., wal=True)`, then writes an empty `<copy>-wal` and a 32 KB
  `<copy>-shm` of zeros beside it, reads it through `rc._reading(copy)` (schema and
  sessions right) and asserts that the folder holds the same three names and that both
  side files keep their sizes (0 and 32768). Red before 2.1 on Linux (the ordinary
  connection rewrites the `-shm` and, as the last one, deletes both on close).
- [x] 1.3 Scenario "a running LADO's WAL is read": a test that holds an ordinary
  connection to a WAL `lado.db` with `wal_autocheckpoint = 0`, inserts a session after
  the database was made (so it is only in the `-wal`), and asserts that
  `rc._reading(live)` returns it, with that connection still open. Green before and after
  2.1 (it guards the ordinary path).
- [x] 1.4 Keep `test_the_scripts_reads_cannot_write` (scenario "a write … is refused"):
  it must pass with the immutable read too (`attempt to write a readonly database`
  matches `readonly`).

## 2. The fix

- [x] 2.1 `scripts/rc_check.py`, `_reading()`: without `<path>-wal` beside the file, or
  with one of size 0,
  `sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)`; with a non-empty one, the
  ordinary connection with `PRAGMA query_only = ON` as now. The docstring says why each
  (no `-wal` or an empty one = nothing beyond the main file; immutable makes no file on any platform, where macOS's SQLite
  keeps an empty `-wal` and a `-shm` after every close; a holder's WAL needs the ordinary one) and
  drops "this one removes the files it made". 1.1-1.4 and the existing WAL tests pass.

## 3. Checks

- [ ] 3.1 `make lint`, `make test`, `openspec validate rc-check-no-side-files --strict`
  and the trial archive of `.lado/sdlc.md` pass; `python3 scripts/rc_check.py --help`
  runs. No CHANGELOG.md line, no doc change beyond the docstring
  (docs/design/modules.md's line of `rc_check.py` does not describe how it reads; check).
