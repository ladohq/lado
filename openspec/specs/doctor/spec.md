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
the providers (`git rev-parse --path-format=absolute`) and git servers
(`lado git-server`) need 2.31; `OK` with the version otherwise.

#### Scenario: git missing
- **WHEN** no git is on PATH
- **THEN** the `git` line is `[FAIL]` with the install hint, and `lado doctor` exits 1

#### Scenario: The macOS stub
- **WHEN** `git --version` fails
- **THEN** the `git` line is `[FAIL]` with `git does not run: <its first line>` and
  `xcode-select --install`

#### Scenario: An old git
- **WHEN** `git --version` reports 2.30.2
- **THEN** the `git` line is `[warn]` naming 2.31 as the version LADO needs, the hint names
  git servers among what needs it, and the exit status is that of the other checks

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

`lado doctor` SHALL have a check `git author`, after `git`, by the same order as a fresh
start outside a project (capability commit-authors): `OK` with `LADO's commit author set` or `user.name and
user.email set`, else `WARN` with `no LADO commit author and no user.name or user.email:
agents cannot commit` and the fresh start's hint, and no line when git itself does not run
(the `git` check says why).

#### Scenario: A machine whose git knows the author
- **WHEN** git's global config has `user.name` and `user.email` and LADO has no author
- **THEN** `lado doctor` prints `[ok  ] git author: user.name and user.email set`

#### Scenario: LADO's author
- **WHEN** LADO's commit author is set and git has no `user.name`
- **THEN** `lado doctor` prints `[ok  ] git author: LADO's commit author set`

#### Scenario: A fresh machine
- **WHEN** git has no `user.email` and LADO has no author
- **THEN** `lado doctor` prints `[warn] git author: no LADO commit author and no user.name
  or user.email: agents cannot commit` with the `lado git-server author` command, and its
  exit status is that of the other checks

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

### Requirement: Only folders count as agent config folders

`lado doctor`'s check `Agent config folders` SHALL count as a session's or an agent's config
folder only a folder under `LADO_HOME/agents/` (or under a session's folder there) whose name
does not start with `.`; files and hidden names SHALL be neither listed nor offered for
removal.

#### Scenario: Finder's .DS_Store
- **WHEN** `LADO_HOME/agents/` holds the file `.DS_Store`, and `LADO_HOME/agents/s/` of a
  running session `s` holds `.DS_Store` beside its running agents' folders
- **THEN** the check is `[ok  ]` "only those of running agents"

#### Scenario: A folder left beside a file
- **WHEN** `LADO_HOME/agents/` holds `.DS_Store`, a file `notes`, and the folder `old` of a
  session that does not run
- **THEN** the check warns with `LADO_HOME/agents/old` alone, and its `rm -rf` names only it

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

### Requirement: lado doctor names a git server's certificate

doctor's line of a saved server SHALL be `warn` with the check's line for a certificate not
trusted, changed or one trust cannot fix, with the hint `trust it: lado git-server check
<address>, or Check in Settings → Git servers` (the check's own hint for one trust cannot
fix), never asking to trust; a GitHub server with a certificate SHALL get an `info` line that
`gh` does not get it.

#### Scenario: Not trusted
- **WHEN** `https://gitlab.corp.example`'s certificate is not trusted
- **THEN** doctor prints `[warn] git server https://gitlab.corp.example: the certificate of
  https://gitlab.corp.example is not trusted` with the hint, and saves nothing

#### Scenario: GitHub Enterprise with a certificate
- **WHEN** `https://ghe.corp.example` (GitHub) works with its certificate
- **THEN** doctor prints its `ok` line and `[info] gh: does not get the certificate of
  https://ghe.corp.example: agents' gh cannot reach it; git can`

### Requirement: lado doctor checks the tool of each saved server's kind

`lado doctor` SHALL print, after the `git server` lines, one line per tool of the saved
servers' kinds, named by the tool: `ok` with its version on the agents' PATH, `warn` when it
is missing or older than its kind's oldest, with what to install. It SHALL never fail for it,
and print no such line with no saved server.

#### Scenario: glab in the image
- **WHEN** a GitLab server is saved and `glab` 1.130.0 is on the agents' PATH
- **THEN** doctor prints `[ok  ] glab: glab 1.130.0`

#### Scenario: glab missing
- **WHEN** a GitLab server is saved and no `glab` is on the agents' PATH
- **THEN** doctor prints `[warn] glab: not on the agents' PATH: agents cannot open merge
  requests on https://gitlab.corp.example` with the hint `install glab 1.114.0 or newer`,
  and the exit status does not change

#### Scenario: Only GitHub saved
- **WHEN** only github.com is saved
- **THEN** doctor prints a `gh` line and no `glab` line

### Requirement: lado doctor names the GitLab login outside LADO

`lado doctor` SHALL print `[warn] GitLab login outside LADO: <names> set but not used: a
GitLab takes its token from Settings → Git servers` while a layer or a project's secret sets
a dropped GitLab variable, never a value; `[warn]` that `OAUTH_TOKEN`, which agents keep,
reaches their glab while a layer or a project sets it; `[info]` that `glab`'s own login is not
used while the human's `glab` configuration holds a token or a keyring login; no line
otherwise.

#### Scenario: A token in the shell
- **WHEN** the login shell sets `GITLAB_TOKEN`
- **THEN** doctor prints `[warn] GitLab login outside LADO: GITLAB_TOKEN of your shell set
  but not used: a GitLab takes its token from Settings → Git servers`

#### Scenario: An OAuth token in the shell
- **WHEN** the login shell sets `OAUTH_TOKEN`
- **THEN** doctor prints `[warn] GitLab login outside LADO: OAUTH_TOKEN of your shell reaches
  agents: their glab sends it to a GitLab not in Settings → Git servers (gitlab.com by
  default)` with the hint `remove it from the agents' environment unless another tool needs
  it`

#### Scenario: glab logged in
- **WHEN** the human's `glab` configuration holds a token for `gitlab.com`
- **THEN** doctor prints `[info] GitLab login outside LADO: the GitLab CLI's own login is not
  used by agents`

#### Scenario: None
- **WHEN** no GitLab variable is set and the human's `glab` holds no login
- **THEN** doctor prints no `GitLab login outside LADO` line

### Requirement: lado doctor warns of a GitLab token without api

doctor's line of a saved GitLab whose check works but whose token lacks `api` SHALL be
`warn` with the check's line and the hint `replace it with a token with the scope api: lado
git-server add <address> --token`; the exit status SHALL not change.

#### Scenario: A token for git alone
- **WHEN** `https://gitlab.corp.example`'s token has `read_repository, write_repository,
  read_api`
- **THEN** doctor prints `[warn] git server https://gitlab.corp.example: Works: GitLab, signed
  in as a.sample, may clone and push; glab cannot open merge requests: the token lacks api.`
  with that hint
