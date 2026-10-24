## Context

`lado doctor` reads `lado.db` without migrating it (`cli.py` leaves `doctor` out of
`runtime.migrate_if_safe`), and its checks that read the database print
`state.connect()`'s `SchemaError` text, written for the processes of a running session.
The fix gives the doctor its own line about the database; the behaviour of every other
command stays as it is.

## Decisions

- D1. The sessions that block a migration come from one function in `runtime.py`
  (`state.pending_migration()` filtered by `tmux.has_session`), which
  `migrate_if_safe` and `doctor.check_database` both call. Why: one source of truth; the
  doctor names exactly the sessions that would refuse `lado ls`.
- D2. The doctor's `lado.db` check reads only: `state.schema_version()` and the function of
  D1 (a read-only connection); never `state.connect()` or `state.migrate()`. Why: the
  doctor must change nothing, also under running sessions.
- D3. The newer and incompatible lines take their words from `state.py` (the refusals'
  text made by one helper used by `state.connect()` and the doctor), not a copy. Why: one
  source; the two cannot drift.
- D4. The `info` line names `lado ls` and `lado start`; `cli.py`'s tuple of commands that
  do not migrate becomes a named module constant, and a unit test asserts `ls` and `start`
  are not in it. Why: the line stays true if that tuple changes, without repeating it in
  the text.
- D5. The checks that read the database (Projects, Artifacts, Agent config folders) map a
  `SchemaError` to `not checked: lado.db is not at this LADO's schema (see lado.db)`
  through one constant of `doctor.py`. Why: the `lado.db` line carries the detail once.
- D6. Test layers: the check's cases at the unit layer (`tests/test_doctor.py`, tmux
  replaced as there); one integration test runs `lado doctor` as a process with real tmux
  and the fake agent on a database turned back by `agent_helpers.previous_schema()`, for
  the no-session and the running-session cases, since the session detection crosses
  processes (tmux).
- D7. A fix: patch level, no version bump here; CHANGELOG under `### Fixed`.
