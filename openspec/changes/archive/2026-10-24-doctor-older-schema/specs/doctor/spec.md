## ADDED Requirements

### Requirement: lado doctor shows an older lado.db and what upgrades it

When `lado.db` has an older schema than this LADO's, `lado doctor` SHALL have a check
`lado.db` right after the `LADO` line: `info`, saying `lado ls` or `lado start` upgrades
it, when no session runs; `warn`, naming the running sessions (those that keep the other
commands from migrating) and saying to stop them with `lado stop --all`, when some run.

#### Scenario: The first doctor after an upgrade
- **WHEN** `lado.db` has schema 34, this LADO knows 35, no session runs, and the human
  runs `lado doctor`
- **THEN** it prints `[info] lado.db: schema 34, this LADO knows 35: lado ls or lado start
  upgrades it (its backup goes to backups/)`, and its exit status is that of the other
  checks

#### Scenario: Sessions of the older LADO still run
- **WHEN** `lado.db` has schema 34, the sessions `a` and `b` run in tmux, and `c` is not
  marked stopped but its tmux session is gone
- **THEN** `lado doctor` prints `[warn] lado.db: schema 34, this LADO knows 35, and the
  sessions "a", "b" run on it` with the hint `stop them with lado stop --all (it upgrades
  lado.db), then lado start`, and `c` is not named

### Requirement: lado doctor shows a newer or incompatible lado.db

When `lado.db` has a newer schema than this LADO's, the check `lado.db` SHALL be `warn`
with the words of the newer-LADO refusal (upgrade LADO); when it is incompatible, `FAIL`
with the words of that refusal, and `lado doctor` SHALL exit 1.

#### Scenario: A database of a newer LADO
- **WHEN** `lado.db` has schema 36 and this LADO knows 35
- **THEN** `lado doctor` prints a `[warn] lado.db:` line that says to upgrade LADO, and its
  exit status is that of the other checks

#### Scenario: An incompatible database
- **WHEN** `lado.db` has tables and a schema version this LADO cannot migrate from
- **THEN** `lado doctor` prints `[FAIL] lado.db:` with the refusal's words and exits 1

### Requirement: lado doctor reads lado.db as it is

`lado doctor` SHALL never migrate or write `lado.db`. At this LADO's schema, or with no
`lado.db`, it SHALL print no `lado.db` line. A check that cannot read `lado.db` because
of its schema SHALL say `not checked: lado.db is not at this LADO's schema (see
lado.db)`, and no line SHALL say that LADO was upgraded under a running session.

#### Scenario: The checks that read lado.db on an older schema
- **WHEN** `lado.db` has schema 34, this LADO knows 35, no session runs, and the human
  runs `lado doctor`
- **THEN** Projects and Artifacts say `not checked: lado.db is not at this LADO's schema
  (see lado.db)`, no line says `upgraded under a running session`, and `lado.db` still
  has schema 34 with nothing written to `backups/`

#### Scenario: The current schema
- **WHEN** `lado.db` has this LADO's schema, or there is no `lado.db`
- **THEN** `lado doctor` prints no `lado.db` line
