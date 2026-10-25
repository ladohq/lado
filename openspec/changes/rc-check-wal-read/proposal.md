Task: LAD-150

## Why

Symptom: on the human's Mac, `python3 scripts/rc_check.py upgrade X.Y.ZrcN` stops in
`_schema()` and `rollback` in `plan()` with `sqlite3.OperationalError: unable to open
database file`, before anything changes. A second, smaller gap: `lado project repo add
<project> --new <name>` in section 4.5 of the checklist (the image) fails with `lado: git
doesn't know who signs the agents' commits`. Found at the manual check of 0.43.0rc1,
2026-10-25 (report findings B-2 and B-4).

Cause of the first: `_read_only()` opens a database as
`file:<path>?mode=ro`. LADO's `lado.db` is in WAL mode. When no process holds it, which
is its usual state right after `lado update` and always the state of the kept copy
`~/.lado-rc/lado.db.<final>`, it has no `-wal` and `-shm` files beside it, and a
read-only connection must create the `-shm`. The SQLite of macOS's `python3` refuses that
in read-only mode; the SQLite of Linux's python creates both files and leaves them
behind (in `~/.lado-rc/` too). The unit tests never saw it: their databases are in the
default rollback-journal mode. The workaround at the check was a background process
holding an ordinary connection to each database.

Cause of the second: the `.env` of 4.5 has no `LADO_GIT_NAME` / `LADO_GIT_EMAIL`, and the
image writes git's identity only from them (docker/compose.yaml); docs/install.md's
example has them, the checklist was written before 4.5 gained `project repo add --new`
(0.43.0).

Options weighed for the first:

- A (taken): read with an ordinary connection (`sqlite3.connect(path)`) that refuses
  writes (`PRAGMA query_only = ON`: the kept copy is what a rollback goes back to). It
  opens a WAL database in any state on every platform, sees what a running
  LADO has in its WAL (the live `lado.db` while sessions run), and, as the last
  connection of a database no one else holds, removes the `-wal` and `-shm` it made on
  close, so nothing is left in `~/.lado-rc/`. The fix the report names, and the
  workaround that worked.
- B: `?immutable=1`: opens without `-shm` and never writes, but ignores the WAL: the
  live `lado.db` of a running LADO would read stale (sessions missing from the plan).
  Right only for the copy, so two ways of reading for one script.
- C: keep `mode=ro` and fall back to B on the error: both ways, and the stale read
  stays on the fallback path.

## What Changes

- `scripts/rc_check.py`: `_read_only()` (renamed `_reading()`, its docstring saying why
  not `mode=ro`) opens an ordinary connection; `_schema()` and `plan()` read through it
  as now.
- Unit tests: `make_db` of `tests/test_rc_check.py` can make a WAL database; `upgrade`
  and `rollback` over WAL databases with no `-wal` / `-shm` read them and leave no such
  file.
- docs/release.md, 4.5: the `.env` names `LADO_GIT_NAME` and `LADO_GIT_EMAIL`, and the
  log check says there is no warning about git's identity either.
- No CHANGELOG.md line (release tooling, not the product); no version bump.

## Scope

- How `rc_check.py` opens `lado.db` and the kept copy; the checklist's `.env` of 4.5.

## Out of scope

- The `.env` files of 4.6: that section starts sessions only and adds no repository,
  and the `compose.yaml` of the old final it runs is not this change's.
- The other findings of the report (B-1 password manager, B-3 Codex sandbox in the image,
  B-5 Codex trust prompt, the minor ones): their own tasks.
- Checking the image in `rc_check.py` (docs/release.md: "does not do it yet"): a feature,
  not this fix.
