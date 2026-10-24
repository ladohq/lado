## 1. The sessions that block a migration

- [x] 1.1 `src/lado/runtime.py`: one function gives the schema version of an older
  `lado.db` and the sessions that keep it from being migrated (`state.pending_migration`'s
  sessions that `tmux.has_session` finds), None when nothing is to migrate;
  `migrate_if_safe` uses it, its refusal unchanged. The existing `migrate_if_safe` tests
  in `tests/test_runtime.py` stay green unchanged (AC-5); a unit test of the new function:
  a session marked running but gone from tmux is not among them (D1).
- [x] 1.2 `src/lado/cli.py`: the tuple of commands that do not migrate becomes a named
  module constant, used where it is today; a unit test asserts `ls` and `start` are not
  in it (AC-6, D4).
- [x] 1.3 `src/lado/state.py`: the newer and incompatible refusals' text comes from one
  helper that `connect()` and the doctor use (D3); `connect()`'s messages unchanged.

## 2. The doctor

- [x] 2.1 `src/lado/doctor.py`: `check_database()` (name `lado.db`) by the delta's three
  requirements: reads only (`state.schema_version`, the function of 1.1), None at the current schema or with no
  `lado.db`; the newer and incompatible lines take their words from 1.3; incompatible
  is `FAIL`. `run_checks` puts it right after `check_lado()`.
- [x] 2.2 `check_projects` and `check_artifacts`: on a `SchemaError` they say `not
  checked: lado.db is not at this LADO's schema (see lado.db)`; `check_config_folders`
  likewise for a `SchemaError` (its tmux error keeps its text); one constant (D5).
- [x] 2.3 `tests/test_doctor.py` (unit, tmux replaced as in the module's other tests):
  older schema with no session, with two running and one gone from tmux, newer (36),
  incompatible (`FAIL`, `doctor.main()` returns 1), current, no `lado.db` (AC-1 to
  AC-4); each asserts `lado.db`'s schema is unchanged and `backups/` empty, and the first that no line of `doctor.main()`'s output
  holds `upgraded under a running session`. Adapt
  `test_artifacts_are_not_checked_on_another_schema` to the new text. Each new test fails
  before 2.1/2.2.

## 3. End to end

- [x] 3.1 `tests/integration/` (the module that runs the CLI against a real tmux server;
  the doctor's file if there is one): `agent_helpers.previous_schema()`, no session, `lado
  doctor` as a process: the `[info] lado.db:` line, no `upgraded under a running
  session`, schema unchanged (AC-1); then a session started with the fake agent and the
  database turned back: the `[warn]` line names it (AC-2). Run with `-m integration`.

## 4. Documents

- [x] 4.1 `docs/cli.md`, the `lado doctor` paragraphs: the `lado.db` line, when it shows,
  and that doctor never migrates.
- [x] 4.2 CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`: `lado doctor` after
  an upgrade no longer says LADO was upgraded under a running session; it says the
  database waits for its upgrade and what to do; on an incompatible `lado.db` it now
  fails (exit 1).

## 5. Checks

- [x] 5.1 `make lint`, `make test`, `uv run pytest -m integration -n auto <the changed
  integration file>` pass; `openspec validate doctor-older-schema --strict` passes; CI
  green on the pull request's last commit (AC-7).
