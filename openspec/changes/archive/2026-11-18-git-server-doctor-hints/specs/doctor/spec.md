## ADDED Requirements

### Requirement: lado doctor checks each saved git server

`lado doctor` SHALL print one line per saved git server, after `git author`, named `git
server <address>`: `ok` with the check's line when it works, `warn` with its line and hint
otherwise, by the same check as `lado git-server check`. With no saved server it SHALL print
no such line; with lado.db not at this LADO's schema, one `git servers` line `not checked`.

#### Scenario: A server that works and one whose token was revoked
- **WHEN** `https://gitlab.corp.example` works for `a.sample` and the token of
  `https://ghe.corp.example` is refused
- **THEN** doctor prints `[ok  ] git server https://gitlab.corp.example: Works: GitLab,
  signed in as a.sample, may clone and push.` and `[warn] git server
  https://ghe.corp.example: GitHub refused the token: it expired or was revoked` with the
  hint `replace it: lado git-server add https://ghe.corp.example --token`

#### Scenario: No saved server
- **WHEN** no git server is saved
- **THEN** doctor prints no `git server` line

#### Scenario: lado.db at another schema
- **WHEN** lado.db is at an older schema than this LADO's
- **THEN** doctor prints `[info] git servers: not checked: lado.db is not at this LADO's
  schema (see lado.db)` and asks no server

### Requirement: A git server's failure never fails lado doctor

A git server's line SHALL never be `FAIL` and SHALL NOT change doctor's exit status: a
server that does not answer, a missing token file or a saved address this LADO no longer
takes SHALL be its own `warn` line, and the other lines SHALL follow. The servers SHALL be
asked at once, so doctor waits about one check's time (at most about 10 s) for all of them.

#### Scenario: A server that does not answer
- **WHEN** one of two saved servers does not answer in 5 seconds
- **THEN** its line is `[warn]` with `does not answer` and the reach hint, the other
  server's line follows, and the exit status is that of the other checks

#### Scenario: A missing token file
- **WHEN** a saved server's token file is gone
- **THEN** its line is `[warn] git server <address>: the token file of <address> is
  missing` with `replace it: lado git-server add <address> --token`, and no request is sent
  to it

### Requirement: lado doctor's check of a git server writes nothing

Doctor's check of a git server SHALL write nothing to lado.db, also when it works and the
saved login differs from the one it saw, as doctor never writes lado.db.

#### Scenario: A server saved without a check
- **WHEN** doctor checks a server saved with `--kind` and it works as `a.sample`
- **THEN** its line says it works, and `lado git-server list` still says `not checked`
