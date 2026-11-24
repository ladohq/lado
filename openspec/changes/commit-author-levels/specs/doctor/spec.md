## MODIFIED Requirements

### Requirement: lado doctor checks git's author

`lado doctor` SHALL have a check `git author`, after `git`, by the same order as a fresh
start outside a project (capability commit-authors): `OK` with `LADO's commit author set` or `user.name and
user.email set`, else `WARN` with `no LADO commit author and no user.name or user.email:
agents cannot commit` and the fresh start's hint, and no line when git itself does not run
(the `git` check says why).

#### Scenario: A machine whose git knows the author
- **WHEN** git's global config has `user.name` and `user.email` and LADO has no author
- **THEN** `lado doctor` prints `[ok  ] git author: user.name and user.email set`

#### Scenario: LADO's author
- **WHEN** LADO's commit author is set and git has no `user.name`
- **THEN** `lado doctor` prints `[ok  ] git author: LADO's commit author set`

#### Scenario: A fresh machine
- **WHEN** git has no `user.email` and LADO has no author
- **THEN** `lado doctor` prints `[warn] git author: no LADO commit author and no user.name
  or user.email: agents cannot commit` with the `lado git-server author` command, and its
  exit status is that of the other checks
