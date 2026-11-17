## ADDED Requirements

### Requirement: lado git-server check checks a saved server again

`lado git-server check <address>` SHALL ask the saved server of the address's host and
port with its saved token as `add` does, judge the answers by its saved kind, and print one
line of what it found, storing nothing but the login of a passing check. Exit status SHALL be 0 when
the server works; 1 for any other outcome, for an address that is no saved server's and for
a missing token file, with no request sent for those two; 2 for an address it does not take.

#### Scenario: A server that works
- **WHEN** `https://gitlab.corp.ru` is saved as GitLab and the human runs
  `lado git-server check gitlab.corp.ru`, and the server answers `/api/v4/user` with
  `{"username": "ivan.petrov"}` and the token's own information with the scopes
  `read_repository, write_repository, read_api`
- **THEN** stdout is `Works: GitLab, signed in as ivan.petrov, may clone and push.` and the
  exit status is 0

#### Scenario: An expired token
- **WHEN** `https://gitlab.corp.ru` is saved as GitLab and the server answers the saved token
  with its own 401: `{"message": "401 Unauthorized"}`, or `{"error": "invalid_token",
  "error_description": …}` for a revoked or expired token
- **THEN** stderr has `lado: GitLab refused the token: it expired or was revoked` and the hint
  `replace it: lado git-server add https://gitlab.corp.ru --token`, and the exit status is 1

#### Scenario: A revoked GitHub token
- **WHEN** `https://ghe.corp.ru` is saved as GitHub and the server answers the saved token
  with GitHub's 401 `{"message": "Bad credentials", "documentation_url": …}`
- **THEN** stderr has `lado: GitHub refused the token: it expired or was revoked` and the hint
  `replace it: lado git-server add https://ghe.corp.ru --token`, and the exit status is 1

#### Scenario: No such server
- **WHEN** no server is saved for `git.lan` and the human runs `lado git-server check git.lan`
- **THEN** stderr has `lado: https://git.lan is no saved git server` with the hint
  `see them: lado git-server list`, no request is sent, and the exit status is 1

#### Scenario: The token file is missing
- **WHEN** the server's token file is gone from `LADO_HOME`
- **THEN** no request is sent, stderr says its token file is missing with the hint
  `replace it: lado git-server add https://gitlab.corp.ru --token`, and the exit status is 1

### Requirement: A check names each outcome in one line

A check SHALL tell these outcomes apart, each in one line with a hint where there is a way
out: the server works; the kind refuses the token; the token lacks a right agents need; the
server does not answer (the reasons of `add`); its certificate is not trusted; a redirect,
with no request sent to its target; an answer of another kind than the saved one; an answer
of neither kind (`it answers as neither GitHub nor GitLab`).

#### Scenario: A token without the push right
- **WHEN** a GitLab token's scopes are `read_repository, read_api`
- **THEN** stderr has `lado: the token lacks write_repository: agents can clone but not push`
  with the hint naming the scopes a token needs and `lado git-server add <address> --token`;
  a token without `read_repository` too gets `…: agents can neither clone nor push`

#### Scenario: An untrusted certificate
- **WHEN** the TLS handshake fails because the server's certificate is signed by an authority
  this machine does not trust
- **THEN** stderr has `lado: the certificate of https://gitlab.corp.ru is not trusted` with
  the hint `ask your IT department to make this computer trust it (with LADO in Docker, its
  container), then check again`, not that the server does not answer

#### Scenario: A redirect
- **WHEN** `/api/v4/user` answers 302 to `https://sso.corp.ru/login`
- **THEN** stderr has `lado: it redirects to https://sso.corp.ru/login: add that address
  instead` and no request reaches `sso.corp.ru`

#### Scenario: Another kind
- **WHEN** a server saved as GitHub answers GitHub's path with 404 and GitLab's with a
  `username`
- **THEN** stderr has `lado: it answers as GitLab, not GitHub: remove it and add it again`,
  and the saved kind is unchanged

#### Scenario: No answer
- **WHEN** the server does not answer in 5 seconds
- **THEN** stderr has `lado: gitlab.corp.ru does not answer: it did not answer in 5 s`
  and the exit status is 1

### Requirement: A token's rights are read from the server

A check, and an `add` the server answers, SHALL read the token's rights: the `scopes` of
GitLab's `<address>/api/v4/personal_access_tokens/self`, where a token needs
`read_repository` and `write_repository` (or `api`, which holds them); GitHub's
`X-OAuth-Scopes` header of the user answer, where it needs `repo`. A token whose server does
not tell its rights SHALL count as working, said as `the token's rights are not checked`.

#### Scenario: A GitHub classic token without repo
- **WHEN** GitHub's user answer carries `X-OAuth-Scopes: read:org`
- **THEN** the check says the token lacks `repo`

#### Scenario: A fine-grained GitHub token
- **WHEN** GitHub's user answer is 200 with a `login` and no `X-OAuth-Scopes` header
- **THEN** stdout is `Works: GitHub, signed in as ivan; the token's rights are not checked.`
  and the exit status is 0

#### Scenario: An older GitLab
- **WHEN** `/api/v4/personal_access_tokens/self` answers 404
- **THEN** the check works with `the token's rights are not checked`

### Requirement: A passing check saves the login it saw

A check that passes SHALL save the login it saw in the server's row, so a server saved
without a check is no longer `not checked`; a check with any other outcome SHALL change
nothing saved.

#### Scenario: A server saved without a check
- **WHEN** `https://git.lan` was saved with `--kind gitlab` and a later check works,
  signed in as `ivan`
- **THEN** `lado git-server list` shows `GitLab  ivan` for it

#### Scenario: A failed check
- **WHEN** a check of a server with the login `ivan` finds the token refused
- **THEN** the server keeps the login `ivan`, its kind and its token

### Requirement: A token without a right agents need is saved with a warning

`add`, when the server accepts the token but the token lacks a right agents need, SHALL save
the server and warn `the token lacks <scopes>: agents can clone but not push` (or `…neither
clone nor push`), with the hint how to replace it and the scopes a token needs.

#### Scenario: A GitLab token without write_repository
- **WHEN** the human adds `gitlab.corp.ru` with a token whose scopes are `read_repository,
  read_api`
- **THEN** the server is saved, stderr has the warning that the token lacks
  `write_repository`, and the exit status is 0

### Requirement: Saving and removing a server are done one at a time

Saving a server (an add or a replacement) and removing one SHALL hold one lock of
`LADO_HOME`, from reading the saved server to writing its token file, so a removal and a
replacement of the same server never leave a token without a row or a row without its
token; the command and the Settings page alike.

#### Scenario: A removal during a replacement
- **WHEN** a replacement of `https://gitlab.corp.ru` is saving its token and a removal of it
  starts
- **THEN** the removal waits and then removes the server with its folder, or the
  replacement finds the server gone and saves it anew; either way the row and the token
  file agree

### Requirement: An https remote's letter case and default port keep its author

A repository whose https or http remote on a server with an author is written with its host
in another letter case or with its scheme's own port (`:443`, `:80`) SHALL get that author
as the address as saved does.

#### Scenario: A remote with another letter case or its port written out
- **WHEN** `https://gitlab.corp.ru` has an author and a repository's remote is
  `https://GitLab.Corp.ru/team/app.git` or `https://gitlab.corp.ru:443/team/app.git`
- **THEN** the agent's commit there carries the server's author

### Requirement: An address with a space or a stray character is refused

`add`, `check`, `author` and `remove` SHALL refuse with exit 2 an address with a space, tab
or control character anywhere, or a host name with a character other than a letter, a
digit, `-`, `.` and `_`, before any server is asked.

#### Scenario: An address with a space
- **WHEN** the human runs `lado git-server check 'not a url'` or `lado git-server add
  'not a url' --token`
- **THEN** it exits 2 with `not a git server's address: …`, and no server is asked

## MODIFIED Requirements

### Requirement: A git server's address

`add` SHALL take an address with or without a scheme, `https://` when none. It SHALL keep
a path (a server under `https://corp.ru/gitlab`), drop a trailing `/`, drop a trailing `.`
of the host name, and refuse with exit 2 an address with a user, a password, a query or a
fragment, or a scheme other than `https` and `http`. `http://` SHALL be taken with the
warning that the token goes to the host unencrypted.

#### Scenario: No scheme
- **WHEN** the human adds `gitlab.corp.ru/`
- **THEN** the saved address is `https://gitlab.corp.ru`

#### Scenario: A plain http address
- **WHEN** the human adds `http://git.lan`
- **THEN** stderr has a warning that the token goes to git.lan over plain http://,
  unencrypted, and the server is saved when its check passes

#### Scenario: A host with a trailing dot
- **WHEN** `https://gitlab.corp.ru` is saved and the human adds `gitlab.corp.ru.` with a new
  token
- **THEN** it replaces the token of `https://gitlab.corp.ru`, and the list still has one
  server for that host

### Requirement: A server that cannot be checked is not saved without --kind

When no kind recognises the server, `add` SHALL save nothing and say why in one line and
a hint: the server does not answer (the name is not found, the connection is refused, it
timed out, its certificate is not trusted), it refuses the token (a kind's own 401
answer), or it answers as neither GitHub nor GitLab. A server that refuses the token SHALL
NOT be saved even with `--kind`. When every kind's request is refused so, the refusal SHALL
name no kind.

#### Scenario: The server does not answer
- **WHEN** `gitlab.corp.ru` does not resolve
- **THEN** stderr has `lado: gitlab.corp.ru does not answer: the name is not found`, a hint
  naming `--kind`, nothing is saved, and the exit status is 1

#### Scenario: An untrusted certificate
- **WHEN** the server's certificate is signed by a company CA this machine does not trust
- **THEN** the refusal says the server's certificate is not trusted, and nothing is saved

#### Scenario: The token is refused
- **WHEN** `/api/v4/user` answers 401 with `{"message": "401 Unauthorized"}`
- **THEN** stderr has `lado: GitLab at https://gitlab.corp.ru refuses the token` and the
  kind's token page, nothing is saved, and `--kind gitlab` gives the same refusal

#### Scenario: A GitLab token without read_api
- **WHEN** `/api/v4/user` answers 403 with `{"error": "insufficient_scope", …}`
- **THEN** the refusal says the token lacks the scope `read_api`, and nothing is saved

#### Scenario: A gateway that refuses every request
- **WHEN** a gateway in front of `git.corp.example` answers both `/api/v4/user` and
  `/api/v3/user` with 401 and `{"message": "Unauthorized"}`
- **THEN** stderr has `lado: https://git.corp.example refuses the token on GitHub's and
  GitLab's API alike` with the hint `check that the token was copied whole; a sign-in gateway
  in front of the server refuses any token too`, and nothing is saved

### Requirement: lado git-server remove removes a server and its token

`lado git-server remove <address>` SHALL find the server by the host and port of the
address, remove it from `lado.db` and remove its token file and folder, and
`<LADO_HOME>/git-servers/` itself once no server is left; an address that is no saved
server's SHALL be refused with exit 1. When the server is removed but a folder cannot be,
the command SHALL say `Removed` with a warning naming the folder, and exit 0.

#### Scenario: Removing a server
- **WHEN** the human runs `lado git-server remove gitlab.corp.ru`
- **THEN** the server is no longer listed and `<LADO_HOME>/git-servers/<id>/` is gone

#### Scenario: Removing the last server
- **WHEN** `https://gitlab.corp.ru` is the only saved server and the human removes it
- **THEN** `<LADO_HOME>/git-servers/` is gone too

#### Scenario: Removing one of two servers
- **WHEN** two servers are saved and the human removes one
- **THEN** `<LADO_HOME>/git-servers/` stays with the other server's folder

#### Scenario: A folder that cannot be removed
- **WHEN** the last server is removed and `<LADO_HOME>/git-servers/` holds a file of the
  human's
- **THEN** the server is no longer listed, the output says `Removed` with a warning naming
  `<LADO_HOME>/git-servers/`, and the exit status is 0

### Requirement: Agents commit to a listed server's repositories as its author

An agent launched while a saved server has a commit author SHALL commit, as author and
committer, with that name and email in every repository with a remote on that server, in any
form git servers take (`<address>/…`, with a user before the host, `git@<host>:…`,
`ssh://git@<host>[:22]/…`), and in no other repository. That
author SHALL win over a repository's own `user.name` and `user.email`; with remotes on two
servers with authors, the server later by host SHALL win.

#### Scenario: A commit to the server's repository
- **WHEN** `https://git.test:8443` is saved with the author `Ivan Petrov
  <ivan.petrov@corp.ru>`, and an agent of a new session clones
  `https://git.test:8443/team/app.git`, commits and pushes
- **THEN** the pushed commit's author and committer are both `Ivan Petrov
  <ivan.petrov@corp.ru>`

#### Scenario: A clone by its git@ address
- **WHEN** the agent clones `git@git.test:team/app.git`, which goes over https to the server
  while the repository's remote stays `git@git.test:team/app.git`
- **THEN** its commit carries the server's author too

#### Scenario: Another host
- **WHEN** the same agent commits in a repository whose only remote is on a host that is no
  saved server's, or that has no remote
- **THEN** the commit carries the author of the human's own git settings, as without LADO

#### Scenario: After the author is cleared
- **WHEN** the author is cleared and the agent is restarted
- **THEN** its commits to the server's repository carry the human's own git author

#### Scenario: The global and system configs
- **WHEN** an agent commits with a server's author
- **THEN** `~/.gitconfig` and the system git config are unchanged

#### Scenario: A worker's worktree of a session's repository
- **WHEN** LADO clones `https://git.test:8443/team/app.git` for a session and a worker
  commits in its own git worktree of that clone
- **THEN** the commit carries the server's author


### Requirement: A commit author's file holds only the name and email

The file git includes for a server's author SHALL be written at each launch in the agent's
own config folder under `LADO_HOME`, SHALL hold only the `user` section's `name` and `email`,
never a token or a path, and SHALL go with the agent's config folder when it stops. A write
that fails SHALL leave no file of its own behind.

#### Scenario: The file of an author
- **WHEN** an agent is launched while `https://gitlab.corp.ru` has an author and a token
- **THEN** its author file holds the `[user]` section with `name` and `email` and nothing else

#### Scenario: A failed write
- **WHEN** writing an author file fails midway
- **THEN** the agent's config folder holds no temporary file of it

### Requirement: A commit author needs git 2.36

Setting a commit author SHALL be refused when the git on LADO's PATH is older than 2.36,
naming the version found and 2.36. While a saved server has a commit author, an agent's
launch SHALL be refused when the agents' git is older than 2.36, naming the version, 2.36
and `lado git-server author <address> --clear` for every server with an author; with no
author set, the launch SHALL go as before.

#### Scenario: An old git at a launch
- **WHEN** a server has an author and the agents' git reports `git version 2.34.1`
- **THEN** the launch is refused with a line naming git 2.34.1, 2.36 and
  `lado git-server author <address> --clear`, and no agent starts

#### Scenario: An old git without an author
- **WHEN** a server is saved with no author and the agents' git reports 2.34.1
- **THEN** the launch goes as before

#### Scenario: Two servers with authors
- **WHEN** `https://gitlab.corp.ru` and `https://git.lan` both have an author and the agents'
  git is 2.34.1
- **THEN** the refusal names `lado git-server author` with `--clear` for both addresses
