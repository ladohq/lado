## Purpose
Settings → Models: the page where the human sees what each agent CLI and saved model
server offers and ticks the models to keep under names, renames them, and adds, changes
and removes servers, with the rules of `lado model-server` and `lado model`; and the API it
uses, which a server's key enters and never leaves.

## ADDED Requirements

### Requirement: Settings has a section Models

The Settings page SHALL show a section **Models** after Agent CLIs and environment and
before Usage statistics, at the anchor `#models`, with no tabs: an intro line, then three
blocks one under the other, each headed by its name and its count where it has one:
**Your models**, the configured models; **Model servers**, the saved servers and `Add
server`; **Models of your agent CLIs**, the agent CLIs LADO knows with their lists.

#### Scenario: The anchor
- **WHEN** the human opens `/settings#models`
- **THEN** the page scrolls to the section Models once, its three blocks one under the
  other

#### Scenario: Four models
- **WHEN** four models and two servers are saved
- **THEN** the blocks read `Your models 4` and `Model servers 2`

### Requirement: Opened at its anchor, Models stays at the top

When the page opens at `#models`, the page SHALL keep the top of Models at the top of the
view while the page around it grows, until the human first presses, scrolls, touches or
types; from then on the page is the human's.

#### Scenario: The anchor while the sections above grow
- **WHEN** the human opened `/settings#models` and Agent CLIs and environment, above, grows
  once its check ends, nothing pressed, scrolled or typed yet
- **THEN** the top of Models stays at the top of the view

#### Scenario: After the human's scroll
- **WHEN** the human scrolled the page opened at `#models` and a section above grows
- **THEN** the page scrolls nothing

### Requirement: Nothing moves under the pointer

No change in the section SHALL scroll the page or move the element the human acts on or
holds the focus on, whatever it changes above it: a tick, a rename, × and Undo, adding,
changing or removing a server, the section's reload after any of them, and a list's read
ending. The page SHALL keep that element at its place on the screen by scrolling by the
height changed above it, and SHALL scroll to `#models` only when it opens with that anchor.
No row SHALL leave the section on a timer.

#### Scenario: A tick adds a card above
- **WHEN** the human ticks a model in the middle of Kilo CLI's open list and its model adds a
  card to Your models above
- **THEN** the tick stays where it was on the screen, to the pixel

#### Scenario: A server added
- **WHEN** the human adds a server
- **THEN** the new server takes the place of the form, and the form's place on the screen
  does not move

#### Scenario: Nothing acted on
- **WHEN** the human opens `/settings` and presses nothing in Models while the sections above
  grow and Models renders its rows
- **THEN** the page stays where it is: only what the human acts on in Models is held in place

#### Scenario: A section above grows
- **WHEN** the human opened a source in Models and a section above grows while its list is
  read
- **THEN** the list's read ending scrolls nothing to make up for the section above

#### Scenario: The focus out of view
- **WHEN** the focus is on Kilo CLI's row, the human scrolled up so that Your models shows and
  Kilo CLI is below the view, and the blocks between them grow
- **THEN** the page scrolls nothing: what shows stays where it is

#### Scenario: Undo runs out while the human is below
- **WHEN** the human pressed × on a model, then works in Models of your agent CLIs, and ten
  seconds pass
- **THEN** nothing under the pointer moves: only the Undo of that row goes

### Requirement: Your models without a model

With no configured model, Your models SHALL say `No models yet. Without them each agent
runs on its agent CLI's default model.` and `Add a model server below, or tick the models
your agent CLIs already offer.`

#### Scenario: Nothing saved
- **WHEN** no model is saved and the human opens Settings
- **THEN** Your models shows those lines and no card

### Requirement: Opening the section reads no list

Opening the section Models SHALL send no request to any model server and read no CLI's list
of models; every source SHALL show closed.

#### Scenario: Two servers saved
- **WHEN** `LM Studio дома` and `LiteLLM` are saved and the human opens Settings → Models
- **THEN** no request reaches either server, and every source is closed

### Requirement: The sources

Model servers SHALL list every saved server by name ignoring case, then `Add server`.
Models of your agent CLIs SHALL list every agent CLI LADO knows in LADO's order, the ones not
installed last. An agent CLI not installed SHALL be greyed and not open; one not logged
in SHALL say `not logged in` and open.

#### Scenario: First open
- **WHEN** Claude Code, Codex CLI and OpenCode are installed and logged in, Kilo CLI is not
  installed, and no server is saved
- **THEN** Model servers shows only `Add server`, and Models of your agent CLIs shows Claude
  Code, Codex CLI and OpenCode, then Kilo CLI greyed

### Requirement: A source's row

Each source SHALL be one row: an open/close arrow in a framed box, its name, for a server
its type as a badge and `key` when it has one, and a second line: for a server how many
models it gave (`2 models added`, `no models added`) then its address; for an agent CLI its
login state and how many models it gave, after `aliases` or `its list` once its list was
read on the page (before a read the page cannot tell them apart without reading a list).

#### Scenario: LM Studio with two models
- **WHEN** `LM Studio дома` at `http://localhost:1234`, without a key, gave two models
- **THEN** its row says `LM Studio дома`, the badge `LM Studio`, and `2 models added ·
  http://localhost:1234`

#### Scenario: Claude Code read
- **WHEN** Claude Code is logged in with one model saved, and the human opens its source
- **THEN** its second line says `logged in · 1 added` before, and `aliases · logged in · 1
  added` once its list was read

### Requirement: A source opens from its whole row

A click anywhere on a source's row but its buttons SHALL open or close it, and so SHALL
Enter and Space on the row; the row SHALL show it can be clicked on hover, and its arrow
SHALL turn when open.

#### Scenario: A click on the name
- **WHEN** the human clicks the name `Kilo CLI`
- **THEN** Kilo CLI opens and its arrow points down

### Requirement: A long address stays on one line

A server's address SHALL be cut with `…` to the row's room, the whole address shown on
hover and on keyboard focus of the row; the server's **Change** (✎) and **Remove** (🗑)
SHALL be icons with their names in their labels and titles, staying on the row's line. On a
window narrower than 600 px the address SHALL wrap whole, and the icons SHALL go on a line
of their own under the name.

#### Scenario: A gateway with a long address
- **WHEN** a server's address is
  `https://litellm-gateway.platform.internal.example.com:4000/v1`
- **THEN** its row is one line ending in ✎ and 🗑, and hovering it or focusing it shows the
  whole address

### Requirement: A source shows its list, Change or Remove, one at a time

A server SHALL show at most one of its list of models, its Change form and its Remove
confirmation: opening one SHALL close the others. After Change saves, the list SHALL open
and be read again.

#### Scenario: Change of an open server
- **WHEN** LM Studio's list is open and the human presses ✎
- **THEN** the list closes and the Change form shows in its place

### Requirement: Opening a source reads its list now

Opening a source SHALL read its models now, and **Refresh** (↻, at the right above the
list) SHALL read them again: a CLI's aliases and its own list as the launch window's Model field reads them;
a server's list by a probe with its kept key; while it reads, the source SHALL say `reading
the models…`. LADO SHALL keep no source's list between reads.

#### Scenario: A new model on the server
- **WHEN** LM Studio got the model `gemma-3-12b` since the source was opened, and the human
  presses Refresh
- **THEN** `gemma-3-12b` shows in the list without a tick

### Requirement: A source's list keeps its height

An open source's list SHALL show at most about nine models and scroll within itself; the
models of the source's configured models SHALL come first, in the order read at opening or
Refresh, which no tick SHALL change; under the list a line SHALL say how many models it
has.

#### Scenario: Kilo CLI's 323 models
- **WHEN** the human opens Kilo CLI, which lists 323 models, one of them configured
- **THEN** the configured one is first, the list scrolls within itself, the page grows by
  the list's height only, and the line says `323 models`

### Requirement: A tick is a configured model

Each model of an open agent CLI's source SHALL have one tick, on exactly when a configured
model of that CLI, no server, has that model. Ticking SHALL save a model with its default name as `lado model add`
would; unticking SHALL remove it and leave no Undo row: the tick is its own undo. A ticked
row SHALL say `as <name>` when the name differs from the model.

#### Scenario: Claude Sonnet
- **WHEN** the human opens Claude Code and ticks `sonnet`
- **THEN** `Claude Sonnet` (Claude Code, sonnet, no server) shows in Your models and the
  row says `as Claude Sonnet`

#### Scenario: Unticked
- **WHEN** the human unticks `sonnet` under Claude Code
- **THEN** `Claude Sonnet` is removed, and Your models shows no Undo row for it

### Requirement: A server's model opens its CLIs

A click on a model of an open server, or Enter on it, SHALL open under its row a list of
the installed agent CLIs whose API the server proves, one under the other, each with its
tick and under its title `as <name>` when ticked; Esc SHALL close it. The row SHALL say `in <CLI title>, …`
for the agent CLIs it is configured in. A server no installed agent CLI can use SHALL say
`No installed CLI can use this server.` and have no ticks.

#### Scenario: qwen3-8b in OpenCode and Kilo CLI
- **WHEN** the human opens `LM Studio`, clicks `qwen3-8b` and ticks OpenCode and Kilo CLI
- **THEN** two models of `qwen3-8b` on `LM Studio` are saved, one of each agent CLI, and the
  row says `in OpenCode, Kilo CLI`

#### Scenario: More CLIs
- **WHEN** a server suits six installed agent CLIs
- **THEN** the list under the row shows six ticks one under the other, and the row is no
  wider

### Requirement: The name before the tick

An unticked agent CLI under a server's model SHALL say `would be <name>`: the name a tick
would save, as the core gives it, never made by the page.

#### Scenario: The name before the tick
- **WHEN** `LM Studio дома` suits OpenCode and Kilo CLI and the human opens `qwen3-8b`
- **THEN** Kilo CLI says `would be qwen3-8b · LM Studio дома · Kilo CLI`

### Requirement: A model's default name

A model ticked or added SHALL be named: an alias of a CLI, the first word of the CLI's
title and the alias with its first letter capitalised, a `[1m]` of it as ` 1M` (`Claude
Sonnet`, `Claude Opus 1M`); a model of a CLI's own list, the model; a model on a server,
`<model> · <server>`, and `<model> · <server> · <CLI title>` when the server suits more
than one CLI. A name taken SHALL get ` · <CLI title>` added, and then ` (2)`, ` (3)` until
free.

#### Scenario: A taken name
- **WHEN** `gpt-5-codex` is saved as a name of another model and the human ticks
  `gpt-5-codex` under Codex CLI
- **THEN** the new model is named `gpt-5-codex · Codex CLI`

#### Scenario: A server several CLIs suit
- **WHEN** `LM Studio дома` suits OpenCode and Kilo CLI and the human ticks OpenCode for
  `qwen3-8b`
- **THEN** the model is named `qwen3-8b · LM Studio дома · OpenCode`

#### Scenario: An alias with [1m]
- **WHEN** the human ticks `opus[1m]` under Claude Code
- **THEN** the model is named `Claude Opus 1M`

### Requirement: A tick of several models

When several configured models have the same CLI, model and server, their tick SHALL be on
and disabled, its title naming them; they SHALL be removed in Your models.

#### Scenario: Two names for one model
- **WHEN** `Claude Opus` and `Сильная` are both Claude Code's `opus`
- **THEN** the tick of `opus` under Claude Code is on and disabled, and its title names
  both

### Requirement: Search in a long list

An open source with more than ten models SHALL have a search field above its list,
`Search <n> models`, that shows only the models whose name holds the typed text, ignoring
case; the line under the list SHALL say `<shown> of <n> models`.

#### Scenario: Kilo CLI searched
- **WHEN** the human types `qwen3-8` in the search of Kilo CLI
- **THEN** only the models whose name holds `qwen3-8` show

### Requirement: Embeddings models are hidden and counted

A model the server types embeddings SHALL NOT be listed; under the list a line SHALL say
`<n> embeddings model(s) hidden: agents cannot run on it (them).`

#### Scenario: LM Studio's embeddings model
- **WHEN** the human opens `LM Studio`, which types `text-embedding-nomic-embed-text-v1.5`
  embeddings
- **THEN** it is not listed and the line says `1 embeddings model hidden: agents cannot run
  on it.`

### Requirement: A model its source no longer lists

When a source's list was read and lacks the model of a configured model of that source,
the model SHALL show first in the list, ticked, marked `no longer listed`, and in Your
models with `⚠ not in list`, its title saying agents on it stop at their first turn.
Nothing SHALL remove it but the human; unticking it SHALL remove it from the list too.

#### Scenario: A model gone from the server
- **WHEN** `mistral-7b · LiteLLM` is saved and `LiteLLM` no longer lists `mistral-7b`, and
  the human opens `LiteLLM`
- **THEN** `mistral-7b` shows first, ticked, marked `no longer listed`, and the model stays
  saved

### Requirement: A server that does not answer

When an open server does not answer, asks for a key or refuses it, the source SHALL show
the probe's line and its hint (the container's `host.docker.internal` one included) as a
warning, and `Its model(s) stay(s) saved: <names>. Agents on it stop at their first turn
until the server answers.`; the models SHALL stay.

#### Scenario: LM Studio switched off
- **WHEN** `Локальная Gemma` is on `LM Studio дома`, which is off, and the human opens it
- **THEN** it shows `⚠ http://localhost:1234 does not answer (connection refused)`, says
  `Локальная Gemma` stays saved, and it stays

### Requirement: A model id only where the list is not whole

A field **Model id** with Add SHALL end an open source only when its list is not whole:
Claude Code (aliases only), a CLI whose list cannot be read, and a server that gives no
list (with a choice of the CLI). Its note SHALL be the check `lado model add` would make, once
the typing settles; Add SHALL save the model with its default name, off while refused.

#### Scenario: Claude Code's full model id
- **WHEN** the human types `claude-opus-4-1-20250805` in Model id of Claude Code
- **THEN** the note is a warning that LADO cannot check it, and Add saves it

#### Scenario: Codex CLI with its list
- **WHEN** the human opens Codex CLI logged in to OpenAI
- **THEN** its source has no Model id field

### Requirement: Your models by CLI

Your models SHALL show a card per agent CLI that has configured models, in LADO's order of
agent CLIs, headed by its title and its number of models on a ground of its own, apart from
the next. A card SHALL list its models by name ignoring case: Name (wrapped, never cut),
Model, From (its server, the address on hover, else `the agent CLI`) and ×, which removes
the model at once as `lado model remove` does.

#### Scenario: Removing a model
- **WHEN** the human presses × on `Claude Sonnet`
- **THEN** its row says `Removed Claude Sonnet. Undo` and the tick of `sonnet` under Claude
  Code is off

#### Scenario: A renamed model
- **WHEN** the human renames `qwen3-8b · LM Studio · OpenCode` to `Alpha`
- **THEN** `Alpha` shows first in OpenCode's card, and no other card moves

### Requirement: Agent CLIs without models, and one not installed

Under the cards one line SHALL name the agent CLIs without models: `<CLI title> has no
models: its agents run on its default model.`, or `<titles> have no models: their agents
run on their default model.` A card of an agent CLI not installed SHALL say in its head `⚠
not installed: its models cannot run`.

#### Scenario: Kilo CLI without models
- **WHEN** models of Claude Code and OpenCode are saved, none of Kilo CLI's
- **THEN** there is no card of Kilo CLI, and the line says `Kilo CLI has no models: its
  agents run on its default model.`

### Requirement: Undo of a model removed

A model removed by × SHALL leave in its row `Removed <name>. Undo`, the row's height kept,
the focus on Undo; Undo SHALL save the model again with its name, agent CLI, model and
server, as `lado model add <name>` would, a refusal shown in the row, the focus then on the
model's name. After ten seconds only Undo SHALL go: `Removed <name>.` SHALL stay until the
human's next change in the section or the page's next opening.

#### Scenario: Undo
- **WHEN** the human presses × on `Сонет для ревью` and then Undo
- **THEN** `Сонет для ревью` is saved again and the tick of `sonnet` under Claude Code is
  on

#### Scenario: Ten seconds
- **WHEN** ten seconds pass after ×
- **THEN** the row says `Removed Сонет для ревью.` without Undo, at the same height, until
  the human's next change

### Requirement: A renamed model unticked keeps its name

While the page stays open, a model removed by its tick under a name other than its default
SHALL be saved again under that name when the same agent CLI, model and server are ticked
again, or under its default name when that name is taken by then; meanwhile its row SHALL
say `would be <name>`. A ticked model with a name of its own SHALL have the title
`Unticking removes <name>.`

#### Scenario: A mis-click
- **WHEN** the human renamed `qwen3-8b · LM Studio дома · OpenCode` to `Локальная Qwen`,
  unticks OpenCode under `qwen3-8b` and ticks it again
- **THEN** `Локальная Qwen` is saved again, and between the two clicks the row said `would
  be Локальная Qwen`

#### Scenario: The page reloaded
- **WHEN** the human unticks it, reloads the page and ticks it again
- **THEN** the model is saved under its default name

### Requirement: Renaming a model in place

A click on a model's name, or Enter on it, SHALL turn it into a field no wider than its
cell, the name selected; Enter or leaving the field SHALL rename the model under the rules
of a model's name, Esc SHALL restore it; there SHALL be no Save or Cancel button. A refused
name SHALL keep the field with the refusal under it; leaving it then restores the name. On
hover the name SHALL show a frame and the title `Click to rename`.

#### Scenario: Claude Sonnet becomes Сильная
- **WHEN** the human clicks `Claude Sonnet`, types `Сильная` and presses Enter
- **THEN** Your models shows `Сильная` with Claude Code and sonnet, and `lado model list`
  shows it too

#### Scenario: A name taken
- **WHEN** the human renames a model to the name of another, in another case, and presses
  Enter
- **THEN** under the field it shows the name-taken line, and nothing changes

#### Scenario: Esc
- **WHEN** the human types a new name and presses Esc
- **THEN** the old name shows and nothing is saved

### Requirement: The page adds a server as lado model-server add does

`Add server` SHALL open, in its place at the end of Model servers, a form with Name, Address
and Key; its button Add server SHALL probe and save the server as `lado model-server add
<name> <address> [--key]` does, each request no longer than the command's. On success the
server SHALL show in place of the form, open, with `Saved model server "<name>".` and `Open
a model to tick the agent CLIs that run it.` above its list, the focus on its row.

#### Scenario: LiteLLM
- **WHEN** the human adds `LiteLLM` at `10.0.0.5:4000` with its key, and it answers
- **THEN** `LiteLLM` shows open where the form was, with its models and `Saved model server
  "LiteLLM".`, and `lado model-server list` shows it

#### Scenario: The next change
- **WHEN** the human, after adding `LiteLLM`, ticks one of its models
- **THEN** `Saved model server "LiteLLM".` and `Open a model to tick…` go, as a model's
  `Removed <name>.` line goes with the next change

### Requirement: The form checks the server as the human types

Once the typing settles, the form SHALL check without a key: the name under Name, the
address by the probe under Address (`checking …` meanwhile). A key SHALL go only with
**Check key** or Add server. Add server SHALL be on only for a free name and a server that
answered, or that asks for a key with one typed.

#### Scenario: LM Studio found, nothing sent
- **WHEN** the human types `LM Studio дома` and `http://localhost:1234`, where LM Studio
  answers with 12 models and one embeddings model
- **THEN** under Address it shows `✓ LM Studio answers at http://localhost:1234`, `12`
  models, the embeddings line and the agent CLIs that can use it, before any Add

#### Scenario: A gateway that asks for a key
- **WHEN** the human types `https://gw.corp/llm`, which answers 401
- **THEN** Address says the server asks for a key, Key says `required by this server`,
  Check key shows once a key is typed, and no key has been sent

#### Scenario: A typo in the port
- **WHEN** the human types `http://localhost:1243` and nothing answers there
- **THEN** Address shows `http://localhost:1243 does not answer (connection refused)`
  before any Add, and Add server stays off

### Requirement: The form says what answers and what the key needs

A server that answered the form's check SHALL show under Address a panel `✓ <type> answers
at <address>` with its number of models, the hidden embeddings' line, and the agent CLIs
that can use it. Key SHALL be labelled `optional`, or `required by this server` once the
check says the server asks for one, with `Kept in a file only LADO reads; never shown
again.` under it.

#### Scenario: The panel
- **WHEN** LM Studio answers the check with 12 models and one embeddings model
- **THEN** the panel says `✓ LM Studio answers at http://localhost:1234`, `12`, `1
  embeddings model hidden: agents cannot run on it.` and the agent CLIs that can use it

#### Scenario: A key asked for
- **WHEN** the check finds that the server asks for a key
- **THEN** Key is labelled `required by this server`

### Requirement: The same address and plain http are said, not refused

The line `same address as model server "<name>"` SHALL show under Address for each saved
server at the typed address, and after the server is saved, in its source until the next
server is added, changed or removed; the plain-http warning SHALL show under Key once an
address and a key that would go there are typed, nothing sent. Neither SHALL stop Add.

#### Scenario: A key over plain http, said before Add
- **WHEN** the human types the address `gw.example.com:4000` and a key, and has not pressed
  Add
- **THEN** under Key it shows the plain-http warning, and no key has been sent

#### Scenario: The same address under a second name
- **WHEN** `gateway` is saved at `http://10.0.0.5:4000` and the human types `LiteLLM` at
  `10.0.0.5:4000/v1/`
- **THEN** Address shows `same address as model server "gateway"`, and Add saves it

### Requirement: A refusal is the command's rule in the page's words under its field

Every refusal and warning SHALL be the one the matching command makes, its hint under it,
under the field it concerns: Name, Address or Key of a server; Model id; a rename's field;
a refusal of no field under the buttons or in the tick's row. Its line and hint SHALL name
no command to run, but what to do on the page; the commands SHALL print their lines as
before. The form SHALL keep its values but the key's.

#### Scenario: A key refused
- **WHEN** the human adds `work` at `https://gw.corp/llm` with a key it answers 401 to
- **THEN** under Key it shows the refusal, and `lado model-server add work
  https://gw.corp/llm --key` prints its own line as before

#### Scenario: A name taken
- **WHEN** the human renames a model to `claude sonnet` and `Claude Sonnet` is saved
- **THEN** under the field it shows `the name is taken by the model "Claude Sonnet"`

#### Scenario: A model gone from the server's list
- **WHEN** the human ticks a model its server no longer lists
- **THEN** the row shows `<model> is not in <server>'s list of models`, and the tick is
  off

### Requirement: The fields and notes look as the launch window's

Every field, choice and button of the section SHALL have the size and font of the launch
window's; a warning, a refusal and an ok SHALL look as the launch window's notes do, and no
note SHALL cover a field or another note.

#### Scenario: The CLI of a model id on a server
- **WHEN** the human opens the CLI choice by Model id of a server without a list
- **THEN** its options show in the font and size of the launch window's choices

#### Scenario: Two notes under one field
- **WHEN** an address does not answer in LADO's container
- **THEN** the refusal and the container's hint show one under the other under Address,
  the field still visible

### Requirement: Change replaces a server's address or key

**Change** of a server SHALL open, under its row, its Address, filled, and New key, empty,
with `Its <n> models keep their names and move with it.` when it has models; the address
SHALL be checked as the human types as the add form's is, the server's own name not taken.
Save SHALL replace the server as `lado model-server add <name> <address> [--key] --replace`
does, with the kept key, kept, when New key is empty. Its models SHALL keep referring to
it; a failed probe SHALL change nothing.

#### Scenario: A new key for a gateway
- **WHEN** `work` is saved with a key and the human saves a new key in New key, which the
  server takes
- **THEN** the server's key file holds the new key, and its models still name `work`

#### Scenario: Another port, the key kept
- **WHEN** `LM Studio дома` moved to port 1235 and the human types it in Change's Address
- **THEN** the note under Address says what answers there before Save, its check sent with
  the kept key while New key is empty, and after Save with New key empty it shows
  `http://localhost:1235` and its key, if any, stays

#### Scenario: An address that does not answer
- **WHEN** the human types in Change's Address a port where nothing answers
- **THEN** the refusal shows under Address and Save is off; a Save refused otherwise shows
  its refusal in the check line's place, never both

### Requirement: Removing a server removes its models after a confirmation

**Remove** of a server SHALL ask under its row, the focus on Cancel: `Remove <name>?`, or
with models `Remove <name> and its <n> models: <name>, <name>?`; only its confirmation SHALL remove them as `lado
model-server remove <name> --with-models` does, and only the models it named: when the
server has others by then, nothing SHALL be removed and it SHALL ask again, naming them.
The row SHALL then say `Removed <name> and its <n> models.`

#### Scenario: A model added after it asked
- **WHEN** the confirmation names `a`, and `lado model add` puts `late` on the server before
  the human confirms
- **THEN** the server, `a` and `late` stay, and it asks `Remove <name> and its 2 models: a,
  late?`

#### Scenario: A server with three models
- **WHEN** three models refer to `LiteLLM` and the human removes it and confirms
- **THEN** the models, the server and its key folder are gone, and the row says `Removed
  LiteLLM and its 3 models.`

#### Scenario: Cancel
- **WHEN** the human presses Cancel at the confirmation
- **THEN** the server and its models stay

### Requirement: Remove's question says what goes

Remove's question SHALL say `Its key is deleted too.` only when the server has a key, then
`This cannot be undone.`; its button SHALL say `Remove server`, or `Remove server and <n>
models` when it has models.

#### Scenario: A server with a key and three models
- **WHEN** the human removes `LiteLLM`, which has a key and three models
- **THEN** the question says `Its key is deleted too. This cannot be undone.` and the button
  `Remove server and 3 models`

#### Scenario: A server without a key
- **WHEN** the human removes `Ollama`, saved without a key
- **THEN** the question says nothing of a key

### Requirement: A server's key enters the API and never leaves it

A server's key SHALL reach the page's API only in the body of a POST, never in an address.
No answer of the API (refusals and validation errors included), the server's log, the error
journal, the change feed, `lado.db` or any file of `LADO_HOME` but the server's key file
SHALL hold its value.

#### Scenario: The canary
- **WHEN** a unique key is sent through a real server's API to check a server, to add one,
  to change it, in a request the server refuses as unreadable and in one whose probe is
  refused
- **THEN** no answer, no line of the server's log or the error journal, and no file of
  `LADO_HOME` but `model-servers/<id>/key` holds the key

### Requirement: The page keeps the key only in its field

The Key and New key fields SHALL be the dots field of a project's secrets, not a password
field; the page SHALL keep the key only in its field, never in the page's state, an address
or the browser's storage, and SHALL empty the field after Add or Save, on Cancel and when
the form closes. Check key SHALL leave the key in its field, so that Add or Save can send it
next.

#### Scenario: Cancel
- **WHEN** the human types a key, presses Cancel and opens + Add server again
- **THEN** the Key field is empty

#### Scenario: Check key, then Add
- **WHEN** the human types a key and presses Check key
- **THEN** the Key field still holds the key, and Add sends it

#### Scenario: Dots, never letters
- **WHEN** the human types a key in Key or in New key
- **THEN** the field is drawn in the font of dots of a project's secret (`LadoSecretDots`),
  every character one dot

### Requirement: The section fits a phone

On a window narrower than 600 px the section's forms SHALL show their fields one under the
other; its icon buttons, × and Undo SHALL be at least 44 by 44 px and a list's row 44 px
high; a server's list of up to 20 models SHALL not scroll within itself; and no part of the
section SHALL make the page scroll sideways.

#### Scenario: A server's list on a phone
- **WHEN** the human opens a server with a long address and 12 models in a window 390 px
  wide
- **THEN** the page does not scroll sideways, the address wraps whole, ✎ and 🗑 show under
  its name, and all 12 models show without a scroll inside the list

#### Scenario: A model with marks on a phone
- **WHEN** a server's model `qwen/qwen-gone-7b-instruct-q4` is no longer listed and saved
  for OpenCode, in a window 390 px wide
- **THEN** its id takes the row's width and `no longer listed` and `in OpenCode` show under
  it

#### Scenario: Names and ids whole on a phone
- **WHEN** a server `LiteLLM на работе` has the badges `OpenAI-compatible` and `key`, and
  Your models holds `claude-opus-4-1-20250805` on its agent CLI, in a window 390 px wide
- **THEN** the server's name, the model's id and `the agent CLI` show whole, wrapped,
  never cut with `…`

### Requirement: The UI calls Claude Code, Codex CLI, OpenCode and Kilo CLI agent CLIs

The UI SHALL name what runs an agent "agent CLI": the New session window's field `Agent
CLI`, Settings' section `Agent CLIs and environment`, the system panel's `Agent CLIs`, and
every line pointing to that section `Settings → Agent CLIs and environment`; the section
Models SHALL say `agent CLI`, or `CLI` where room is short. The section's anchor and the
commands' options (`--provider`, `--cli`) SHALL stay as they are.

#### Scenario: A worker refused for a CLI not logged in
- **WHEN** a session starts with Claude Code not logged in
- **THEN** the refusal says `log in in Settings → Agent CLIs and environment`, and that
  heading shows in Settings

#### Scenario: An old link
- **WHEN** the human opens `/settings#providers-and-environment`
- **THEN** the page scrolls to Agent CLIs and environment

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server or model by themselves, and SHALL NOT
change how `lado start`, the launch window, a resume or any agent behaves.

#### Scenario: Models saved through the page
- **WHEN** the human saved servers and models through the page and starts a session
  without `--model`
- **THEN** the session's agents start on their CLI's default, as without them
