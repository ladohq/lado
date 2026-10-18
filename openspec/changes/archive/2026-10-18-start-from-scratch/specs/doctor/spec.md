## ADDED Requirements

### Requirement: lado doctor checks git's author

`lado doctor` SHALL have a check `git author`, after `git`, by the same look as a fresh
start (`scratch.author_problem`, git's `user.name` and `user.email` outside any
repository): `OK` with `user.name and user.email set` when both are, `WARN` with `no
user.name or user.email: agents cannot commit` and the fresh start's hint (in LADO's
container the `.env` one, elsewhere the `git config --global` one) otherwise, and no line
when git itself does not run (the `git` check says why). It SHALL never print the name or
the email, and the check SHALL NOT change the exit status.

#### Scenario: A machine whose git knows the author
- **WHEN** git's global config has `user.name` and `user.email`
- **THEN** `lado doctor` prints `[ok  ] git author: user.name and user.email set`

#### Scenario: A fresh machine
- **WHEN** git has no `user.email`
- **THEN** `lado doctor` prints `[warn] git author: no user.name or user.email: agents
  cannot commit` with the `git config --global` command, and its exit status is that of
  the other checks
