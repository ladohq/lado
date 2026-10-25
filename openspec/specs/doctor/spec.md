# doctor Specification

## Purpose
What `lado doctor` and the UI's System panel check and show about the machine LADO runs
on, so the human sees what is missing before a session fails on it.

## Requirements

### Requirement: lado doctor checks git

`lado doctor` SHALL have a `git` check, after `tmux`, by the same look as the folder check
(`git --version` on the PATH of its process): `FAIL` when git is not found (with the
`no_git` hint for this OS) or does not run (with git's first line and the `git_broken`
hint); `WARN` when its version is older than 2.31, saying that the folder-trust lookup of
the providers (`git rev-parse --path-format=absolute`) needs 2.31; `OK` with the version
otherwise.

#### Scenario: git missing
- **WHEN** no git is on PATH
- **THEN** the `git` line is `[FAIL]` with the install hint, and `lado doctor` exits 1

#### Scenario: The macOS stub
- **WHEN** `git --version` fails
- **THEN** the `git` line is `[FAIL]` with `git does not run: <its first line>` and
  `xcode-select --install`

#### Scenario: An old git
- **WHEN** `git --version` reports 2.30.2
- **THEN** the `git` line is `[warn]` naming 2.31 as the version LADO needs, and the
  exit status is that of the other checks

#### Scenario: A current git
- **WHEN** `git --version` reports 2.47.1
- **THEN** the `git` line is `[ok  ]` with `git version 2.47.1`

### Requirement: The System panel shows git

The UI's system facts (`GET /api/system`, `doctor.system_info`) SHALL carry git's version,
or `not installed` / `does not run`, never its path; the System panel SHALL show it as a
`git` row beside `tmux`, and the issue report (`doctor.report`) SHALL have a `- git: ...`
line.

#### Scenario: The panel names git's version
- **WHEN** the human opens the System panel on a machine with git 2.47.1
- **THEN** it shows a row `git` with `2.47.1`, and the copied report has `- git: 2.47.1`

#### Scenario: No git
- **WHEN** the server finds no git
- **THEN** the row shows `not installed`

### Requirement: lado doctor checks git's author

`lado doctor` SHALL have a check `git author`, after `git`, by the same look as a fresh
start (`scratch.author_problem`, git's `user.name` and `user.email` outside any
repository): `OK` with `user.name and user.email set` when both are, `WARN` with `no
user.name or user.email: agents cannot commit` and the fresh start's hint (in LADO's
container the `.env` one, elsewhere the `git config --global` one) otherwise, and no line
when git itself does not run (the `git` check says why).

#### Scenario: A machine whose git knows the author
- **WHEN** git's global config has `user.name` and `user.email`
- **THEN** `lado doctor` prints `[ok  ] git author: user.name and user.email set`

#### Scenario: A fresh machine
- **WHEN** git has no `user.email`
- **THEN** `lado doctor` prints `[warn] git author: no user.name or user.email: agents
  cannot commit` with the `git config --global` command, and its exit status is that of
  the other checks

### Requirement: The git author check names no one and keeps the exit status

The `git author` check SHALL never print the name or the email, and the check SHALL NOT
change the exit status.

#### Scenario: The author stays out of the output
- **WHEN** git's global config has `user.name` `Ann Lee` and `user.email`
  `ann@example.com`
- **THEN** no line of `lado doctor` holds `Ann Lee` or `ann@example.com`, and the exit
  status is that of the other checks

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
