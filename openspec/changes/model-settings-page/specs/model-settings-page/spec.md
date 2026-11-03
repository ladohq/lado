## ADDED Requirements

### Requirement: Settings has a section Models

The Settings page SHALL show a section **Models** after Providers and environment and
before Usage statistics, at the anchor `#models`, with the line `Models set once under
names; sessions will refer to them by name. No session uses them yet.` and two blocks: **Your
models** and, under it, **Model servers**. A block with nothing saved SHALL say `No models
yet.` or `No servers yet.` above its add button.

#### Scenario: Nothing saved
- **WHEN** no server and no model is saved and the human opens Settings
- **THEN** the section Models shows `No models yet.`, `+ Add model`, `No servers yet.` and
  `+ Add server`

#### Scenario: The anchor
- **WHEN** the human opens `/settings#models`
- **THEN** the page scrolls to the section Models

### Requirement: Opening the section asks no server

Opening the section Models SHALL send no request to any model server and run no CLI but
the version check of the CLIs whose provider declares ready-made models.

#### Scenario: Two servers saved
- **WHEN** `LM Studio дома` and `work` are saved and the human opens Settings
- **THEN** no request reaches either server

### Requirement: The page adds a server as lado model-server add does

**+ Add server** SHALL open a form with the fields Name, Address and Key (optional); Add
SHALL probe the address with the key and save the server exactly as `lado model-server add
<name> <address> [--key]` does: the same rules, checks and lines, and a probe no longer
than the command's. While it probes, Add SHALL be disabled and the form SHALL say `checking
the server…`.

#### Scenario: Adding while the probe runs
- **WHEN** the human presses Add and the server takes a few seconds to answer
- **THEN** the form says `checking the server…` and Add is disabled until the answer

#### Scenario: Saved as the command saves it
- **WHEN** the human adds `LM Studio дома` at `localhost:1234`, where LM Studio answers
- **THEN** `lado model-server list` shows `LM Studio дома` with `http://localhost:1234`

### Requirement: A server added shows what the probe found

On success the form SHALL close and the new server's row SHALL show `Saved model server
"<name>".` and the probe's findings: its type, address, models (each the server types
embeddings followed by `(embeddings)`, or `no list (<why>)`), the CLIs that can use it with
their API and those that cannot with the API they lack, and whether a key is kept.

#### Scenario: LM Studio with an embeddings model
- **WHEN** the human adds `LM Studio дома` at `localhost:1234`, where LM Studio answers with
  `qwen3-8b` and `text-embedding-nomic-embed-text-v1.5` typed embeddings
- **THEN** the row shows `LM Studio`, `http://localhost:1234`, `qwen3-8b,
  text-embedding-nomic-embed-text-v1.5 (embeddings)`, Kilo CLI and OpenCode as able to use
  it, and `Saved model server "LM Studio дома".`

### Requirement: The same address and plain http are said, not refused

A line `same address as model server "<name>"` SHALL show under a server's row after it is
added or changed, for each other saved server at its address; the command's plain-http
warning SHALL show under the Key field. Neither SHALL stop the save.

#### Scenario: The same address under a second name
- **WHEN** `LM Studio дома` is saved at `http://localhost:1234` and the human adds `macpro`
  at `localhost:1234/v1/`
- **THEN** `macpro` is saved and its row shows `same address as model server "LM Studio
  дома"`

#### Scenario: A key over plain http
- **WHEN** the human adds `ext` at `http://llm.example.com` with a key, and the server
  takes it
- **THEN** `ext` is saved and under Key it shows the warning naming `llm.example.com`

### Requirement: A refusal is the command's line

Every refusal and warning of the page SHALL be the line the matching command prints (`lado
model-server add`, `lado model add`, `lado model-server remove`, `lado model remove`), with
its hint under it. A refusal SHALL keep the form and its values, the key's field emptied.

#### Scenario: An address that does not answer
- **WHEN** the human adds `lab` at `http://127.0.0.1:<a closed port>`
- **THEN** it shows `http://127.0.0.1:<port> does not answer (connection refused)`, nothing
  is saved, and the form keeps `lab` and the address

#### Scenario: Localhost in LADO's container
- **WHEN** LADO runs in its container and the human adds `lab` at `localhost:1234`, which
  does not answer
- **THEN** it shows the line that it does not answer and, under it, the command's hint
  naming `http://host.docker.internal:1234`

### Requirement: A refusal shows under the field it concerns

A refusal SHALL show under the field it concerns: a server's name under Name; an address
the probe does not take, one that does not answer, a TLS failure and an unknown server
under Address; a key asked for, refused, or that no header can carry under Key. A refusal
of no field SHALL show under the form's buttons.

#### Scenario: A gateway that asks for a key
- **WHEN** the human adds `work` at `https://gw.corp/llm` without a key and the server
  answers 401
- **THEN** under Key it shows `https://gw.corp/llm asks for a key (401): run lado
  model-server add "work" https://gw.corp/llm --key`

#### Scenario: A name taken
- **WHEN** `LM Studio дома` is saved and the human adds a server `lm studio ДОМА`
- **THEN** under Name it shows the command's name-taken line, and no request reaches the
  address

### Requirement: A model's refusal shows under its field

A model's refusal SHALL show under the field it concerns: its name under Name, its CLI
under CLI, a server not saved, not answering or not suiting the CLI under Server, and the
model empty, an embeddings model or one not in the list under Model.

#### Scenario: A server that does not suit the CLI
- **WHEN** `LM Studio дома` proves only chat completions and the human adds a model of
  Codex CLI on it
- **THEN** under Server it shows `LM Studio дома does not suit Codex CLI: it has no
  Responses API; it suits Kilo CLI, OpenCode`, and nothing is saved

#### Scenario: An embeddings model typed by hand
- **WHEN** the human types `text-embedding-nomic-embed-text-v1.5` on `LM Studio дома`, which
  types it embeddings, and presses Add
- **THEN** under Model it shows the command's line `text-embedding-nomic-embed-text-v1.5 is
  an embeddings model on LM Studio дома; an agent needs a chat model: …`, and nothing is
  saved

### Requirement: The notes look as the launch window's

A warning under a field SHALL look as the launch window's warning, a refusal as its
refusal, and an ok as its ok; no note SHALL cover a field or another note.

#### Scenario: Two notes in one form
- **WHEN** the Name and the Server of a model are both refused
- **THEN** each refusal shows under its own field in the launch window's refusal look, and
  both fields stay visible and usable

### Requirement: A server's row shows what was saved

A server's row SHALL show, without asking the server, its name, type, address, the CLIs
whose API it proved when saved and whether a key is kept.

#### Scenario: Opening the page
- **WHEN** `LM Studio дома` is saved without a key and the human opens Settings
- **THEN** its row shows `LM Studio`, `http://localhost:1234`, Kilo CLI and OpenCode, and
  `key: no`

### Requirement: Check asks a server again

**Check** in a server's row SHALL probe the server with its kept key, as adding it does,
and show its models and CLIs in the row, or the probe's line as a warning in the row; it
SHALL change nothing saved.

#### Scenario: A server that answers
- **WHEN** the human presses Check on `LM Studio дома`, which lists `qwen3-8b`
- **THEN** the row shows `qwen3-8b` among its models

#### Scenario: A server that went away
- **WHEN** the human presses Check on `work`, which no longer answers
- **THEN** the row shows `⚠ https://gw.corp/llm does not answer (<why>)` and `work` stays
  saved as it was

### Requirement: Change replaces a server's address or key

**Change** in a server's row SHALL open its Address, filled with the saved address, and a
New key field, empty; Save SHALL replace the server as `lado model-server add <name>
<address> [--key] --replace` does, with the new key, or with the kept key, kept, when New
key is empty. Its models SHALL keep referring to it; a failed probe SHALL change nothing.

#### Scenario: A new key for a gateway
- **WHEN** `work` is saved with a key and the human types a new key in New key and saves,
  and the server takes it
- **THEN** the server's key file holds the new key, and its models still name `work`

#### Scenario: Another port, the key kept
- **WHEN** `LM Studio дома` moved to port 1235 and the human changes its address with New
  key empty
- **THEN** its row shows `http://localhost:1235`, and its key, if any, stays

#### Scenario: The new address does not answer
- **WHEN** the human changes a server's address to one that does not answer
- **THEN** under Address it shows the line, and the saved address and key are as before

### Requirement: Removing a server asks in its row

**Remove** in a server's row SHALL ask `Remove <name>?` in the row, and only its second
Remove SHALL remove the server and its key file, as `lado model-server remove` does. A
server a model refers to SHALL NOT be removed: the row SHALL show the command's line naming
every model that refers to it.

#### Scenario: A server two models use
- **WHEN** `Локальная Qwen` and `Локальная Gemma` refer to `LM Studio дома` and the human
  removes `LM Studio дома`
- **THEN** the row shows `model server "LM Studio дома" is used by the models Локальная
  Qwen, Локальная Gemma; remove them first: lado model remove "Локальная Qwen" "Локальная
  Gemma"`, and the server stays

#### Scenario: A server no model uses
- **WHEN** no model refers to `work` and the human removes it and confirms
- **THEN** its row is gone and its folder under `<LADO_HOME>/model-servers/` is gone

### Requirement: The page adds a model as lado model add does

**+ Add model** SHALL open a form with the fields Name, CLI (every CLI LADO knows, one not
installed marked `(not installed)`), Server (`—` for the CLI's own service, then every
saved server) and Model; Add SHALL check and save the model exactly as `lado model add
<name> --cli <cli> --model <model> [--server <server>]` does: the same checks in the same
order and the same lines.

#### Scenario: A model on LM Studio
- **WHEN** `LM Studio дома` answers and lists `qwen3-8b`, and the human adds `Локальная
  Qwen`, OpenCode, `LM Studio дома`, `qwen3-8b`
- **THEN** `lado model list` shows `Локальная Qwen  OpenCode  qwen3-8b  LM Studio дома`

### Requirement: The table of Your models

Your models SHALL show a table of the saved models, sorted by name ignoring case, with the
columns Name, CLI (its title), Model and Server (`—` for none), and Remove in each row. A
model just added with a warning of its check SHALL show the warning in its row until the
page is left.

#### Scenario: Two models
- **WHEN** `Claude Haiku` (Claude Code, haiku) and `Локальная Qwen` (OpenCode, qwen3-8b on
  `LM Studio дома`) are saved
- **THEN** the table shows `Claude Haiku  Claude Code  haiku  —` and `Локальная Qwen
  OpenCode  qwen3-8b  LM Studio дома`

### Requirement: The Model field suggests as the launch window's

The Model field SHALL be the launch window's field with suggestions: without a server, the
CLI's aliases (tagged `alias`) and its own list; with a server, the server's models from a
probe with its kept key, without those the server types embeddings.

#### Scenario: A server's models
- **WHEN** the human chooses OpenCode and `LM Studio дома` and types `gem`
- **THEN** the suggestions show `gemma-3-12b` and not the embeddings model

### Requirement: The Model field checks the model as it is typed

Under the Model field SHALL show, once the typing settles, the check `lado model add` would
make of the name, CLI, server and model given, nothing saved: `✓` and the check's text, `⚠`
and the warning, or the refusal, and `checking the model…` while it runs. A server's probe
for the check MAY be kept up to a minute; Add SHALL probe the server again.

#### Scenario: A model in the server's list
- **WHEN** the human picks `gemma-3-12b` on `LM Studio дома`
- **THEN** the note says `✓ in LM Studio дома's list of models`

#### Scenario: A model Claude Code cannot list
- **WHEN** the human chooses Claude Code, no server, and types `claude-mini-9`
- **THEN** the note is a warning that LADO cannot check `claude-mini-9`

### Requirement: Removing a model asks in its row

**Remove** in a model's row SHALL ask `Remove <name>?` in the row, and only its second
Remove SHALL remove the model as `lado model remove <name>` does; its server SHALL stay.
Models SHALL be removed one at a time.

#### Scenario: Removing the last model of a server
- **WHEN** `Локальная Qwen` is the only model on `LM Studio дома` and the human removes it
- **THEN** it is gone from the table, and removing `LM Studio дома` then succeeds

### Requirement: Ready-made models of the installed CLIs

Under Your models the page SHALL offer, for each installed CLI whose provider declares
ready-made models, a chip `+ <name> · <model>` per ready-made model that no saved model of
that CLI has (the same CLI and model); a click SHALL add it as + Add model would, with no
server. A chip's refusal (its name taken) SHALL show under the chips.

#### Scenario: One click
- **WHEN** Claude Code is installed and the human clicks `+ Claude Opus · opus`
- **THEN** `Claude Opus` (Claude Code, opus, no server) is saved and its chip is gone

#### Scenario: Claude Code not installed
- **WHEN** Claude Code is not installed
- **THEN** no ready-made model is offered

### Requirement: Several ready-made models at once

With two or three chips of a CLI shown, a button `Add both` or `Add all three` SHALL add
them in their order, as their clicks would; one refused SHALL NOT stop the others.

#### Scenario: Add all three
- **WHEN** Claude Code is installed, no model is saved, and the human clicks `Add all three`
- **THEN** `Claude Haiku`, `Claude Sonnet` and `Claude Opus` are saved and no chip is left

### Requirement: The ready-made models of each CLI

Claude Code SHALL declare the ready-made models `Claude Haiku · haiku`, `Claude Sonnet ·
sonnet` and `Claude Opus · opus`, each an alias of Claude Code; the other CLIs SHALL
declare none, and the page SHALL show no chip for them.

#### Scenario: Claude Code installed, nothing saved
- **WHEN** Claude Code is installed and no model is saved
- **THEN** the page shows `+ Claude Haiku · haiku`, `+ Claude Sonnet · sonnet`, `+ Claude
  Opus · opus` and `Add all three`

#### Scenario: Only Codex CLI installed
- **WHEN** Codex CLI is installed and Claude Code is not
- **THEN** no chip is shown

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

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server or model by themselves, and SHALL NOT
change how `lado start`, the launch window, a resume or any agent behaves.

#### Scenario: Servers and models saved through the page
- **WHEN** the human saved servers and models through the page and starts a session
  without `--model`
- **THEN** the session's agents start on their CLI's default, as without them

### Requirement: The section fits a phone

On a window narrower than 464 px the section's forms SHALL show their fields one under the
other, a server's row its buttons under its name, and the table of Your models SHALL fit
the width, with no horizontal scroll of the page.

#### Scenario: Adding a model on a phone
- **WHEN** the human opens + Add model in a window 390 px wide
- **THEN** Name, CLI, Server and Model show one under the other and the page does not
  scroll sideways
