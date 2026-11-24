# commit-authors Specification

## Purpose
Who LADO's agents and LADO itself commit as: LADO's own commit author, a project's and a git
server's, in one order of priority over git's own config, set from the UI and the CLI.

## Requirements

### Requirement: LADO keeps its own commit author and a project's in lado.db

LADO SHALL keep at most one commit author of its own and at most one per project, each a
name and an email together, in lado.db alone, checked as a git server's author is; it SHALL
write neither into a git config file. A project's author SHALL go with its project.

#### Scenario: Setting LADO's author leaves git's files alone
- **WHEN** the human sets LADO's author `Ann Lee <ann@example.com>`
- **THEN** lado.db holds it, and `~/.gitconfig`, the system git config and every
  repository's `.git/config` are unchanged

#### Scenario: A deleted project's author
- **WHEN** the project `shop` has an author and is deleted
- **THEN** no author of `shop` is left in lado.db

### Requirement: The commit author follows one order

An agent's commit, as author and committer, SHALL carry the first of: its session's
project's author; the author of a saved git server a remote of the repository is on; LADO's
author; the author of git's own config (system, global, the repository's own). LADO's
authors SHALL win over every git config file; the agent's `GIT_AUTHOR_*` and
`GIT_COMMITTER_*` variables SHALL win over all.

#### Scenario: LADO's author in a repository without a remote
- **WHEN** git's config has no `user.name`, LADO's author is `Ann Lee <ann@example.com>`
  and an agent commits in its session's repository, which has no remote
- **THEN** the commit's author and committer are `Ann Lee <ann@example.com>`

#### Scenario: The server's author wins over LADO's
- **WHEN** LADO's author is `Ann Lee <ann@example.com>`, `https://git.test:8443` has the
  author `Ivan Petrov <ivan.petrov@corp.ru>`, and an agent clones
  `https://git.test:8443/team/app.git` and commits there
- **THEN** the commit carries `Ivan Petrov <ivan.petrov@corp.ru>`

#### Scenario: The project's author wins over the server's
- **WHEN** the project `shop` has the author `Shop Bot <bot@shop.example>`, its repository
  `api` has its remote on `https://git.test:8443`, which has an author, and an agent of a
  session in `shop`/`api` commits
- **THEN** the commit carries `Shop Bot <bot@shop.example>`

#### Scenario: LADO's author over the human's own
- **WHEN** git's global config names `Alex Home <alex@home.example>`, the repository's own
  config names `Alex Work <alex@work.example>`, and LADO's author is `Ann Lee
  <ann@example.com>`
- **THEN** an agent's commit there carries `Ann Lee <ann@example.com>`

#### Scenario: No LADO author
- **WHEN** neither LADO, the project nor a server has an author
- **THEN** the commit carries the author of git's own config, as without LADO

#### Scenario: A change reaches agents started after it
- **WHEN** LADO's author is changed while an agent runs
- **THEN** that agent's commits keep the author of its launch, and an agent started or
  restarted after the change takes the new one

### Requirement: LADO's own first commits take the same author

A fresh start, a plain folder's set-up and a project's repository made from scratch SHALL
commit as the author an agent there would get (the project's, else LADO's, else git's own),
and SHALL be refused, making nothing, only when there is none, with the session-scratch
capability's text and hint of a missing author.

#### Scenario: A fresh start on a clean machine
- **WHEN** git has no `user.name` or `user.email`, LADO's author is `Ann Lee
  <ann@example.com>`, and the human runs `lado start --new ~/workspace/coffee`
- **THEN** the repository's first commit carries `Ann Lee <ann@example.com>`, and git's
  config is unchanged

#### Scenario: A project's repository from scratch
- **WHEN** the project `shop` has the author `Shop Bot <bot@shop.example>` and the human runs
  `lado project repo add shop --new site`
- **THEN** the first commit of `site` carries `Shop Bot <bot@shop.example>`

#### Scenario: Nobody known at a start
- **WHEN** neither LADO nor git has an author and the human starts from scratch
- **THEN** the start is refused with `nobody signs the agents' commits: LADO has no commit
  author and git has no user.name or user.email` and the hint naming Settings → Git servers,
  and nothing is made

### Requirement: A launch needs git 2.31 for LADO's or a project's author

Setting LADO's or a project's author SHALL be refused when the git on LADO's PATH is older
than 2.31. While LADO's author or the session's project's author is set, an agent's launch
SHALL be refused when the agents' git is older than 2.31, naming the version found, 2.31
and the command that clears that author.

#### Scenario: An old git at a launch
- **WHEN** LADO's author is set and the agents' git reports `git version 2.30.2`
- **THEN** the launch is refused with a line naming git 2.30.2, 2.31 and `lado git-server
  author --clear`, and no agent starts

### Requirement: lado git-server author without an address is LADO's author

`lado git-server author` without an address SHALL work on LADO's author: `--name <name>
--email <email>` SHALL set it and say how agents commit now, `--clear` SHALL remove it, and
without options it SHALL print it or, when unset, the author agents commit as from git's
config or that git knows none and agents cannot commit. Setting or clearing it inside an
agent SHALL be refused; half an author SHALL exit 2.

#### Scenario: Setting LADO's author
- **WHEN** the human runs `lado git-server author --name "Ann Lee" --email ann@example.com`
- **THEN** the output is `Agents commit as Ann Lee <ann@example.com> where no project or
  git server has an author of its own.` and `Agents started from now on commit so; restart
  running agents to give it to them.`, and the exit status is 0

#### Scenario: Clearing it
- **WHEN** the human runs `lado git-server author --clear`
- **THEN** the output starts with `LADO has no commit author now.`

#### Scenario: Showing it unset
- **WHEN** LADO has no author, git's global config names `Ann Lee <ann@example.com>`, and
  the human runs `lado git-server author`
- **THEN** the output is `LADO has no commit author: agents commit as Ann Lee
  <ann@example.com> from your git config.`

#### Scenario: Nobody known
- **WHEN** LADO has no author, git knows none, and the human runs `lado git-server author`
- **THEN** the output is `LADO has no commit author and git knows none: agents cannot
  commit.` and the command `lado git-server author --name "Your Name" --email
  you@example.com`

#### Scenario: Inside an agent
- **WHEN** an agent runs `lado git-server author --name Bot --email bot@example.com`
- **THEN** it is refused as the human's command, and LADO's author is unchanged

### Requirement: lado git-server list names LADO's author first

`lado git-server list` SHALL print `LADO's commit author: <name> <<email>>` (`-` for none)
as its first line, before the servers' table or the line that there is none.

#### Scenario: No servers, an author
- **WHEN** LADO's author is `Ann Lee <ann@example.com>` and no server is saved
- **THEN** the output is `LADO's commit author: Ann Lee <ann@example.com>` and then `No git
  servers. Add one: lado git-server add <address> --token`

### Requirement: lado project author sets, shows and clears a project's author

`lado project author <id> --name <name> --email <email>` SHALL set the project's author and
print `Agents of project <id> commit as <name> <<email>>.`; `--clear` SHALL remove it; without
options it SHALL print it or that there is none. Inside an agent a change SHALL be refused, a
show not (capability projects). An unknown project SHALL exit 1, half an author exit 2.

#### Scenario: Setting a project's author
- **WHEN** the human runs `lado project author shop --name "Shop Bot" --email
  bot@shop.example`
- **THEN** the output is `Agents of project shop commit as Shop Bot <bot@shop.example>.` and
  the restart line, and `lado project show shop` prints `  author:  Shop Bot
  <bot@shop.example>`

### Requirement: The server's API sets LADO's and a project's author

`GET /api/git-servers` SHALL answer LADO's author and git's own; `PUT` and `DELETE
/api/git-author` SHALL set and clear LADO's author as the command does. `GET
/api/projects/{id}` SHALL answer the project's author and, per repository, the author its
agents commit as with its source (`project`, `server`, `lado`, `git`, `none`); `PUT` and
`DELETE /api/projects/{id}/author` SHALL set and clear the project's.

#### Scenario: The author in effect per repository
- **WHEN** LADO's author is `Ann Lee <ann@example.com>`, the project `shop` has none, its
  repository `site` has no remote and `api` a remote on a server with the author `Ivan
  Petrov <ivan.petrov@corp.ru>`
- **THEN** `GET /api/projects/shop` answers `site` with `Ann Lee <ann@example.com>` from
  `lado` and `api` with `Ivan Petrov <ivan.petrov@corp.ru>` from `server`

#### Scenario: An email that is no email
- **WHEN** `PUT /api/git-author` gets `{"name": "Ann Lee", "email": "ann"}`
- **THEN** it answers 400 with `not an email address: name@host` under the field `email`,
  and nothing is saved

### Requirement: The launch names author variables that win over LADO's authors

When LADO's author, the session's project's author or a saved server's author is set and an
agent's environment holds `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` or
`GIT_COMMITTER_EMAIL`, its launch SHALL warn `<NAME> is set for <agent>: it wins over LADO's
commit authors`, also when the variable is a project variable.

#### Scenario: A variable from the login shell
- **WHEN** LADO's author is set and the agent's login shell exports `GIT_AUTHOR_EMAIL`
- **THEN** the launch's warnings hold `GIT_AUTHOR_EMAIL is set for <agent>: it wins over
  LADO's commit authors`

### Requirement: lado.db of schema 43 is migrated to 44

A lado.db of schema 43 SHALL be migrated to 44 with its data kept, LADO having no author and
no project an author; `backups/lado.db.schema-43` SHALL hold the database as it was.

#### Scenario: The migration
- **WHEN** LADO starts on a lado.db of schema 43 with a project and a server with an author
- **THEN** the project and the server's author are kept, LADO and the project have no
  author, and the backup is there
