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
