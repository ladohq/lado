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
GitHub's `<address>/api/v3/user` with `Authorization: token <token>`. A kind SHALL be
recognised by 200 with a JSON object holding a string `username` (GitLab) or `login`
(GitHub).

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
NOT be saved even with `--kind`.

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
a path (a server under `https://corp.ru/gitlab`), drop a trailing `/`, and refuse with
exit 2 an address with a user, a password, a query or a fragment, or a scheme other than
`https` and `http`. `http://` SHALL be taken with the warning that the token goes to the
host unencrypted.

#### Scenario: No scheme
- **WHEN** the human adds `gitlab.corp.ru/`
- **THEN** the saved address is `https://gitlab.corp.ru`

#### Scenario: A plain http address
- **WHEN** the human adds `http://git.lan`
- **THEN** stderr has a warning that the token goes to git.lan over plain http://,
  unencrypted, and the server is saved when its check passes

### Requirement: One git server per host

A server SHALL be identified by its host and port: a second `add` of the same host and
port SHALL replace the saved server's address, kind, login and token once its check
passes, saying `Replaced`, and keep the server's id.

#### Scenario: A new token for a saved server
- **WHEN** `https://gitlab.corp.ru` is saved and the human adds `gitlab.corp.ru` with a
  new token that the server accepts
- **THEN** the list still has one server for that host, holding the new token, and the
  output says `Replaced git server https://gitlab.corp.ru.`

### Requirement: github.com is not added

`add` SHALL refuse `github.com`, `www.github.com` and `api.github.com`, saying that
github.com is reached through `gh`'s login (`GH_TOKEN` or `gh auth login`), before asking
for a token.

#### Scenario: github.com
- **WHEN** the human runs `lado git-server add github.com --token`
- **THEN** no token is asked, nothing is saved, and the exit status is 1

### Requirement: A git server's token is asked and kept in its own file

The token SHALL be kept in `<LADO_HOME>/git-servers/<id>/token`, the folders mode 700 and
the file mode 600 whatever the umask, written whole by a rename, refusing a symbolic link
on the way. Its value SHALL appear in no output, log, error journal, `lado.db`, git config
file, agent's working copy, or other file under `LADO_HOME`.

#### Scenario: A token piped in
- **WHEN** the human runs `printf '%s' "$TOKEN" | lado git-server add gitlab.corp.ru --token`
  and the server accepts it
- **THEN** `<LADO_HOME>/git-servers/<id>/token` holds it with mode 600 in a folder of mode
  700, and neither the output, `lado.db`, the error journal nor any other file of
  `LADO_HOME` holds its value

### Requirement: The token is asked, never taken from the command line

`add` SHALL ask the token without echo, or read it from stdin when that is not a terminal,
and SHALL refuse a token given on the command line (`--token <value>`), naming the bare
`--token` instead, and a missing or empty token.

#### Scenario: A token on the command line
- **WHEN** the human runs `lado git-server add gitlab.corp.ru --token glpat-abc`
- **THEN** it is refused without echoing the value, and nothing is saved

### Requirement: lado git-server list shows the saved servers without asking them

`lado git-server list` SHALL print one row per saved server with its address, its kind,
the login seen when it was added (`not checked` for one saved with `--kind` unchecked) and
whether its token file is there, asking no server; with none saved it SHALL say how to add
one.

#### Scenario: Two servers
- **WHEN** `https://gitlab.corp.ru` (GitLab, ivan.petrov) and `https://git.lan` (GitLab,
  saved with `--kind`) are saved
- **THEN** the rows show `GitLab  ivan.petrov  yes` and `GitLab  not checked  yes`

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** the output is `No git servers. Add one: lado git-server add <address> --token`

### Requirement: lado git-server remove removes a server and its token

`lado git-server remove <address>` SHALL find the server by the host and port of the
address, remove it from `lado.db` and remove its token file and folder; an address that
is no saved server's SHALL be refused with exit 1.

#### Scenario: Removing a server
- **WHEN** the human runs `lado git-server remove gitlab.corp.ru`
- **THEN** the server is no longer listed and `<LADO_HOME>/git-servers/<id>/` is gone

### Requirement: The saved git servers are kept in lado.db

The saved git servers SHALL be kept in `lado.db` (from schema 41), each with an id that
never changes, its address, host and port, kind and login; never its token. A `lado.db` of
schema 40 SHALL be upgraded by the migration with no git server saved.

#### Scenario: Upgrading from schema 40
- **WHEN** a `lado.db` of schema 40 is upgraded
- **THEN** it is at schema 41 with no git server, and every session, agent and model server
  is as before

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
