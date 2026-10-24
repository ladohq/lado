Task: LAD-141

## Why

Symptom: after an upgrade of LADO with a schema change (0.42.0 to 0.43.0, schema 31 to
35), the first `lado doctor`, with no session running, prints

```
[info] Projects: not checked: <home>/lado.db has schema version 31 and this LADO knows 35: LADO was upgraded under a running session. Run `lado stop --all`, then `lado start`; ...
[info] Artifacts: not checked: <same text>
```

No session runs, so the human gets a false diagnosis and a needless command.

Cause (reproduced): `lado doctor` does not migrate `lado.db` on purpose (`cli.py`: it
checks the environment as it is, a migration due included), so its checks that read the
database meet `state.connect()`'s `SchemaError`. Its text for an older schema is written
for the processes of a running session (hooks, `lado mcp`, the session loop), which never
migrate and for which it is true. The checks Projects and Artifacts print that text as
it is; Project variables and Project secrets drop their line silently. No line of
`lado doctor` says what is true: the database is older and `lado ls` or `lado start`
upgrades it, or the sessions named keep it from being upgraded.

Options weighed:
- A: `lado doctor` migrates as the other commands do. Cheap, but the diagnostic starts
  changing the database, and while a session runs it would be refused as a whole (no
  migration under a running session): no doctor exactly when it is needed.
- B (taken, the human's choice, question #1441, with the supervisor's recommendations,
  message #1448): `lado doctor` stays read-only and has one line `lado.db` that says the
  truth: the schema it has and this LADO's, and whether `lado ls` or `lado start`
  upgrades it or which running sessions keep it from that. The checks
  that read the database say they were not checked because of it. The sessions that
  block a migration are found by the same function `migrate_if_safe` uses: one source of
  truth. Small and lasting; nothing else changes.
- C: one neutral `SchemaError` text for every caller. The cheapest, but the hooks, `lado
  mcp` and the loop lose the precise "upgraded under a running session", which is true
  there.

## What Changes

- `lado doctor` gets a check `lado.db`, shown only when `lado.db` is not at this LADO's
  schema: `info` when it is older and no session runs (`lado ls` or `lado start` upgrades
  it), `warn` when it is older and sessions run (it names them and says to stop them),
  `warn` when it is newer (upgrade LADO), `FAIL` when it is incompatible (exit 1).
- Projects and Artifacts on such a database say `not checked: lado.db is not at this
  LADO's schema (see lado.db)` instead of `SchemaError`'s text.
- `lado doctor` still never migrates or writes `lado.db`.
- New visible behaviour: on an incompatible `lado.db`, `lado doctor` exits 1 (today it
  says `not checked` and passes).
- `docs/cli.md` (the `lado doctor` paragraph) and CHANGELOG.md (`### Fixed` under
  `## 0.43.0 (unreleased)`: the truthful line, and exit 1 on an incompatible `lado.db`).

## Scope

`src/lado/doctor.py`, `src/lado/runtime.py` (the sessions that block a migration, shared
by `migrate_if_safe` and the doctor), `src/lado/cli.py` (the tuple of commands that do
not migrate, named), `tests/test_doctor.py`, `tests/test_runtime.py`,
an integration test, the spec delta (`doctor`), `docs/cli.md`, CHANGELOG.md.

## Out of scope

- Migrating in `lado doctor` (option A): a diagnostic that changes the database, and is
  refused while a session runs.
- Changing `SchemaError`'s text in `state.connect()` (option C): true for every caller
  that meets it with a running session.
- `lado bug-report`, the UI's System panel: they report the schema number and say nothing
  false; the UI server migrates when it starts.
- Project variables and Project secrets: on another schema they show no line, as today;
  the `lado.db` line now says why there is nothing to read.
- A `lado.db` line when the schema is current (the human's choice, question #1441): the
  report of `lado bug-report` and the System panel already show the number.
- Listing in the `info` line every command that does not migrate (`doctor`, `bug-report`,
  `telemetry`, `uninstall`, `stop` under running sessions): two commands that do are
  enough to act on, and the list would be a second copy of `cli.py`'s.

## Acceptance criteria

- AC-1: `lado.db` at schema 34 (this LADO 35), no session running: `lado doctor` prints
  `[info] lado.db: schema 34, this LADO knows 35: lado ls or lado start upgrades it (its
  backup goes to backups/)` right after the `LADO` line,
  Projects and Artifacts say `not checked: lado.db is not at this LADO's schema (see
  lado.db)`, no line holds `upgraded under a running session`, the exit status is that of
  the other checks, and `lado.db` still has schema 34 with no backup made.
- AC-2: the same with sessions `a` and `b` running in tmux (and `c` marked running in
  `lado.db` but gone from tmux): `[warn] lado.db: schema 34, this LADO knows 35, and the
  sessions "a", "b" run on it` and the hint `stop them with lado stop --all (it upgrades
  lado.db), then lado start`; `c` is not named.
- AC-3: a newer `lado.db` (schema 36): `[warn] lado.db:` with the newer-LADO words
  (upgrade LADO); an incompatible one: `[FAIL] lado.db:` and exit 1.
- AC-4: `lado.db` at the current schema, or none: no `lado.db` line.
- AC-5: `lado ls` and `lado stop` still refuse or migrate as before (`migrate_if_safe`
  unchanged in behaviour, its tests green).
- AC-6: the command the `info` line names migrates: `ls` and `start` are not among the
  commands `cli.py` keeps from migrating (a unit test against that one tuple).
- AC-7: `make lint`, `make test`, the new integration test with `-m integration` pass;
  `openspec validate doctor-older-schema --strict` passes; CI green on the pull request's
  last commit.

## Impact

- CLI output of `lado doctor` only: no API, MCP, schema or kit change. A fix: patch level;
  the version is not bumped here.
- Living spec: `doctor` (a requirement added).
