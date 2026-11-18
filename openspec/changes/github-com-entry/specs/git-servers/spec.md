## ADDED Requirements

### Requirement: github.com is a git server like any other

`lado git-server add github.com --token` SHALL save github.com as `add` saves any
server, as kind `github` at `https://github.com`, asking `https://api.github.com/user`
alone; `www.github.com` and `api.github.com` SHALL be taken as it, and another port or a
path refused. `list`, `check`, `author` and `remove` SHALL work for it as for any server.

#### Scenario: Adding it
- **WHEN** the human runs `lado git-server add github.com --token` and
  `https://api.github.com/user` answers 200 with `{"login": "octo"}`
- **THEN** it prints `GitHub, signed in as octo` and `lado git-server list` shows
  `https://github.com  GitHub  octo  yes`

#### Scenario: No --kind
- **WHEN** the human runs `lado git-server add github.com --token --kind gitlab`
- **THEN** it is refused and nothing is asked or saved

#### Scenario: Removing it
- **WHEN** the human runs `lado git-server remove github.com`
- **THEN** the entry and its token folder are gone

### Requirement: The GitHub login is taken over once

On the first start of this LADO for a `LADO_HOME` (the UI server's start or a launch of
agents), before any agent starts, LADO SHALL save the GitHub login agents used as the
github.com entry, once, and record it in `lado.db`. An entry already saved SHALL be left
as it is. Nothing outside LADO SHALL be changed.

#### Scenario: A token of the outside folder
- **WHEN** `/run/secrets/GH_TOKEN` holds a token GitHub takes as `octo` and the UI server
  starts for the first time on this LADO
- **THEN** github.com is saved signed in as `octo`, and `/run/secrets/GH_TOKEN` is unchanged

#### Scenario: Once
- **WHEN** the takeover ran and the human then removes github.com and restarts LADO
- **THEN** github.com stays out of the list

#### Scenario: An entry already there
- **WHEN** github.com was saved by hand before the first start
- **THEN** its token, login and author stay as they were

### Requirement: The takeover takes the token agents used

The takeover SHALL take `GH_TOKEN`, else `GITHUB_TOKEN`, of the agents' layers without a
project, else what `gh auth token --hostname github.com` prints; it SHALL check it on
GitHub: saved with its login, saved unchecked when GitHub does not answer in 5 seconds,
not saved when GitHub refuses it. It SHALL record the source in words, never the token.

#### Scenario: gh's login
- **WHEN** no layer sets `GH_TOKEN` or `GITHUB_TOKEN` and `gh auth token --hostname
  github.com` prints a token GitHub takes as `octo`
- **THEN** github.com is saved signed in as `octo` with the source `the GitHub CLI's login`

#### Scenario: No answer
- **WHEN** GitHub does not answer in 5 seconds
- **THEN** github.com is saved not checked, and a later check saves its login

#### Scenario: A refused token
- **WHEN** GitHub answers 401 for the token
- **THEN** no entry is saved, and the record names the source as refused

#### Scenario: Nothing found
- **WHEN** no layer sets either variable and `gh` is not logged in or not installed
- **THEN** no entry is saved, and a later login outside LADO is not taken over

### Requirement: A takeover that could not read gh's login runs again

When `gh auth token` fails for another reason than no login (a keychain closed to the
process, a crash) or runs longer than 10 seconds, the takeover SHALL record nothing and
run again at the next start; `lado doctor` SHALL say it is pending and why.

#### Scenario: A keychain closed to an ssh session
- **WHEN** `gh auth token` exits 1 with a keychain error on the first start
- **THEN** nothing is recorded, and the next start runs the takeover again

### Requirement: The takeover says what it did

The command or server that took the login over SHALL print or log one line: `LADO took
your GitHub login (<source>) into Settings → Git servers: github.com, signed in as
<login>.` (`not checked yet` for no answer); for a refused token, `GitHub refused the token
of <source>: add github.com in Settings → Git servers.`

#### Scenario: Taken over by lado start
- **WHEN** `lado start` takes over `GH_TOKEN of your shell` as `octo`
- **THEN** it prints `LADO took your GitHub login (GH_TOKEN of your shell) into Settings →
  Git servers: github.com, signed in as octo.`

#### Scenario: A refused token
- **WHEN** GitHub refuses the token of `GH_TOKEN in /run/secrets` on the UI server's start
- **THEN** its log has `GitHub refused the token of GH_TOKEN in /run/secrets: add github.com
  in Settings → Git servers.`

### Requirement: Agents get no GitHub variable from outside LADO

An agent's launch and LADO's own git SHALL drop `GH_TOKEN`, `GITHUB_TOKEN`,
`GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`, `GH_HOST` and `GH_CONFIG_DIR` from every
layer (login shell, outside folder, project), and give `GH_CONFIG_DIR` an empty folder of
LADO's own, so `gh` sees neither an outside token nor its own login.

#### Scenario: The outside token changed
- **WHEN** github.com is saved as `octo` and the human puts another token into
  `/run/secrets/GH_TOKEN`
- **THEN** a new agent's `gh` and `git` still use the entry's token

#### Scenario: Removed with gh logged in
- **WHEN** github.com has no entry and `gh auth login` was done outside LADO
- **THEN** an agent's `gh auth status` says it is not logged in

### Requirement: gh gets the token of the github.com entry

An agent's launch SHALL set `GH_TOKEN` to the github.com entry's token when it is saved
with its token file, and none otherwise.

#### Scenario: An agent runs gh
- **WHEN** github.com is saved and an agent runs `gh api user`
- **THEN** the request carries the entry's token

### Requirement: gh gets the token of a GitHub Enterprise server

An agent's launch SHALL set `GH_ENTERPRISE_TOKEN` to the token of the GitHub Enterprise
entry that holds the session repository's `origin`, else of the only one saved, and
`GH_HOST` to that server's host for the repository's server only.

#### Scenario: A pull request on GitHub Enterprise
- **WHEN** the session's repository is on the saved `https://ghe.corp.example` and an agent
  runs `gh api -X POST repos/team/app/pulls`
- **THEN** the request reaches `ghe.corp.example` with that entry's token

#### Scenario: Two servers, the repository on neither
- **WHEN** two GitHub Enterprise servers are saved and the repository is on neither
- **THEN** the agent has no `GH_ENTERPRISE_TOKEN` and no `GH_HOST`

### Requirement: The schema keeps the takeover's record

From schema 43 `lado.db` SHALL keep the takeover's record (when, the source, the
outcome), apart from the github.com entry, so a removal never makes it run again. A `lado.db` of
schema 42 SHALL be upgraded with its servers kept and no record, so the takeover runs.

#### Scenario: Upgrading from schema 42
- **WHEN** a `lado.db` of schema 42 with a saved GitLab server is upgraded
- **THEN** it is at schema 43, the server is kept, and `backups/lado.db.schema-42` holds the
  database as it was

#### Scenario: Rolling back after the takeover
- **WHEN** the takeover saved github.com and `backups/lado.db.schema-42` is put back
- **THEN** no github.com entry is there, and `/run/secrets/GH_TOKEN` and `gh`'s login are
  as before

## MODIFIED Requirements

### Requirement: The kind of a server is told by its API

LADO SHALL ask each kind's API at once, one request per kind, each cut at 5 seconds and
following no redirect: GitLab's `<address>/api/v4/user` with the header `PRIVATE-TOKEN`,
GitHub's `<address>/api/v3/user` (github.com: `https://api.github.com/user`, the only
request) with `Authorization: token <token>`. A kind SHALL be recognised by 200 with a JSON
object holding a string `username` (GitLab) or `login` (GitHub).

#### Scenario: Both asked, one answers
- **WHEN** a server answers `/api/v4/user` with 200 and a `username`, and `/api/v3/user`
  with 404
- **THEN** it is GitLab

#### Scenario: Two kinds recognised
- **WHEN** both requests are recognised
- **THEN** nothing is saved without `--kind`, and the refusal names both kinds

#### Scenario: A redirect
- **WHEN** the server answers both with 302 to `https://sso.corp.ru/login`
- **THEN** nothing is saved, the refusal names the redirect's target, and no request is
  sent to `sso.corp.ru`

#### Scenario: github.com
- **WHEN** github.com is added
- **THEN** only `https://api.github.com/user` is asked

### Requirement: A git server's token is asked and kept in its own file

The token SHALL be kept in `<LADO_HOME>/git-servers/<id>/token`, the folders mode 700 and
the file mode 600 whatever the umask, written whole by a rename, refusing a symbolic link
on the way. Its value SHALL appear in no output, log, error journal, `lado.db`, git config
file, agent's working copy, or other file under `LADO_HOME`, but a GitHub entry's in the
agent's launch file, removed when read.

#### Scenario: A token piped in
- **WHEN** the human runs `printf '%s' "$TOKEN" | lado git-server add gitlab.corp.ru --token`
  and the server accepts it
- **THEN** `<LADO_HOME>/git-servers/<id>/token` holds it with mode 600 in a folder of mode
  700, and neither the output, `lado.db`, the error journal nor any other file of
  `LADO_HOME` holds its value

#### Scenario: The GitHub token of a running agent
- **WHEN** github.com is saved and an agent has started
- **THEN** no file under `LADO_HOME` but the token file holds the token

## REMOVED Requirements

### Requirement: github.com is not added

**Reason**: github.com is now a saved server like any other; the human decided that access
to git servers is configured only in LADO's settings (#7389).
**Migration**: the GitHub login of `GH_TOKEN` or `gh auth login` is taken over once into the
github.com entry (`The GitHub login is taken over once`).
