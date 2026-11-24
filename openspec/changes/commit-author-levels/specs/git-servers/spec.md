## MODIFIED Requirements

### Requirement: lado git-server list shows the saved servers without asking them

`lado git-server list` SHALL print, after the line of LADO's commit author, one row per
saved server with its address, its kind, the login seen when it was added (`not checked`
for one saved with `--kind` unchecked), whether its token file is there, its certificate's
expiry (`-` for none) and, last, its commit author (`-` for none), asking no server; with
none saved it SHALL say how to add one.

#### Scenario: Two servers
- **WHEN** `https://gitlab.corp.ru` (GitLab, ivan.petrov) and `https://git.lan` (GitLab,
  saved with `--kind`) are saved
- **THEN** the rows show `GitLab  ivan.petrov  yes` and `GitLab  not checked  yes`

#### Scenario: None saved
- **WHEN** no server is saved and LADO has no commit author
- **THEN** the output is `LADO's commit author: -` and then `No git servers. Add one: lado
  git-server add <address> --token`

#### Scenario: A server with an author
- **WHEN** `https://gitlab.corp.ru` has the author `Ivan Petrov <ivan.petrov@corp.ru>` and
  `https://git.lan` none
- **THEN** the row of gitlab.corp.ru ends with `Ivan Petrov <ivan.petrov@corp.ru>` and the
  row of git.lan with `-`

#### Scenario: A server with a certificate
- **WHEN** `https://gitlab.corp.ru` has a certificate valid until 2031-03-01
- **THEN** its row shows `until 2031-03-01` before its author, and a server without one `-`

### Requirement: lado git-server author sets, shows and clears a server's commit author

`lado git-server author <address> --name <name> --email <email>` SHALL save the commit author
(both together) of the saved server of the address's host and port and say how agents commit
there now; `--clear` SHALL remove it; without options it SHALL print it or that there is none.
An address of no saved server SHALL exit 1; half an author or `--clear` with either value
SHALL exit 2. Without an address it is LADO's own author (capability commit-authors).

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
  there with LADO's commit author, or the human's own git author when LADO has none, the
  third says the server has no commit author

#### Scenario: A half author
- **WHEN** the human runs `lado git-server author gitlab.corp.ru --name "Ivan Petrov"`
- **THEN** it exits 2 saying that `--name` and `--email` go together, and nothing changes

### Requirement: Agents commit to a listed server's repositories as its author

An agent launched while a saved server has a commit author SHALL commit, as author and
committer, with that name and email in every repository with a remote on that server, in any
form git servers take (`<address>/…`, with a user before the host, `git@<host>:…`,
`ssh://git@<host>[:22]/…`), and in no other repository. It SHALL win over git's configs and
LADO's author and lose to the session's project's; with remotes on two servers with
authors, the server later by host SHALL win.

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
- **THEN** the commit carries LADO's commit author when one is set, else the author of the
  human's own git settings, as without LADO

#### Scenario: After the author is cleared
- **WHEN** the author is cleared and the agent is restarted
- **THEN** its commits to the server's repository carry LADO's commit author when one is
  set, else the human's own git author

#### Scenario: The global and system configs
- **WHEN** an agent commits with a server's author
- **THEN** `~/.gitconfig` and the system git config are unchanged

#### Scenario: A worker's worktree of a session's repository
- **WHEN** LADO clones `https://git.test:8443/team/app.git` for a session and a worker
  commits in its own git worktree of that clone
- **THEN** the commit carries the server's author

## REMOVED Requirements

### Requirement: The author variables of an agent's environment are named at its launch

**Reason**: The warning now covers LADO's and a project's author as well as a server's.
**Migration**: Replaced by "The launch names author variables that win over LADO's commit
authors" of capability commit-authors.
