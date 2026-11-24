## MODIFIED Requirements

### Requirement: lado project list and show print projects with their folders

`lado project list` SHALL print one line per project, by id: the id, the title (the id
when none) and the folder, `  (folder not found)` when it is missing, or with none `No
projects. Make one with: lado project create <id>`. `lado project show <id>` SHALL print
`<id> "<title>"` (the id alone without a title), `  folder:  <folder>` (same mark),
`  made:    <local date and time>` and `  author:  <its commit author>` (`-` for none); an
unknown id SHALL exit 1 with `lado: unknown project "<id>"`.

#### Scenario: Two projects
- **WHEN** LADO has `shop` titled `Shop` with its folder and `acme` without a title whose
  folder is gone
- **THEN** `lado project list` prints `acme  acme  <ws>/projects/acme  (folder not
  found)` and `shop  Shop  <ws>/projects/shop`

#### Scenario: A project's commit author
- **WHEN** `shop` has the commit author `Shop Bot <bot@shop.example>` and `acme` none
- **THEN** `lado project show shop` prints `  author:  Shop Bot <bot@shop.example>` after its
  `made:` line, and `lado project show acme` prints `  author:  -`

### Requirement: lado project show lists the project's repositories

`lado project show <id>` SHALL print, after its `author:` line, `  repositories:` and one
line per repository, by name: `    <name>  <branch>  <remote>`, the names and branches
padded to one width, `(detached)` for no branch and `(no remote)` for no remote; with
none, `  repositories: none`. A symbolic link in the project's folder SHALL be listed
among them by name, marked `(a link to <target>: clone it into <folder> instead)`. The
project's variables follow.

#### Scenario: Two repositories
- **WHEN** the project `shop` has `frontend` (branch `main`, remote
  `https://github.com/shop/frontend`) and `backend` (branch `dev`, no remote)
- **THEN** `lado project show shop` prints `  repositories:`, `    backend   dev
  (no remote)` and `    frontend  main  https://github.com/shop/frontend`, then its
  variables

#### Scenario: A link in the project's folder
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to `/srv/docs`
- **THEN** `lado project show shop` lists `    docs      (a link to /srv/docs: clone it into
  <ws>/projects/shop instead)` between `backend` and `frontend`

#### Scenario: A project whose folder is gone
- **WHEN** the folder of `acme` is gone and the human runs `lado project show acme`
- **THEN** it prints `  folder:  <ws>/projects/acme  (folder not found)` and
  `  repositories: none`

### Requirement: Agents cannot change projects

`lado project create`, `rename`, `delete`, `set`, `unset`, `author` with options, `repo add`
and `repo remove` SHALL refuse with `lado: lado project <command> is for the human; agent
"<agent>" cannot use it`, exit 1, changing nothing, when `LADO_AGENT` is set (every agent
has it). `list`, `show` and `author` without options SHALL work for agents. No MCP tool
SHALL make, change or delete a project or anything of it.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

#### Scenario: Adding a repository from an agent
- **WHEN** a worker runs `lado project repo add shop --new site` in its shell
- **THEN** it exits 1 with `lado: lado project repo add is for the human; agent
  "<agent>" cannot use it`, and no folder `site` is made

#### Scenario: Setting a variable from an agent
- **WHEN** a worker runs `lado project set shop MODEL_URL http://evil` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, and `shop` keeps its variables as they were

#### Scenario: Setting a secret from an agent
- **WHEN** a worker runs `printf x | lado project set shop GH_TOKEN --secret` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, before reading stdin, and `shop` keeps its secrets as they were

#### Scenario: A project's commit author from an agent
- **WHEN** a worker runs `lado project author shop --name Bot --email bot@x.example`, then
  `lado project author shop`
- **THEN** the first exits 1 with `lado: lado project author is for the human; agent
  "<agent>" cannot use it` and `shop`'s author is unchanged; the second prints it

### Requirement: lado project repo add --new makes a repository from scratch

`lado project repo add <id> --new <name>` SHALL make `<workspace>/projects/<id>/<name>` a
git repository with one empty commit, as `lado start --new` does (the author checked first:
the project's, else LADO's, else git's own; capability commit-authors), print `Made <folder>
a git repository with an empty first commit`, then the `Added repository` and `Start a
session in it` lines.

#### Scenario: From scratch
- **WHEN** the human runs `lado project repo add shop --new site`
- **THEN** `<ws>/projects/shop/site` is a git repository with one empty commit, and `lado
  project show shop` lists `site`

#### Scenario: No author
- **WHEN** git has no `user.name`, neither LADO nor `shop` has a commit author, and the
  human runs `lado project repo add shop --new site`
- **THEN** it exits 1 with the fresh start's text and hint, and no folder `site` is made

## ADDED Requirements

### Requirement: The project's page shows and sets its commit author

The project's page SHALL show, under its facts, a line `Commit author` ⓘ: without a
project author, who its repositories' agents commit as and from where, with `Set one for
this project`; with nobody anywhere `⚠ Nobody to commit as: agents cannot commit.` and a link
to LADO's author in Settings; with one, `<author> (this project's, in every repository)`
with `Edit`, `Remove` and Undo, as on Settings.

#### Scenario: A repository on a server with its own author
- **WHEN** LADO's author is `Ann Lee <ann@example.com>`, the project has none, and its
  repository `api` is on a server whose author is `Ivan Petrov <ivan@gitlab.example.com>`
- **THEN** the line reads `Ann Lee <ann@example.com> (LADO's); in api: Ivan Petrov
  <ivan@gitlab.example.com> (its git server's)` with `Set one for this project`

#### Scenario: Setting the project's author
- **WHEN** the human sets `Coffee Team <team@example.com>` on the page
- **THEN** the line reads `Coffee Team <team@example.com> (this project's, in every
  repository)` and `lado project author shop` prints it

### Requirement: Add repository from scratch shows the missing author

Add repository → From scratch SHALL show the note of the missing author between the name and
the buttons, with Create off, when nobody signs the project's commits (no project author,
no LADO author, no git author).

#### Scenario: Nobody
- **WHEN** nobody signs the commits and the human opens From scratch
- **THEN** the note with `Set it in Settings ↗` shows and Create is off
