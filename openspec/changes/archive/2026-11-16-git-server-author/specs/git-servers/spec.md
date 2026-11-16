## ADDED Requirements

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
`ssh://git@<host>[:22]/…`), and in no other repository. That author SHALL win over a
repository's own `user.name` and `user.email`; with remotes on two servers with authors, the
server later by host SHALL win.

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

### Requirement: A commit author's file holds only the name and email

The file git includes for a server's author SHALL be written at each launch in the agent's
own config folder under `LADO_HOME`, SHALL hold only the `user` section's `name` and `email`,
never a token or a path, and SHALL go with the agent's config folder when it stops.

#### Scenario: The file of an author
- **WHEN** an agent is launched while `https://gitlab.corp.ru` has an author and a token
- **THEN** its author file holds the `[user]` section with `name` and `email` and nothing else

### Requirement: A commit author needs git 2.36

Setting a commit author SHALL be refused when the git on LADO's PATH is older than 2.36,
naming the version found and 2.36. While a saved server has a commit author, an agent's
launch SHALL be refused when the agents' git is older than 2.36, naming the version, 2.36
and `lado git-server author <address> --clear`; with no author set, the launch SHALL go as
before.

#### Scenario: An old git at a launch
- **WHEN** a server has an author and the agents' git reports `git version 2.34.1`
- **THEN** the launch is refused with a line naming git 2.34.1, 2.36 and
  `lado git-server author <address> --clear`, and no agent starts

#### Scenario: An old git without an author
- **WHEN** a server is saved with no author and the agents' git reports 2.34.1
- **THEN** the launch goes as before

### Requirement: The author variables of an agent's environment are named at its launch

When a saved server has a commit author and an agent's environment holds
`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` or `GIT_COMMITTER_EMAIL`, its
launch SHALL warn that the variable wins over the git servers' commit authors.

#### Scenario: An author variable from the login shell
- **WHEN** the agent's login shell exports `GIT_AUTHOR_EMAIL` and a server has an author
- **THEN** the launch's warnings name `GIT_AUTHOR_EMAIL` and that it wins over the commit
  author of the git servers

## MODIFIED Requirements

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
