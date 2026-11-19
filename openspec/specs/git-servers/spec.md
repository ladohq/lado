# git-servers Specification

## Purpose
The git servers the human keeps in LADO (GitLab, GitHub Enterprise) with their tokens, and
how agents and LADO's own git reach them over https without a prompt.

## Requirements

### Requirement: lado git-server add checks a server and saves it

`lado git-server add <address> --token` SHALL ask the server's API with the token, tell
the server's kind and the account the token signs in as (`GitLab, signed in as <login>`),
and save the server with its kind, its login and its token. It SHALL then say that agents
started from now on reach the server and running agents after their restart. Exit status
SHALL be 0 when saved, 1 for a refusal, 2 for an address it does not take.

#### Scenario: A GitLab server
- **WHEN** the human runs `lado git-server add gitlab.corp.ru --token`, types a token, and
  `https://gitlab.corp.ru/api/v4/user` answers 200 with `{"username": "ivan.petrov", …}`
- **THEN** the output has `GitLab, signed in as ivan.petrov` and
  `Saved git server https://gitlab.corp.ru.`, `lado git-server list` shows it, and the
  exit status is 0

#### Scenario: A GitHub Enterprise server
- **WHEN** `https://github.corp.ru/api/v3/user` answers 200 with `{"login": "ivan", …}`
- **THEN** the output has `GitHub, signed in as ivan` and the server is saved with kind
  `github`

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

### Requirement: Each kind of git server is a module of its own

Each kind of server SHALL be a module of its own that names its API request, how it tells
its answer and a refused token, the user name git sends with the token (`oauth2` for
GitLab, `x-access-token` for GitHub), its host tool (`glab`, `gh`) and its token page; the
list of kinds SHALL be the one place that names them.

#### Scenario: The kinds of --kind
- **WHEN** the human runs `lado git-server add --help`
- **THEN** `--kind` offers `github` and `gitlab`, the names of the kind modules

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

### Requirement: --kind saves a server that could not be checked

With `--kind github` or `--kind gitlab`, a server that does not answer or is not
recognised SHALL be saved with that kind and no login, with a warning that the server
could not be checked. A server some kind recognises SHALL be saved as that kind and a
different `--kind` SHALL be refused.

#### Scenario: Saved with --kind
- **WHEN** the server does not answer and the human runs
  `lado git-server add gitlab.corp.ru --token --kind gitlab`
- **THEN** stderr has a warning that the server could not be checked, the server is saved
  as GitLab with no login, and the exit status is 0

#### Scenario: --kind against the answer
- **WHEN** the server is recognised as GitLab and the human gave `--kind github`
- **THEN** nothing is saved, and the refusal says the server answers as GitLab

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

### Requirement: One git server per host

A server SHALL be identified by its host and port: a second `add` of the same host and
port SHALL replace the saved server's address, kind, login and token once its check
passes, saying `Replaced`, and keep the server's id and commit author. A server whose host
name a saved server holds on another port SHALL be refused before any request, naming that
server, as git's ssh addresses carry no port; the command and the Settings page alike.

#### Scenario: A new token for a saved server
- **WHEN** `https://gitlab.corp.ru` is saved and the human adds `gitlab.corp.ru` with a
  new token that the server accepts
- **THEN** the list still has one server for that host, holding the new token, and the
  output says `Replaced git server https://gitlab.corp.ru.`

#### Scenario: A new token keeps the author
- **WHEN** `https://gitlab.corp.ru` has a commit author and the human adds it again with a
  new token
- **THEN** the server keeps its commit author

#### Scenario: The same host name on another port
- **WHEN** `https://git.corp.example` is saved and the human runs `lado git-server add
  git.corp.example:8443 --token`
- **THEN** it is refused with exit 1 before a token is asked, saying that
  `git.corp.example` already has the git server `https://git.corp.example`, with the hint
  `remove it first: lado git-server remove https://git.corp.example`, and nothing is saved

#### Scenario: Plain http on another port of a saved host name
- **WHEN** `https://git.corp.example` is saved and the human adds `http://git.corp.example:8080`
- **THEN** it is refused the same way and no request reaches the server

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

### Requirement: The token is asked, never taken from the command line

`add` SHALL ask the token without echo, or read it from stdin when that is not a terminal,
and SHALL refuse a token given on the command line (`--token <value>`), naming the bare
`--token` instead, and a missing or empty token.

#### Scenario: A token on the command line
- **WHEN** the human runs `lado git-server add gitlab.corp.ru --token glpat-abc`
- **THEN** it is refused without echoing the value, and nothing is saved

### Requirement: lado git-server list shows the saved servers without asking them

`lado git-server list` SHALL print one row per saved server with its address, its kind,
the login seen when it was added (`not checked` for one saved with `--kind` unchecked),
whether its token file is there and, last, its commit author (`-` for none), asking no
server; with none saved it SHALL say how to add one.

#### Scenario: Two servers
- **WHEN** `https://gitlab.corp.ru` (GitLab, ivan.petrov) and `https://git.lan` (GitLab,
  saved with `--kind`) are saved
- **THEN** the rows show `GitLab  ivan.petrov  yes` and `GitLab  not checked  yes`

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** the output is `No git servers. Add one: lado git-server add <address> --token`

#### Scenario: A server with an author
- **WHEN** `https://gitlab.corp.ru` has the author `Ivan Petrov <ivan.petrov@corp.ru>` and
  `https://git.lan` none
- **THEN** the row of gitlab.corp.ru ends with `Ivan Petrov <ivan.petrov@corp.ru>` and the
  row of git.lan with `-`

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

### Requirement: The saved git servers are kept in lado.db

The saved git servers SHALL be kept in `lado.db` (from schema 41), each with an id that
never changes, its address, host and port, kind and login, and from schema 42 its commit
author's name and email (both or neither); never its token. A `lado.db` of schema 40 SHALL be
upgraded by the migrations with no git server saved, and one of schema 41 with its servers
kept and no author.

#### Scenario: Upgrading from schema 40
- **WHEN** a `lado.db` of schema 40 is upgraded
- **THEN** it is at the current schema with no git server, and every session, agent and
  model server is as before

#### Scenario: Upgrading from schema 41
- **WHEN** a `lado.db` of schema 41 with a saved server is upgraded
- **THEN** it is at schema 42, the server is kept with its id, address, kind and login and
  has no commit author, and `backups/lado.db.schema-41` holds the database as it was

#### Scenario: Rolling back to schema 41
- **WHEN** a server has a commit author and `backups/lado.db.schema-41` is put back as
  `lado.db`
- **THEN** the server is there without an author, and an agent's launch gives git no author
  entry

### Requirement: Agents and LADO's own git reach a listed server over https with its token

Each agent at its launch, and LADO's own network git (kits, packs, marketplaces, a clone
or listing of a URL) at each call, SHALL get per saved server, through `GIT_CONFIG_COUNT`,
`GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>`, an empty `credential.<address>.helper`
then LADO's helper. git SHALL then clone, fetch and push there with the token and no
prompt, no other helper SHALL store it, and the global and system configs SHALL NOT change.

#### Scenario: An agent pushes
- **WHEN** `https://git.test:8443` is saved with a token the server requires, and an agent
  of a new session runs `git clone https://git.test:8443/team/app.git`, commits and
  `git push`
- **THEN** both succeed without a prompt, and the server saw the token

#### Scenario: LADO's own clone
- **WHEN** the human starts a session from `https://git.test:8443/team/app.git`
- **THEN** LADO's clone succeeds with the saved token

#### Scenario: A global store helper does not keep the token
- **WHEN** the human's `~/.gitconfig` has `credential.helper=store` and an agent pushes to a
  saved server
- **THEN** `~/.git-credentials` does not hold the token, and `~/.gitconfig` and the system
  git config are unchanged

### Requirement: LADO's git variables only add to the agent's

With no server saved, LADO SHALL set no `GIT_CONFIG_*` variable. Entries of `GIT_CONFIG_*`
the agent's layers already hold SHALL be kept, LADO's coming after them.

#### Scenario: A host not in the list
- **WHEN** an agent clones from a host that is no saved server's
- **THEN** git asks the helpers it would ask without LADO, and LADO's helper is not called

#### Scenario: The human's own GIT_CONFIG_COUNT
- **WHEN** the agent's login shell exports `GIT_CONFIG_COUNT=1` with
  `GIT_CONFIG_KEY_0=core.autocrlf`
- **THEN** the agent has `GIT_CONFIG_KEY_0=core.autocrlf` still, and LADO's entries start
  at index 1

### Requirement: ssh addresses of a listed server go over https

For each saved server, the same variables SHALL rewrite `git@<host>:` and
`ssh://git@<host>/` (and `ssh://git@<host>:22/`) to the server's address followed by `/`,
for fetch and push alike. An ssh address with another port SHALL go over ssh as before.

#### Scenario: The scp form
- **WHEN** `https://gitlab.corp.ru` is saved and an agent runs
  `git ls-remote git@gitlab.corp.ru:team/app.git`
- **THEN** git asks `https://gitlab.corp.ru/team/app.git` with the saved token

#### Scenario: The ssh URL
- **WHEN** an agent runs `git push` to `ssh://git@gitlab.corp.ru/team/app.git`
- **THEN** git pushes to `https://gitlab.corp.ru/team/app.git`

#### Scenario: A server under a path
- **WHEN** `https://corp.ru/gitlab` is saved
- **THEN** `git@corp.ru:team/app.git` goes to `https://corp.ru/gitlab/team/app.git`

### Requirement: LADO's credential helper

LADO's credential helper SHALL run with LADO's own Python by its absolute path, without
the working folder on its module path, so it is found when `lado` is not on the agent's
PATH. On `get` it SHALL print the kind's user name and the token read from the server's
token file by the link-refusing reader of LADO's secrets. It SHALL do nothing on `store`
and `erase`, and SHALL NOT open `lado.db`.

#### Scenario: Without lado on PATH
- **WHEN** an agent's PATH holds git and no `lado`, and it clones from a saved server
- **THEN** the clone succeeds with the saved token

### Requirement: The helper stops git when it has no token

With no token file for its server, or one it cannot read, LADO's helper SHALL print
`quit=1`, so git neither asks another helper nor prompts, and write one line to stderr
naming the address and `lado git-server add`, never a token.

#### Scenario: A server removed while an agent runs
- **WHEN** the server is removed after the agent's launch and the agent then fetches from it
- **THEN** git fails without a prompt, and its stderr names the address and
  `lado git-server add`

### Requirement: git older than 2.31 is refused where a git server is needed

LADO SHALL refuse loudly, naming the version found and 2.31, when the git it would run is
older than 2.31 and: `lado git-server add` is run (the git on LADO's PATH); an agent is
launched while a server is saved (the git on the agent's PATH); or LADO's own git call is
for the host of a saved server. A launch or call that needs no saved server SHALL go as
before.

#### Scenario: An old git at a launch
- **WHEN** a server is saved and the agents' git reports `git version 2.30.2`
- **THEN** the launch is refused with a line naming git 2.30.2, 2.31 and
  `lado git-server remove`, and no agent starts

#### Scenario: An old git without servers
- **WHEN** no server is saved and the agents' git reports 2.30.2
- **THEN** the launch goes as before

### Requirement: lado git-server author sets, shows and clears a server's commit author

`lado git-server author <address> --name <name> --email <email>` SHALL save the commit author
(both values together) of the saved server of the address's host and port and say how agents
commit there now; `--clear` SHALL remove it; without options it SHALL print the author or that
there is none. An address of no saved server SHALL exit 1; `--name` without `--email`, the
other way round, or `--clear` with either SHALL exit 2.

#### Scenario: Setting an author
- **WHEN** `https://gitlab.corp.ru` is saved and the human runs `lado git-server author
  gitlab.corp.ru --name "Ivan Petrov" --email ivan.petrov@corp.ru`
- **THEN** the output is `Agents commit to https://gitlab.corp.ru as Ivan Petrov
  <ivan.petrov@corp.ru>.` and `Agents started from now on commit so; restart running agents
  to give it to them.`, and the exit status is 0

#### Scenario: Showing and clearing it
- **WHEN** the human runs `lado git-server author gitlab.corp.ru`, then `lado git-server
  author gitlab.corp.ru --clear`, then `lado git-server author gitlab.corp.ru` again
- **THEN** the first prints `Ivan Petrov <ivan.petrov@corp.ru>`, the second says agents commit
  there with the human's own git author again, the third says the server has no commit author

#### Scenario: A half author
- **WHEN** the human runs `lado git-server author gitlab.corp.ru --name "Ivan Petrov"`
- **THEN** it exits 2 saying that `--name` and `--email` go together, and nothing changes

### Requirement: A commit author's name and email are checked

A commit author's name SHALL be refused when it is empty after trimming, or holds `<`, `>`
or a control character; its email SHALL be refused unless it has text on both sides of one
`@` and no space, `<`, `>` or control character. Nothing SHALL be saved on a refusal.

#### Scenario: Not an email
- **WHEN** the human gives `--email ivan.petrov`
- **THEN** it is refused with `not an email address: name@host` and exit 1

#### Scenario: A name with an angle bracket
- **WHEN** the human gives `--name "Ivan <boss>"`
- **THEN** it is refused, saying that a name holds no `<` or `>`

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

### Requirement: The author variables of an agent's environment are named at its launch

When a saved server has a commit author and an agent's environment holds
`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` or `GIT_COMMITTER_EMAIL`, its
launch SHALL warn that the variable wins over the git servers' commit authors.

#### Scenario: An author variable from the login shell
- **WHEN** the agent's login shell exports `GIT_AUTHOR_EMAIL` and a server has an author
- **THEN** the launch's warnings name `GIT_AUTHOR_EMAIL` and that it wins over the commit
  author of the git servers

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
