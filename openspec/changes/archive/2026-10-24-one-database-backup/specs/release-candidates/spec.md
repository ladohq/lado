## ADDED Requirements

### Requirement: upgrade migrates lado.db before it keeps the copy

`upgrade` SHALL read `lado.db`'s schema before `lado update` (read-only; none without a
`lado.db`), and after it, once the RC is installed, run `lado ls` once, so that a
`lado.db` no resumed session migrated is migrated, and its copy written, before the
script looks for it.

#### Scenario: No session ran
- **WHEN** no session runs, the human runs `upgrade 0.38.0rc1`, and 0.38.0rc1 has a newer
  schema
- **THEN** the script's `lado ls` migrates `lado.db`, and `~/.lado-rc/lado.db.0.37.1` is
  a copy of the migration's `backups/lado.db.schema-26`

### Requirement: rollback hands the copy to lado update

When the plan says lado.db will be restored, `rollback` SHALL, after the stops and before
`lado update <final>`, write the copy to `~/.lado/backups/lado.db.schema-<the copy's
schema>` (under `LADO_HOME` when set; beside it, then renamed over a file of that name;
other files stay), and SHALL restore nothing itself: `lado update <final>` warns, asks and
restores (capability update-database).

#### Scenario: The copy goes where lado update looks
- **WHEN** `~/.lado-rc/lado.db.0.37.1` has schema 26 and `backups/` holds only
  `lado.db.schema-27`
- **THEN** before `lado update 0.37.1` runs, `backups/` holds `lado.db.schema-26` (the
  copy's content) and `lado.db.schema-27`

## MODIFIED Requirements

### Requirement: Moving onto a release candidate keeps the final's database

`python3 scripts/rc_check.py upgrade VERSION` SHALL run the human's own `lado update
VERSION` on the terminal, without `--yes`, then read `lado --version`. After a final whose
schema the RC moved, it SHALL copy `backups/lado.db.schema-<the final's schema>` of
`LADO_HOME` to `~/.lado-rc/lado.db.<final>`, the only file there; when the schema did not
move it SHALL keep nothing, saying `lado update <final>` alone goes back; after a
pre-release it SHALL leave `~/.lado-rc/` as it is.

#### Scenario: The first release candidate of a cycle
- **WHEN** LADO 0.37.1 runs with schema 26, the human runs `python3 scripts/rc_check.py
  upgrade 0.38.0rc1` and answers `y` to `lado update`'s question, and 0.38.0rc1 migrates
  `lado.db` to schema 27
- **THEN** LADO is 0.38.0rc1 and `~/.lado-rc/` holds only `lado.db.0.37.1`, a copy of
  the migration's `backups/lado.db.schema-26`

#### Scenario: The next release candidate keeps the final's copy
- **WHEN** LADO 0.38.0rc1 runs and the human runs `upgrade 0.38.0rc2`
- **THEN** `~/.lado-rc/lado.db.0.37.1` stays as it was, although a migration by 0.38.0rc2
  replaced `backups/lado.db.schema-26` with `lado.db.schema-27`

#### Scenario: A release candidate that keeps the schema
- **WHEN** LADO 0.37.1 runs with schema 26 and 0.38.0rc1 has schema 26 too
- **THEN** `~/.lado-rc/` is not changed, and the script says that `lado update 0.37.1`
  alone goes back

### Requirement: upgrade keeps the copy only when the release candidate is installed

When the `lado --version` that `upgrade` reads is not
`VERSION`, it SHALL keep nothing and exit with the update's exit code (1 when that was 0).
When it is `VERSION`, it SHALL keep the copy also when the update exited non-zero
(an update that installed the RC exits 1 when a session did not resume on it), and then
exit with that code, saying that LADO is on `VERSION` now. It SHALL refuse inside an agent
(`LADO_AGENT` set).

#### Scenario: The RC is installed but a session did not resume
- **WHEN** LADO 0.37.1 runs, the human runs `upgrade 0.38.0rc1`, and `lado update`
  installs 0.38.0rc1, which moves the schema, but exits 1 as a session did not resume on it
- **THEN** `~/.lado-rc/` holds `lado.db.0.37.1`, and the script exits 1 saying that LADO
  is 0.38.0rc1 now

#### Scenario: The update did not install the RC
- **WHEN** the human answers `n` to `lado update`'s question, or its installer fails
- **THEN** `lado --version` is still the final, `~/.lado-rc/` is not changed, and the
  script exits with the update's exit code

### Requirement: rollback installs the final, restores lado.db and starts again what ran

On yes `rollback` SHALL run `lado stop --all`, `lado server stop` and `lado update
<final>` (on the terminal, without `--yes`), which restores lado.db when the plan said so;
check that `lado --version` is the final and, when the plan said so, that lado.db's schema
is the copy's; then run `lado start <repo> --name <session> --no-attach` for each planned
session the copy has and `lado ui --no-open` with the server's host and port when it ran.

#### Scenario: Back to the final after a schema migration
- **WHEN** LADO 0.38.0rc1 runs with schema 27, `~/.lado-rc/lado.db.0.37.1` has schema 26,
  session `app` runs, and the human answers `y` to both questions
- **THEN** LADO is 0.37.1, lado.db has schema 26 and the copy's content, session `app`
  runs again, and the UI server runs on its port again when it ran before

#### Scenario: The update back is refused
- **WHEN** the human answers `n` to `lado update <final>`'s own question, or it fails
- **THEN** lado.db is not restored, no session is started, and the script exits 1 naming
  the stopped sessions with the `lado start <repo> --name <session>` that resumes each
