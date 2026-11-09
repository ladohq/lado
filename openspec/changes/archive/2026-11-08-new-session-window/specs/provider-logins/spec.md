## MODIFIED Requirements

### Requirement: The New session window offers only CLIs that can start

The New session and Resume windows SHALL show a provider with `login_missing` in Agent as a
disabled option "`<title>` · not logged in", never choose it by itself, and, with it suggested
or chosen, open Team, show under Agent "`<CLI>` is not logged in: its agents cannot start. Log
in first" leading to Settings → Agent CLIs and environment, keep the start button off with
`To start: log in to <CLI>`, and read the list for the session's project.

#### Scenario: The folder's last session was Claude
- **WHEN** Claude Code is not logged in and the New session window opens on a folder whose
  last session ran `claude`
- **THEN** Agent shows "choose…", the option "Claude Code · not logged in" is disabled, the
  red note with "Log in first" is shown, and the start button is off

#### Scenario: Log in first
- **WHEN** the human follows "Log in first"
- **THEN** the window closes and Settings → Agent CLIs and environment opens

#### Scenario: The project's own login
- **WHEN** Where is on a repository of project `shop`, whose secrets log Claude Code in
- **THEN** Claude Code can be chosen and the start button is on

#### Scenario: Resume without a login
- **WHEN** the Resume window opens for a stopped Claude session and Claude Code is not
  logged in
- **THEN** the option "Claude Code · not logged in" is disabled, the red note "Claude Code
  is not logged in: its agents cannot start. Log in first" is shown, its link leading to
  Settings → Agent CLIs and environment, and `Resume <name>` is off until another CLI with a
  login is chosen

#### Scenario: A default on a model server
- **WHEN** Claude Code is not logged in and its default model is on a model server
- **THEN** it has no `login_missing`, Claude Code can be chosen and the start button is on
