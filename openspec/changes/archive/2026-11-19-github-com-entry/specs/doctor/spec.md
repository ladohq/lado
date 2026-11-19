## ADDED Requirements

### Requirement: lado doctor names the GitHub login outside LADO

`lado doctor` SHALL print `[warn] GitHub login outside LADO: <names> set but not used:
github.com takes its token from Settings → Git servers` while a layer or a project's
secret sets a GitHub variable, never a value; `[info]` that `gh`'s own login is not used
while `gh` is logged in; no line otherwise. The exit status SHALL not change.

#### Scenario: The outside folder and a project
- **WHEN** `/run/secrets/GH_TOKEN` is set and project `shop` has the secret `GH_TOKEN`
- **THEN** doctor prints `[warn] GitHub login outside LADO: GH_TOKEN in /run/secrets,
  GH_TOKEN of project shop set but not used: github.com takes its token from Settings → Git
  servers`

#### Scenario: gh logged in
- **WHEN** `gh auth status` says it is logged in to github.com
- **THEN** doctor prints `[info] GitHub login outside LADO: the GitHub CLI's own login is
  not used by agents`

#### Scenario: None
- **WHEN** no GitHub variable is set and `gh` is not logged in
- **THEN** doctor prints no `GitHub login outside LADO` line

### Requirement: lado doctor names the takeover of the GitHub login

`lado doctor` SHALL print `[info] GitHub login: taken over from <source> on <date>` after
the takeover saved a token, `[warn] GitHub login: GitHub refused the token of <source>` for
a refused one, and `[info] GitHub login: taken over at the next lado ui or lado start`
(with why, after a failed `gh`) before it ran.

#### Scenario: Before the first start
- **WHEN** lado.db is at schema 43 and the takeover has not run
- **THEN** doctor prints `[info] GitHub login: taken over at the next lado ui or lado
  start`

#### Scenario: Taken over
- **WHEN** the takeover saved `GH_TOKEN in /run/secrets` on 2026-11-18
- **THEN** doctor prints `[info] GitHub login: taken over from GH_TOKEN in /run/secrets on
  2026-11-18`

### Requirement: A busy lado.db never fails lado doctor's git lines

When lado.db stays locked longer than its 10-second wait, the git server and GitHub lines
SHALL be one `[warn] git servers: not checked: lado.db is busy` line, and the other checks
SHALL follow.

#### Scenario: A locked lado.db
- **WHEN** another process holds lado.db's write lock for longer than 10 seconds
- **THEN** doctor prints `[warn] git servers: not checked: lado.db is busy` and goes on
