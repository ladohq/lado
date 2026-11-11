## ADDED Requirements

### Requirement: Only folders count as agent config folders

`lado doctor`'s check `Agent config folders` SHALL count as a session's or an agent's config
folder only a folder under `LADO_HOME/agents/` (or under a session's folder there) whose name
does not start with `.`; files and hidden names SHALL be neither listed nor offered for
removal.

#### Scenario: Finder's .DS_Store
- **WHEN** `LADO_HOME/agents/` holds the file `.DS_Store`, and `LADO_HOME/agents/s/` of a
  running session `s` holds `.DS_Store` beside its running agents' folders
- **THEN** the check is `[ok  ]` "only those of running agents"

#### Scenario: A folder left beside a file
- **WHEN** `LADO_HOME/agents/` holds `.DS_Store`, a file `notes`, and the folder `old` of a
  session that does not run
- **THEN** the check warns with `LADO_HOME/agents/old` alone, and its `rm -rf` names only it
