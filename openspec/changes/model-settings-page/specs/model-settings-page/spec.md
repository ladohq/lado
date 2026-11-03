## ADDED Requirements

### Requirement: Settings has a section Models

The Settings page SHALL show a section **Models** after Providers and environment and
before Usage statistics, at the anchor `#models`, with two blocks: **Your models**, the
configured models, and under it **Sources**, where models come from: the agent CLIs and the
saved model servers.

#### Scenario: The anchor
- **WHEN** the human opens `/settings#models`
- **THEN** the page scrolls to the section Models, Your models above Sources

### Requirement: Your models without a model

With no configured model, Your models SHALL say `No models yet. Without them each agent
runs on its CLI's default model. Tick models in Sources below.`

#### Scenario: Nothing saved
- **WHEN** no model is saved and the human opens Settings
- **THEN** Your models shows that line and no table

### Requirement: Opening the section reads no list

Opening the section Models SHALL send no request to any model server and read no CLI's list
of models; Sources SHALL show each source closed.

#### Scenario: Two servers saved
- **WHEN** `LM Studio дома` and `LiteLLM` are saved and the human opens Settings
- **THEN** no request reaches either server, and every source is closed

### Requirement: The sources

Sources SHALL list every agent CLI LADO knows, then every saved server by name ignoring
case. A CLI not installed SHALL be greyed with `not installed` and not open; one installed
but not logged in SHALL be marked `not logged in` and open. A server SHALL show its name,
type and address; `+ Add server` SHALL follow the list.

#### Scenario: First open
- **WHEN** Claude Code, Codex CLI and OpenCode are installed and logged in, Kilo CLI is not
  installed, and no server is saved
- **THEN** Sources shows Claude Code, Codex CLI and OpenCode, Kilo CLI greyed with `not
  installed`, and `+ Add server`

### Requirement: Opening a source reads its list now

Opening a source SHALL read its models now, and **Refresh** in an open source SHALL read
them again: a CLI's aliases and its own list as the launch window's Model field reads them;
a server's list by a probe with its kept key; while it reads, the source SHALL say `reading
the models…`. LADO SHALL keep no source's list between reads.

#### Scenario: A new model on the server
- **WHEN** LM Studio got the model `gemma-3-12b` since the source was opened, and the human
  presses Refresh
- **THEN** `gemma-3-12b` shows in the list without a tick

### Requirement: A tick is a configured model

Each model of an open source SHALL have a tick per CLI that can run it: a CLI's source one
tick; a server's source a column per CLI that is installed and whose API the server
proves. A tick SHALL be on exactly when a configured model has that CLI, model and server.
Ticking SHALL save one with its default name as `lado model add` would; unticking SHALL
remove it.

#### Scenario: Claude Sonnet
- **WHEN** the human opens Claude Code and ticks `sonnet`
- **THEN** `Claude Sonnet` (Claude Code, sonnet, no server) shows in Your models

#### Scenario: One model on two CLIs
- **WHEN** the human opens `LiteLLM`, which proves chat completions and the Responses API,
  and ticks `qwen3-8b` under OpenCode and under Codex CLI
- **THEN** Your models shows two models of `qwen3-8b` on `LiteLLM`, one of each CLI

### Requirement: A model's default name

A model ticked or added SHALL be named: an alias of a CLI, the first word of the CLI's
title and the alias with its first letter capitalised (`Claude Sonnet`); a model of a
CLI's own list, the model; a model on a server, `<model> · <server>`. A name taken SHALL
get ` · <CLI title>` added, and then ` (2)`, ` (3)` until free.

#### Scenario: The same model on a second CLI
- **WHEN** `qwen3-8b · LiteLLM` of OpenCode is saved and the human ticks `qwen3-8b` under
  Codex CLI
- **THEN** the new model is named `qwen3-8b · LiteLLM · Codex CLI`

### Requirement: A tick of several models

When several configured models have the same CLI, model and server, their tick SHALL be on
and disabled, its title naming them; they SHALL be removed in Your models.

#### Scenario: Two names for one model
- **WHEN** `Claude Opus` and `Сильная` are both Claude Code's `opus`
- **THEN** the tick of `opus` under Claude Code is on and disabled, and its title names
  both

### Requirement: Search in a long list

An open source with more than ten models SHALL have a search field above its list that
shows only the models whose name holds the typed text, ignoring case; the models missing
from the list (below) SHALL always show.

#### Scenario: A server with a hundred models
- **WHEN** the human types `qwen` in the search of a server with 100 models
- **THEN** only the models whose name holds `qwen` show

### Requirement: Embeddings models are shown, not ticked

A model the server types embeddings SHALL be shown greyed with `(embeddings)` and its
ticks disabled.

#### Scenario: LM Studio's embeddings model
- **WHEN** the human opens `LM Studio дома`, which types
  `text-embedding-nomic-embed-text-v1.5` embeddings
- **THEN** it shows greyed with `(embeddings)` and cannot be ticked

### Requirement: A model its source no longer lists

When a source's list was read and lacks the model of a configured model of that source,
the model SHALL show first in the list, ticked, with `not in the server's list` (a CLI's:
`not in <CLI title>'s list`), and in Your models with the warning `not in <source>'s list
of models`. Nothing SHALL remove it but the human.

#### Scenario: A model gone from the server
- **WHEN** `mistral-7b · LiteLLM` is saved and `LiteLLM` no longer lists `mistral-7b`, and
  the human opens `LiteLLM`
- **THEN** `mistral-7b` shows first, ticked, marked `not in the server's list`, and the
  model stays saved

### Requirement: A server that does not answer

When an open server does not answer, asks for a key or refuses it, the source SHALL show
the probe's line and its hint (the container's `host.docker.internal` one included) as a
warning, and name its configured models, which SHALL stay.

#### Scenario: LM Studio switched off
- **WHEN** `Локальная Gemma` is on `LM Studio дома`, which is off, and the human opens it
- **THEN** it shows `⚠ http://localhost:1234 does not answer (connection refused)` and
  `Локальная Gemma` stays saved

### Requirement: Other model

An open source SHALL end with **Other model…**: a field for a model its list lacks (with a
CLI choice for a server: the CLIs of its columns), the check `lado model add` would make
shown under the field once the typing settles, and Add, which saves the model with its
default name as `lado model add` does.

#### Scenario: Claude Code's full model name
- **WHEN** the human types `claude-opus-5-5` in Other model… of Claude Code
- **THEN** the note is a warning that LADO cannot check `claude-opus-5-5`, and Add saves it

### Requirement: The table of Your models

Your models SHALL show the configured models by name ignoring case: Name, CLI (its title),
Model, Source (its server, else its CLI) and Remove, which removes the model at once as
`lado model remove` does. A model of a CLI not installed SHALL show `<CLI title> is not
installed` as a warning.

#### Scenario: Removing a model
- **WHEN** the human presses Remove on `Claude Sonnet`
- **THEN** it is gone from Your models and the tick of `sonnet` under Claude Code is off

### Requirement: Renaming a model in place

**✎** by a model's name SHALL turn the name into a field with Save and Cancel; Save SHALL
rename the model under the rules of a model's name, a refusal under the field; its CLI,
model and server SHALL stay.

#### Scenario: Claude Sonnet becomes Сильная
- **WHEN** the human renames `Claude Sonnet` to `Сильная`
- **THEN** Your models shows `Сильная` with Claude Code and sonnet, and `lado model list`
  shows it too

#### Scenario: A name taken
- **WHEN** the human renames a model to the name of another, in another case
- **THEN** under the field it shows the name-taken line, and nothing changes

### Requirement: The page adds a server as lado model-server add does

`+ Add server` SHALL open a form with Name, Address and Key (optional); Add SHALL probe and
save the server as `lado model-server add <name> <address> [--key]` does, Add disabled
with `checking the server…` while it probes, no longer than the command. On success the
server SHALL show in Sources, open, with `Saved model server "<name>".` and its CLIs.

#### Scenario: LiteLLM
- **WHEN** the human adds `LiteLLM` at `10.0.0.5:4000` with its key, and it answers
- **THEN** `LiteLLM` shows open in Sources with its models and `Saved model server
  "LiteLLM".`, and `lado model-server list` shows it

### Requirement: The same address and plain http are said, not refused

A line `same address as model server "<name>"` SHALL show in a server's source after it is
added or changed, for each other saved server at its address; the command's plain-http
warning SHALL show under the Key field. Neither SHALL stop the save.

#### Scenario: The same address under a second name
- **WHEN** `gateway` is saved at `http://10.0.0.5:4000` and the human adds `LiteLLM` at
  `10.0.0.5:4000/v1/`
- **THEN** `LiteLLM` is saved and shows `same address as model server "gateway"`

### Requirement: A refusal is the command's line under its field

Every refusal and warning SHALL be the line the matching command prints, its hint under
it, under the field it concerns: Name, Address or Key of a server; Other model's field or
CLI; a rename's field; a refusal of no field under the buttons or the tick's row. The form
SHALL keep its values but the key's.

#### Scenario: A gateway that asks for a key
- **WHEN** the human adds `work` at `https://gw.corp/llm` without a key and it answers 401
- **THEN** under Key it shows `https://gw.corp/llm asks for a key (401): run lado
  model-server add "work" https://gw.corp/llm --key`

#### Scenario: An address that does not answer
- **WHEN** the human adds `lab` at `http://127.0.0.1:<a closed port>`
- **THEN** under Address it shows `http://127.0.0.1:<port> does not answer (connection
  refused)`, and the form keeps `lab` and the address

### Requirement: The notes look as the launch window's

A warning, a refusal and an ok SHALL look as the launch window's notes do, and no note SHALL
cover a field or another note.

#### Scenario: Two notes under one field
- **WHEN** an address does not answer in LADO's container
- **THEN** the refusal and the container's hint show one under the other under Address,
  the field still visible

### Requirement: Change replaces a server's address or key

**Change** of a server SHALL open its Address, filled, and New key, empty; Save SHALL
replace the server as `lado model-server add <name> <address> [--key] --replace` does, with
the kept key, kept, when New key is empty. Its models SHALL keep referring to it; a failed
probe SHALL change nothing.

#### Scenario: A new key for a gateway
- **WHEN** `work` is saved with a key and the human saves a new key in New key, which the
  server takes
- **THEN** the server's key file holds the new key, and its models still name `work`

#### Scenario: Another port, the key kept
- **WHEN** `LM Studio дома` moved to port 1235 and the human changes its address with New
  key empty
- **THEN** it shows `http://localhost:1235`, and its key, if any, stays

### Requirement: Removing a server removes its models after a confirmation

**Remove** of a server SHALL ask in its source: `Remove <name>?`, or with models `Remove
<name> and its <n> models: <name>, <name>?`; only its confirmation SHALL remove them as
`lado model-server remove <name> --with-models` does.

#### Scenario: A server with three models
- **WHEN** three models refer to `LiteLLM` and the human removes it and confirms
- **THEN** the models, the server and its key folder are gone

#### Scenario: Cancel
- **WHEN** the human presses Cancel at the confirmation
- **THEN** the server and its models stay

### Requirement: A server's key enters the API and never leaves it

A server's key SHALL reach the page's API only in the body of a POST, never in an address.
No answer of the API (refusals and validation errors included), the server's log, the error
journal, the change feed, `lado.db` or any file of `LADO_HOME` but the server's key file
SHALL hold its value.

#### Scenario: The canary
- **WHEN** a unique key is sent through a real server's API to add a server, to change it,
  in a request the server refuses as unreadable and in one whose probe is refused
- **THEN** no answer, no line of the server's log or the error journal, and no file of
  `LADO_HOME` but `model-servers/<id>/key` holds the key

### Requirement: The page keeps the key only in its field

The Key and New key fields SHALL be the dots field of a project's secrets, not a password
field; the page SHALL keep the key only in its field, never in the page's state, an address
or the browser's storage, and SHALL empty the field after a send, on Cancel and when the
form closes.

#### Scenario: Cancel
- **WHEN** the human types a key, presses Cancel and opens + Add server again
- **THEN** the Key field is empty

### Requirement: The section fits a phone

On a window narrower than 464 px the section's forms SHALL show their fields one under the
other and no part of the section SHALL make the page scroll sideways; a wide source's list
MAY scroll sideways within itself.

#### Scenario: A server's list on a phone
- **WHEN** the human opens a server with three CLI columns in a window 390 px wide
- **THEN** the page does not scroll sideways

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server or model by themselves, and SHALL NOT
change how `lado start`, the launch window, a resume or any agent behaves.

#### Scenario: Models saved through the page
- **WHEN** the human saved servers and models through the page and starts a session
  without `--model`
- **THEN** the session's agents start on their CLI's default, as without them
