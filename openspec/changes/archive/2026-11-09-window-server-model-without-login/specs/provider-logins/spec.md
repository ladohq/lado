## MODIFIED Requirements

### Requirement: The providers list says which CLI lacks the login it needs

`GET /api/providers` SHALL give, for each provider, `login_missing`: true when its agents
need a login for the CLI's own models and its status, read in the environment of the agents
without a project, or with the project `project=<id>` names, is not logged in, whatever its
default model; false otherwise, also when the status cannot be read. An unknown project
SHALL be 404.

#### Scenario: Claude Code without a login
- **WHEN** Claude Code is installed and not logged in, and the UI asks `GET /api/providers`
- **THEN** Claude Code's entry has `login_missing: true`, and Kilo's `false` whatever its
  login

#### Scenario: Asked for a project with its own login
- **WHEN** project `shop` has the secret `CLAUDE_CODE_OAUTH_TOKEN` and LADO has no Claude
  Code login, and the UI asks `GET /api/providers?project=shop`
- **THEN** Claude Code's entry has `login_missing: false`

### Requirement: The New session window offers only CLIs that can start

The New session and Resume windows SHALL show a provider with `login_missing` and without
`starts_on_server` in Agent as a disabled option "`<title>` · not logged in", never choose it
by itself, and, with it suggested or chosen, open Team, show under Agent "`<CLI>` is not
logged in: its agents cannot start. Log in first" leading to Settings → Agent CLIs and
environment, keep the start button off with `To start: log in to <CLI>`, and read the list
for the session's project.

#### Scenario: The folder's last session was Claude
- **WHEN** Claude Code is not logged in, has no saved model, and the New session window opens
  on a folder whose last session ran `claude`
- **THEN** Agent shows "choose…", the option "Claude Code · not logged in" is disabled, the
  red note with "Log in first" is shown, and the start button is off

#### Scenario: Log in first
- **WHEN** the human follows "Log in first"
- **THEN** the window closes and Settings → Agent CLIs and environment opens

#### Scenario: The project's own login
- **WHEN** Where is on a repository of project `shop`, whose secrets log Claude Code in
- **THEN** Claude Code can be chosen and the start button is on

#### Scenario: Resume without a login
- **WHEN** the Resume window opens for a stopped Claude session, Claude Code is not logged
  in and has no saved model
- **THEN** the option "Claude Code · not logged in" is disabled, the red note "Claude Code
  is not logged in: its agents cannot start. Log in first" is shown, its link leading to
  Settings → Agent CLIs and environment, and `Resume <name>` is off until another CLI with a
  login is chosen

#### Scenario: A default on a model server
- **WHEN** Claude Code is not logged in and its default model is on a model server
- **THEN** Claude Code can be chosen, the Model field holds that default and the start button is on

## ADDED Requirements

### Requirement: The providers list says which CLI starts on a server without its login

`GET /api/providers` SHALL give, for each provider, `starts_on_server`: true when `login_missing`
is true and its agents can still start without the login on a saved model of a server (the CLI
takes that server's whole process and has a saved model); false otherwise.

#### Scenario: A saved model of a server
- **WHEN** Claude Code is not logged in and `CloudClaude` on `OpenRouter` is a saved model of
  Claude Code, its default or not
- **THEN** Claude Code's entry has `login_missing: true` and `starts_on_server: true`

#### Scenario: No saved model
- **WHEN** Codex is not logged in, its model needs a login, and no saved model is Codex's
- **THEN** Codex's entry has `login_missing: true` and `starts_on_server: false`

### Requirement: The window offers a CLI without its login for its server's models

The New session and Resume windows SHALL offer a provider with `starts_on_server` as "`<title>
<version>` · not logged in: your server's models only", take it when suggested, and show under
Agent the plain note "`<CLI>` is not logged in: its agents run on your server's models only. Log in
for its own models."

#### Scenario: A saved model of a server, not the default
- **WHEN** Claude Code is not logged in, has no default model, `CloudClaude` on `OpenRouter` is
  its one saved model, and the New session window opens on a folder whose last session ran
  `claude`
- **THEN** Agent holds "Claude Code 2.1.295 · not logged in: your server's models only", the
  plain note "Claude Code is not logged in: its agents run on your server's models only. Log in
  for its own models." stands under it, the Model field holds `CloudClaude` on `OpenRouter` with
  "For this session only: Claude Code is not logged in, so it runs on your server's model.",
  the start button is on, and the session starts on `CloudClaude`

#### Scenario: Codex with a server model
- **WHEN** Codex is not logged in, its model needs a login, and `CloudCodex` is its saved model
- **THEN** Codex CLI can be chosen as Claude Code can, and starts on `CloudCodex`

#### Scenario: Resume on a server's model
- **WHEN** the Resume window opens for a stopped Claude session that ran on `CloudClaude`, and
  Claude Code is not logged in
- **THEN** Claude Code stays chosen with the plain note, the field holds `CloudClaude`, and
  `Resume <name>` is on

### Requirement: The window's Model field refuses what needs the missing login

For a chosen CLI with `login_missing` and `starts_on_server`, the launch window's Model field SHALL
refuse a built-in model and the CLI's settings before the start, with the start's reason and the
ways out `Use <server model>` and `Log in first`, and SHALL mark them `needs login` in its list.

#### Scenario: A built-in model picked
- **WHEN** Claude Code is not logged in, `CloudClaude` is its saved model, and the human picks
  `opus` in the Model field
- **THEN** the note reads "Claude Code is not logged in, so it cannot run opus: pick a model of
  your server, or log in first." with `Use CloudClaude` and `Log in first`, the summary's mark is
  `! needs login`, and the footer reads `To start: fix the model`

#### Scenario: The marks of the list
- **WHEN** that human opens the Model list
- **THEN** `Claude Code's settings`, `opus` and `sonnet` carry `needs login`, and `CloudClaude`
  none

#### Scenario: The check over the API
- **WHEN** Claude Code is not logged in and `POST /api/session-model/check` asks for `opus`
- **THEN** the answer is of kind `refused` with `login: true` and the text of the note; asked for
  `CloudClaude`, it is `ok`

#### Scenario: Logged in
- **WHEN** Claude Code is logged in
- **THEN** no model is marked `needs login`, the check of `opus` reads no login, and the field is
  never set by itself

### Requirement: A new session takes the one server model a CLI without its login can run

When the chosen CLI has `login_missing` and `starts_on_server` and a new session's Model field would
open on a value that needs the login, the field SHALL take the CLI's saved model by itself when it
has exactly one, and none when it has several.

#### Scenario: One saved model
- **WHEN** Claude Code is not logged in, its default is `opus`, and `CloudClaude` is its one saved
  model
- **THEN** a new session's field holds `CloudClaude` with "For this session only: Claude Code is
  not logged in, so it runs on your server's model.", and the start button is on

#### Scenario: Several saved models
- **WHEN** Claude Code is not logged in, has no default, and `CloudClaude` and `CloudOpus` are its
  saved models
- **THEN** the field reads `Claude Code's settings` with "Claude Code is not logged in, so it
  runs on your server's models only: pick one." and `Log in first`, and the start button is off
  until a saved model is picked
