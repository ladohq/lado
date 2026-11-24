## MODIFIED Requirements

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
