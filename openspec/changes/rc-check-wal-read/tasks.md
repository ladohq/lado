## 1. rc_check reads a WAL database at rest

- [x] 1.1 `tests/test_rc_check.py` (unit: the script's own reads, no LADO needed):
  `make_db(..., wal=True)` sets `PRAGMA journal_mode=WAL` and, after close, asserts no
  `-wal` / `-shm` is left beside it (a database at rest). Two tests:
  `upgrade` over a WAL `lado.db` at rest reads its schema (the existing `final`
  fixture's database made WAL), and `rollback`'s plan over WAL `lado.db` and kept copy
  at rest names both schemas and the sessions, after which `~/.lado-rc/` holds only
  `lado.db.0.37.1` and `LADO_HOME` no `lado.db-wal` / `lado.db-shm`. Red before 1.2: on
  Linux `mode=ro` leaves the side files behind (macOS raises instead, the bug as seen).
- [x] 1.2 `scripts/rc_check.py`: `_read_only()` becomes `_reading()`, an ordinary
  `sqlite3.connect(path)` in `contextlib.closing`, its docstring saying why not
  `mode=ro` (a WAL database at rest has no `-shm`, and macOS's SQLite will not make one
  read-only) and why not `immutable=1` (it ignores the WAL of a running LADO); callers
  renamed. 1.1 passes; `make lint`, `make test`.
- [x] 1.3 `_reading()` sets `PRAGMA query_only = ON` after connect (the supervisor's
  note at the gate): a unit test that a write through it to the kept copy is refused and
  the copy keeps its sessions, red before.

## 2. The image's checklist names git's identity

- [x] 2.1 docs/release.md, 4.5: the `.env` heredoc gains `LADO_GIT_NAME="RC Check"` and
  `LADO_GIT_EMAIL=rc-check@example.com` (after `LADO_PORT`), and the sentence on
  `docker compose logs lado` says it has no warning about `LADO_REPOS` nor about git's
  identity.

## 3. Regression

- [ ] 3.1 `make lint`, `make test`, `openspec validate rc-check-wal-read --strict`,
  `openspec validate --specs --strict`; the pull request's CI.
