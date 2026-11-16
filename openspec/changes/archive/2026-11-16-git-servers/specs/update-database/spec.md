## ADDED Requirements

### Requirement: The plan of an update to an older schema names git servers and their tokens

The warning of the plan of an update to an older schema SHALL name saved git servers among
what is lost, and SHALL list each folder of `<LADO_HOME>/git-servers/` that holds a token
file and whose name is no git server id of the copy of `lado.db` (none for a copy without
the table), saying these tokens stay on disk until removed. With no such folder there SHALL
be no such list; an unreadable folder SHALL be listed itself, and the plan SHALL go on.

#### Scenario: Back to a version without git servers
- **WHEN** `lado.db` has schema 41, the copy `backups/lado.db.schema-40` has no table of git
  servers, `<LADO_HOME>/git-servers/3f9a0c12d4e5/token` exists, and the human runs
  `lado update 0.47.0`
- **THEN** the warning's list of what is lost has `git servers`, and stderr has
  `Git server tokens stay on disk; remove them when you no longer need them:` and the line
  of `<LADO_HOME>/git-servers/3f9a0c12d4e5`, before `Update? [y/N]`

#### Scenario: No token left behind
- **WHEN** `<LADO_HOME>/git-servers/` is missing, or holds only folders with no token file
- **THEN** the warning has no line about tokens
