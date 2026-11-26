## MODIFIED Requirements

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
  commit.` and `Set one in Settings → Git servers, or run: lado git-server author --name
  "Your Name" --email you@example.com`

#### Scenario: Inside an agent
- **WHEN** an agent runs `lado git-server author --name Bot --email bot@example.com`
- **THEN** it is refused as the human's command, and LADO's author is unchanged

## ADDED Requirements

### Requirement: The CLI says when nobody is left to sign agents' commits

When nobody signs agents' commits by the commit author order once `lado git-server author`
or `lado project author` clears or shows an author (a project judged in its repositories,
else its folder; LADO and a server outside any repository), the command SHALL say that agents
cannot commit (naming the project's repositories when only some) and how to set an author,
and a clear SHALL end with the line of running agents instead of the restart line.

#### Scenario: Clearing LADO's last author
- **WHEN** LADO's author is set, git knows none, and the human runs `lado git-server author
  --clear`
- **THEN** the output is `LADO has no commit author now.`, the two lines of nobody known and
  `Running agents keep the author they started with until they restart.`, the exit status is
  0, and no line says that agents commit

#### Scenario: Clearing a project's author leaves nobody
- **WHEN** neither LADO nor git has an author, the project `shop` has the author `Shop Bot
  <bot@shop.example>` and its one repository `frontend` has no remote, and the human runs
  `lado project author shop --clear`
- **THEN** the output is `Project shop has no commit author now, and nobody else signs its
  agents' commits: they cannot commit.`, `Set one: lado project author shop --name "Your
  Name" --email you@example.com, or LADO's in Settings → Git servers.` and `Running agents
  keep the author they started with until they restart.`, and the exit status is 0

#### Scenario: Showing a project nobody signs for
- **WHEN** neither LADO, git nor the project `shop` has an author and the human runs `lado
  project author shop`
- **THEN** the output is `Project shop has no commit author, and nobody else signs its
  agents' commits: they cannot commit.` and the same hint

#### Scenario: Nobody in some repositories only
- **WHEN** neither LADO nor git has an author, the project `shop` has the repositories `api`,
  whose remote is on a saved server with an author, and `site` without a remote, and the human
  runs `lado project author shop --clear`
- **THEN** the output is `Project shop has no commit author now: its agents cannot commit in
  site (nobody signs there).`, the hint and the line of running agents

#### Scenario: Clearing a server's author leaves nobody
- **WHEN** neither LADO nor git has an author, `https://gitlab.corp.ru` has the author `Ivan
  Petrov <ivan.petrov@corp.ru>`, and the human runs `lado git-server author gitlab.corp.ru
  --clear`, then `lado git-server author gitlab.corp.ru`
- **THEN** the first prints `Agents cannot commit to https://gitlab.corp.ru now: it has no
  commit author, LADO has none and git knows none.`, `Set one in Settings → Git servers, or
  run: lado git-server author --name "Your Name" --email you@example.com` and `Running agents
  keep the author they started with until they restart.`, exit 0; the second prints
  `https://gitlab.corp.ru has no commit author, LADO has none and git knows none: agents
  cannot commit there.` and the same hint

#### Scenario: Somebody is left
- **WHEN** git's global config names `Ann Lee <ann@example.com>` and the human runs `lado
  project author shop --clear`
- **THEN** the output is `Project shop has no commit author now: its agents commit as LADO's
  or a git server's.` and the restart line, as before

#### Scenario: git cannot read its config
- **WHEN** git's global config cannot be parsed and the human runs `lado project author shop
  --clear`
- **THEN** the project's author is cleared and the command says in one line that git cannot
  read its config, exit 1
