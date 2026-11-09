# model-settings-page Specification

## Purpose
Settings → Model servers: the page where the human sees what each agent CLI and saved model
server offers and ticks the models to keep under names in one Your models table, renames
them, and adds, changes and removes servers, with the rules of `lado model-server` and `lado
model`; and the API it uses, which a server's key enters and never leaves.

## Requirements

### Requirement: Nothing moves under the pointer

No change in the section SHALL scroll the page or move the element the human acts on or
holds the focus on, whatever it changes above it: a tick, a rename, × and Undo, a default
picked, a server added, changed or removed, the reload after any of them, and a list's read
ending. The page SHALL keep that element at its place on the screen by scrolling by the height
changed above it, No row
SHALL leave the section on a timer.

#### Scenario: A tick adds a card above
- **WHEN** the human ticks an agent CLI under a model in the middle of a server's open list and the model adds a row to Your models below
- **THEN** the tick stays where it was on the screen, to the pixel

#### Scenario: A server added
- **WHEN** the human adds a server, and the page has room to scroll under the form
- **THEN** the new server takes the place of the form, and the form's place on the screen
  does not move

#### Scenario: The very end of the page
- **WHEN** the page is scrolled to its end and a form closes there, so the page gets shorter
  below what the human acted on
- **THEN** the page, with nothing left to scroll, moves by what it lost; a change above that
  element still moves nothing

#### Scenario: Nothing acted on
- **WHEN** the human opens `/settings` and presses nothing on Model servers while Servers and Your models render their rows
- **THEN** the page stays where it is: only what the human acts on is held in place

#### Scenario: A section above grows
- **WHEN** the human opened a source and a server above it grows while its list is read
- **THEN** the list's read ending scrolls nothing to make up for the server above

#### Scenario: The focus out of view
- **WHEN** the focus is on a server's row, the human scrolled up so that the first server shows and that server is below the view, and the servers between them grow
- **THEN** the page scrolls nothing: what shows stays where it is

#### Scenario: Undo runs out while the human is below
- **WHEN** the human pressed × on a model, then works in Servers, and ten seconds pass
- **THEN** nothing under the pointer moves: only the Undo of that row goes

### Requirement: Opening the section reads no list

Opening the page Model servers or Agent CLIs SHALL send no request to any model server, and Agent CLIs SHALL read the list of models only of an agent CLI whose default is built-in, in the background, the page not waiting for it, as the launch window's Model field reads it; every source SHALL show closed.

#### Scenario: Two servers saved
- **WHEN** `LM Studio дома` and `LiteLLM` are saved and the human opens Settings → Model servers
- **THEN** no request reaches either server, and every source is closed

#### Scenario: A built-in default
- **WHEN** Kilo CLI's default is built-in, OpenCode's is `Локальная Qwen` and Claude Code has none, and the human opens Settings → Agent CLIs
- **THEN** only Kilo CLI's list is read, and no request reaches `LM Studio дома`

### Requirement: The sources

Model servers SHALL list every saved server by name ignoring case, then `Add server`.

#### Scenario: First open
- **WHEN** Claude Code, Codex CLI and OpenCode are installed and logged in, Kilo CLI is not
  installed, and no server is saved
- **THEN** Model servers shows only `Add server`

### Requirement: A source opens from its whole row

A click anywhere on a source's row but its buttons SHALL open or close it, and so SHALL
Enter and Space on the row; the row SHALL show it can be clicked on hover, and its arrow
SHALL turn when open.

#### Scenario: A click on the name
- **WHEN** the human clicks the name `LM Studio дома`
- **THEN** it opens and its arrow points down

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
list) SHALL read them again, by a probe with its kept key; while it reads, the source SHALL say `reading
the models…`. LADO SHALL keep no source's list between reads.

#### Scenario: A new model on the server
- **WHEN** LM Studio got the model `gemma-3-12b` since the source was opened, and the human
  presses Refresh
- **THEN** `gemma-3-12b` shows in the list without a tick

### Requirement: A server's model opens its CLIs

A click on a model of an open server, or Enter on it, SHALL open under its row a list of
every agent CLI LADO knows, in LADO's order, one under the other; Esc SHALL close it. An
installed agent CLI that can use the server SHALL have its tick and under its title `as
<name>` when ticked. The row SHALL say `in <CLI title>, …` for the agent CLIs it is configured
in. A server no installed agent CLI can use SHALL say `No installed CLI can use this server.`.

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

### Requirement: A tick of several models

When several configured models have the same CLI, model and server, their tick SHALL be on
and disabled, its title naming them; they SHALL be removed in Your models.

#### Scenario: Two names for one model
- **WHEN** `Быстрая` and `Сильная` are both OpenCode's `qwen3-8b` on `LM Studio дома`
- **THEN** the tick of OpenCode under `qwen3-8b` is on and disabled, and its title names
  both

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
the model SHALL show first in the list, ticked, marked `no longer listed`, and in Your models with `⚠ not in list`, its title saying agents on it stop at their first turn.
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

### Requirement: Undo of a model removed

A model removed by × SHALL leave in its row `Removed <name>. Undo`, the row's height kept,
the focus on Undo; Undo SHALL save the model again with its name, agent CLI, model and
server, as `lado model add <name>` would, a refusal shown in the row, the focus then on the
model's name. After ten seconds only Undo SHALL go: `Removed <name>.` SHALL stay until the
human's next change in the section or the page's next opening.

#### Scenario: Undo
- **WHEN** the human presses × on `Сонет для ревью`, OpenCode's model on `lms`, and then Undo
- **THEN** `Сонет для ревью` is saved again and OpenCode's tick under its model on `lms` is
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
before. A name taken SHALL read from a capital letter. The form SHALL keep its values but the
key's.

#### Scenario: A key refused
- **WHEN** the human adds `work` at `https://gw.corp/llm` with a key it answers 401 to
- **THEN** under Key it shows the refusal, and `lado model-server add work
  https://gw.corp/llm --key` prints its own line as before

#### Scenario: A name taken
- **WHEN** the human renames a model to `claude sonnet` and `Claude Sonnet` is saved
- **THEN** under the field it shows `The name is taken by the model "Claude Sonnet"`

#### Scenario: A server's name taken
- **WHEN** the human adds a server named `LMS` and `lms` is saved
- **THEN** under Name it shows `A model server "lms" is saved already; its Change sets another
  address or key`

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
with models `Remove <name> and its <n> models: <name>, <name>?`. Only its confirmation SHALL
remove them as `lado model-server remove <name> --with-models` does, and only the models it
named: when the server has others by then, nothing SHALL be removed and it SHALL ask again,
naming them. The row SHALL then say `Removed <name> and its <n> models.`

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
or the browser's storage, and SHALL empty the field once Add or Save is done or refused for
anything but the key, on Cancel and when the form closes. Check key, and a refusal of the
key, SHALL leave the key in its field.

#### Scenario: Cancel
- **WHEN** the human types a key, presses Cancel and opens + Add server again
- **THEN** the Key field is empty

#### Scenario: Check key, then Add
- **WHEN** the human types a key and presses Check key
- **THEN** the Key field still holds the key, and Add sends it

#### Scenario: A refused key
- **WHEN** Add or Save is refused for the key (the server answers 401 to it)
- **THEN** the key stays in its field with the refusal under it, and Add or Save stays off
  until the key is edited or erased; erased in Change, Save sends the kept key

#### Scenario: Dots, never letters
- **WHEN** the human types a key in Key or in New key
- **THEN** the field is drawn in the font of dots of a project's secret (`LadoSecretDots`),
  every character one dot

### Requirement: The section fits a phone

On a window narrower than 600 px the forms of Model servers SHALL show their fields one under the
other; their icon buttons, ×, Undo, Agent CLIs' pickers and the picker's search SHALL be at
least 44 px high and a list's row 44 px high; `Default model` SHALL show over the field; the
field SHALL hide the id, not the name or the server's mark; a server's ✎ and 🗑 SHALL stay on its name's line; a list of up to
20 models SHALL not scroll within itself; and neither page SHALL scroll sideways.

#### Scenario: A server's list on a phone
- **WHEN** the human opens a server with a long address and 12 models in a window 390 px
  wide
- **THEN** the page does not scroll sideways, the address wraps whole, ✎ and 🗑 show at
  the right of its name's line, and all 12 models show without a scroll inside the list

#### Scenario: A model with marks on a phone
- **WHEN** a server's model `qwen/qwen-gone-7b-instruct-q4` is no longer listed and saved
  for OpenCode, in a window 390 px wide
- **THEN** its id takes the row's width and `no longer listed` and `in OpenCode` show under
  it

#### Scenario: Names and ids whole on a phone
- **WHEN** a server `LiteLLM на работе` has the badges `OpenAI-compatible` and `key`, and Claude Code's row holds `claude-opus-4-1-20250805` on it, in a window 390 px wide
- **THEN** the server's name and the model's id show whole, wrapped, never cut with `…`

### Requirement: The UI calls Claude Code, Codex CLI, OpenCode and Kilo CLI agent CLIs

The UI SHALL name what runs an agent "agent CLI": Settings' section `Agent CLIs and environment`,
the system panel's `Agent CLIs`, and every line pointing to that section `Settings → Agent CLIs and
environment`; the New session window's field SHALL read `Agent`, its notes `agent CLI` or the CLI's
title. The section Models SHALL say `agent CLI`, or `CLI` where room is short. The section's anchor
and the commands' options (`--provider`, `--cli`) SHALL stay as they are.

#### Scenario: A worker refused for a CLI not logged in
- **WHEN** a session starts with Claude Code not logged in
- **THEN** the refusal says `log in in Settings → Agent CLIs and environment`, and that
  heading shows in Settings

#### Scenario: An old link
- **WHEN** the human opens `/settings#providers-and-environment`
- **THEN** the page scrolls to Agent CLIs and environment

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server, model or default by themselves. What is saved
SHALL reach sessions only as `session-model` says.

#### Scenario: Models saved through the page
- **WHEN** the human saved servers and models through the page, set no default and starts a session
  without `--model`
- **THEN** the session's agents start as their CLI chooses, with the ticked models beside its own

#### Scenario: A default set through the page
- **WHEN** the human set a CLI's default model and starts a session on that CLI
- **THEN** the session's agents start on it, with the source `default in Settings`

### Requirement: A server's source row

Each server SHALL be one row: an open/close arrow in a framed box, its name, its type as a
badge and `key` when it has one, and a second line: how many models it gave (`2 models added`,
`no models added`) then its address.

#### Scenario: LM Studio with two models
- **WHEN** `LM Studio дома` at `http://localhost:1234`, without a key, gave two models
- **THEN** its row says `LM Studio дома`, the badge `LM Studio`, and `2 models added ·
  http://localhost:1234`

### Requirement: A server's list keeps its height

An open server's list SHALL show at most about nine models and scroll within itself; the
models of the server's configured models SHALL come first, in the order read at opening or
Refresh, which no tick SHALL change; under the list a line SHALL say how many models it has.

#### Scenario: A gateway's 323 models
- **WHEN** the human opens a gateway that lists 323 models, one of them configured
- **THEN** the configured one is first, the list scrolls within itself, the page grows by the
  list's height only, and the line says `323 models`

### Requirement: A default name of a server's model

A model ticked or added SHALL be named by its model as the server gives it, whole, cut to 64
characters. A name taken ignoring case SHALL get ` · <CLI title>` when the model holding it is of
another CLI and ` · <server>` when it is of the same CLI, then ` · <server> · <CLI title>`, and then
` (2)`, ` (3)` until free. No saved model SHALL be renamed by it.

#### Scenario: A server several CLIs suit
- **WHEN** `LM Studio дома` suits OpenCode and Kilo CLI, no model is saved, and the human ticks
  OpenCode for `qwen3-8b`
- **THEN** the model is named `qwen3-8b`

#### Scenario: A taken name
- **WHEN** `qwen3-8b` is saved as a name of an OpenCode model and the human ticks Kilo CLI under
  `qwen3-8b` on `lms`
- **THEN** the new model is named `qwen3-8b · Kilo CLI`, and the OpenCode one keeps `qwen3-8b`

#### Scenario: The same model on another server
- **WHEN** `qwen3-8b` is saved as a name of Kilo CLI's model on `lms` and the human ticks Kilo CLI
  under `qwen3-8b` on `Ollama`
- **THEN** the new model is named `qwen3-8b · Ollama`

#### Scenario: Both suffixes taken
- **WHEN** Kilo CLI's `qwen3-8b` on `lms` is saved, and the names `qwen3-8b · Ollama` and
  `qwen3-8b · Ollama · Kilo CLI` are taken, and the human ticks Kilo CLI under `qwen3-8b` on
  `Ollama`
- **THEN** the new model is named `qwen3-8b · Ollama · Kilo CLI (2)`

#### Scenario: An id with its vendor
- **WHEN** the human ticks OpenCode under `qwen/qwen3-coder` on a gateway
- **THEN** the model is named `qwen/qwen3-coder`

### Requirement: Search in a server's long list

An open server with more than ten models SHALL have a search field above its list, `Search
<n> models`, that shows only the models whose name holds the typed text, ignoring case; the
line under the list SHALL say `<shown> of <n> models`.

#### Scenario: A gateway searched
- **WHEN** the human types `qwen3-8` in the search of a gateway
- **THEN** only the models whose name holds `qwen3-8` show

### Requirement: A model id for a server without a list

A field **Model id** with Add SHALL end an open server only when it gives no list, with a
choice of the CLI. Its note SHALL be the check `lado model add` would make, once the typing
settles; Add SHALL save the model with its default name, off while refused.

#### Scenario: A server without a list
- **WHEN** the human types `qwen3-8b` in Model id of a server that gives no list
- **THEN** the note is a warning that LADO cannot check it, and Add saves it

### Requirement: One picker of a model

The field Default model SHALL be a picker over the list the core computes for the CLI, read when
it opens, in this order, an empty group not shown: `<CLI>'s settings` with `no model set: the
agent CLI chooses`; YOUR MODELS, with their server and their id unless it is the name ignoring
case; BUILT-IN, the CLI's list or its aliases (`BUILT-IN · aliases`); `Other name…`, at the
bottom, only when the CLI gives no full list. Any later place that picks a model SHALL use it.

#### Scenario: OpenCode with a server
- **WHEN** the human opens the picker of OpenCode with two of its models saved
- **THEN** it shows OpenCode's settings, those two with `LM Studio дома`, then its built-in
  models, and no `Other name…`

#### Scenario: Codex CLI on OpenAI
- **WHEN** the human opens the picker of Codex CLI logged in to OpenAI
- **THEN** it shows the full list and no `Other name…`

#### Scenario: A model named by its id
- **WHEN** Kilo CLI's default is its model `qwen3.8-27b`, of the model `qwen3.8-27b` on
  `LM Studio`, and the human opens its picker in a window 768 px wide
- **THEN** the field shows `qwen3.8-27b` once, whole, and the badge `LM Studio`, and its row in
  the list shows no id under the name

### Requirement: Picking saves at once

Picking a row SHALL close the list, save the default as `lado model default` does, keep the
focus on the field and show the value. A refusal SHALL show under the field and leave the value
as it was. `<CLI>'s settings` SHALL clear the default.

#### Scenario: A model of the list
- **WHEN** the human picks `anthropic/claude-sonnet-4-5` in Kilo CLI's row
- **THEN** `lado model default` shows it as Kilo CLI's default

#### Scenario: Back to the settings
- **WHEN** the human picks `Kilo CLI's settings`
- **THEN** Kilo CLI has no default, and its field shows `Kilo CLI's settings`

### Requirement: The picker lies over the page

The list SHALL lie over the page and not push it: placed by the field, opening upward when fewer
than 240 px are below and more above, at most 420 px high (`min(420px, 60dvh)` on a window
narrower than 600 px), scrolling within itself, kept above a phone's keyboard. Only a scroll the
human starts outside the list SHALL close it.

#### Scenario: The last card
- **WHEN** the human opens the picker of the last CLI's row at the bottom of the window
- **THEN** the list opens upward, whole, and the page does not grow

### Requirement: Search in the picker

A picker with more than ten models, built-in and yours counted, SHALL have a search field,
`Search <n> models`, that finds by name, id and server ignoring case, hides `<CLI>'s settings`
while it holds text, and says `No model matches “<text>”.` when nothing does. A footer SHALL say
`<n> built-in · <m> of yours` (`<k> of <n>` while searching), with ↻ that reads the list again;
Claude Code's aliases SHALL have no ↻.

#### Scenario: Kilo CLI's 321 models
- **WHEN** the human types `qwen` in the picker of Kilo CLI
- **THEN** only the models holding `qwen` show, Kilo CLI's external ones first

### Requirement: Other name for a CLI without a full list

`Other name…` SHALL show a field with Use and Cancel under the picker, holding the search's text
if any, and stay in the list while searching; once the typing settles,
the note SHALL be the check `lado model default` would make; Use SHALL set the default, the
warning staying under the field. A name saved so SHALL show first in BUILT-IN, marked `other
name`.

#### Scenario: A full id of Claude Code
- **WHEN** the human types `claude-opus-4-1-20250805` and presses Use in Claude Code's row
- **THEN** it is Claude Code's default and the warning that LADO cannot check it stays under the
  field

### Requirement: A list that cannot be read

While a list is read the picker SHALL show the CLI's configured models and `reading the
models…`. When it cannot be read the picker SHALL say why above the configured models, with
`Read again` when reading may help, and offer `Other name…`. With a built-in default the CLI's row SHALL show the same warning under the field with `Check again`.

#### Scenario: kilo models times out
- **WHEN** `kilo models` does not end in time and the human opens Kilo CLI's picker
- **THEN** it says the command timed out, shows Kilo CLI's external models and `Other name…`

#### Scenario: Codex CLI on another provider
- **WHEN** Codex CLI's model provider is not OpenAI
- **THEN** the picker says Codex CLI gives no list for that provider, with no `Read again`, and
  offers `Other name…`

### Requirement: A built-in default the list lost

When a CLI's list was read and lacks its built-in default, the field SHALL show it with `⚠ no
longer listed`, the picker SHALL show it first in BUILT-IN with `no longer listed`, and under the
field a warning SHALL say `<CLI> no longer lists <model>: agents on it stop at their first
turn.` with `Use <CLI>'s settings`. Nothing but the human SHALL change the default.

#### Scenario: A model gone from Kilo CLI
- **WHEN** Kilo CLI's default is `old/model`, and the list read when the page opened lacks it
- **THEN** the row shows it with the warning, and it stays Kilo CLI's default

### Requirement: An external default's server

Opening a picker SHALL probe, in the background, each server of that CLI's models, once; their
rows SHALL say `not answering`, or `not on the server` for a model the server lists no more. For
an external default so affected, the field's mark SHALL show as down when the server is silent,
and a warning under the field SHALL give the reason with `Check again` and `Use <CLI>'s settings`,
until the page closes or Check again finds it well. Nothing but the human SHALL change the
default.

#### Scenario: LM Studio switched off
- **WHEN** OpenCode's default is on `LM Studio дома`, which is off, and the human opens the picker
- **THEN** the warning names the server, and the default stays

### Requirement: An external model on Claude Code or Codex CLI

The picker of Claude Code or Codex CLI with external models SHALL say above them `On <CLI> a
server's model takes the whole process: the agent runs only on that server.`, and with an external default the CLI's row SHALL say `On <CLI> this model takes the whole process: an agent on it runs only on
<server>.` under the field. Which CLIs say so SHALL come from the provider, not from the page.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `work`
- **THEN** the row says `On Claude Code this model takes the whole process: an agent on it runs
  only on work.`

### Requirement: Undo of a default removed

A model that was its CLI's default SHALL say `Removed <name>. <CLI> is back on its settings.`,
and Undo SHALL set the default again.

#### Scenario: Undo of a default
- **WHEN** the human removes `Локальная Qwen`, OpenCode's default, and presses Undo
- **THEN** the model is saved again and OpenCode's field shows it

### Requirement: Removing a server clears the defaults on it

When a model a server's question names is an agent CLI's default, the question SHALL go on with
`<A> is <CLI>'s default model: <CLI> goes back to its settings.`, one such sentence for all of
them, and its confirmation SHALL clear those defaults.

#### Scenario: A default on the server
- **WHEN** `Локальная Qwen` on `LM Studio дома` is OpenCode's default and the human removes the
  server
- **THEN** the question names it, and once confirmed OpenCode's row on Agent CLIs shows `OpenCode's settings`

### Requirement: Removing a default model asks first

× on a model that is its CLI's default, and unticking it, SHALL ask in place, the focus on
Cancel, Esc as Cancel: `Remove <name>? It is <CLI>'s default model: <CLI> goes back to its
settings.`, with `Remove model` and Cancel; the tick SHALL stay on until the answer. The removal
SHALL clear the default in one operation. Any other model SHALL be removed as before, unasked.
A model removed by its tick SHALL leave no Undo; ticked again it SHALL NOT be a default again.

#### Scenario: × on a default
- **WHEN** the human presses × on `Локальная Qwen`, OpenCode's default, and confirms
- **THEN** the row says `Removed Локальная Qwen. OpenCode is back on its settings.` with Undo,
  and OpenCode's field shows `OpenCode's settings`

#### Scenario: Cancel
- **WHEN** the human presses Cancel or Esc at the question
- **THEN** the model and the default stay

#### Scenario: A default set in another window
- **WHEN** this page shows no default, another window made `Локальная Qwen` OpenCode's, and the
  human presses × on it
- **THEN** it goes unasked, but the row says `OpenCode is back on its settings.` and Undo sets the
  default again; removed by its tick, it leaves no Undo and OpenCode's row on Agent CLIs shows `OpenCode's settings`

### Requirement: The picker works from the keyboard

The field SHALL be a combobox named `Default model of <CLI>`, in the launch window `Model`: Enter,
Space, ↓ and ↑ open it on the selected row; ↑ ↓ Home End move; Enter or Space picks; Esc closes
without a pick; a click outside closes. With search the focus SHALL be in the search field, Esc
first clearing its text. Esc, a pick and a press on nothing SHALL return the focus to the field; a
press on another control SHALL go on from there.

#### Scenario: Esc in a search
- **WHEN** the human types in the picker's search and presses Esc twice
- **THEN** the first clears the text, the second closes the list, and the focus is on the field

### Requirement: The notes under the field

Notes under the field SHALL be tied to it by `aria-describedby`; a warning after a background
read SHALL be a status, a refusal an alert.

#### Scenario: A refused pick
- **WHEN** a pick is refused
- **THEN** the refusal under the field is an alert the field is described by

### Requirement: Tab goes through the picker's foot

Tab in an open list SHALL go on into the controls of its foot, and close it without a pick only
past the last, going on from the field; Shift+Tab SHALL go back through them, and from the search
close the list with the focus on the field.

#### Scenario: Tab through the foot
- **WHEN** the list is open and the human presses Tab
- **THEN** the focus is on the foot's first control, and past its last the list is closed and the
  focus goes on from the field

### Requirement: The search stands while a list is first read

Until a list's first read says how long it is, the picker SHALL show its search, reading `Search
models`, with the focus in it; what was typed SHALL stay, and a short list with nothing typed SHALL
hand the focus to the field. Another agent CLI's rows SHALL NOT stand in a list being read.

#### Scenario: Typing while the list is first read
- **WHEN** the human opens a list not read yet and types at once
- **THEN** what was typed stays in the search when the list comes

### Requirement: A request LADO's server did not answer promises nothing

A failed request of Settings → Agent CLIs or Model servers that got no answer from LADO's server SHALL read `LADO's server does not answer: your request may or may not have reached it.`, and SHALL NOT say that nothing was done.

#### Scenario: The server stops during a save
- **WHEN** a request of Settings → Agent CLIs or Model servers gets no answer from LADO's server
- **THEN** the page shows that line

### Requirement: The form names a CLI the server's type does not suit

What answered a server's check SHALL name, under its Agent CLIs, each CLI that has the server's API but cannot use a server of that type, with why, and the server's list SHALL offer no column for that CLI.

#### Scenario: LM Studio
- **WHEN** the human checks a server that is LM Studio and proves chat completions and the Responses API
- **THEN** Agent CLIs reads `Kilo CLI, OpenCode`, a warning under it reads `Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not talk to LADO`, and the list of models has no Codex CLI column

#### Scenario: Another server
- **WHEN** the human checks OpenRouter
- **THEN** Agent CLIs names Codex CLI, and no such warning shows

### Requirement: Settings has a page Model servers

The Settings page Model servers (`/settings/model-servers`) SHALL show, with no intro, two blocks
one under the other, each headed by its name and its count: **Servers**, with the lead `Any
OpenAI-compatible server: LM Studio, Ollama, vLLM, LiteLLM.`, the saved servers and `Add server`;
then **Your models**, shown once a model is saved. No card per agent CLI SHALL be on the page.

#### Scenario: Nothing saved
- **WHEN** no server and no model is saved and the human opens Model servers
- **THEN** the page shows Servers with its lead and `+ Add server`, and no Your models

#### Scenario: Four models
- **WHEN** four models and two servers are saved, three of OpenCode, one of Kilo CLI
- **THEN** the page reads `Servers 2` and `Your models 4`

### Requirement: Your models is one table of the human's models

Your models SHALL list every configured model in one table with the lead `Pick one as a default
in Agent CLIs.`, its last words a link to that page, and the columns Name, Model, From, Agent CLI
and ×, sorted by agent CLI in LADO's order, then by name ignoring case; From SHALL read `⚠
<server>` for a server found not answering. With servers and no model it SHALL say `None yet: open
a server and tick the agent CLIs that run a model.`

#### Scenario: Removing a model
- **WHEN** the human presses × on `Рабочая Qwen`, no agent CLI's default
- **THEN** its row says `Removed Рабочая Qwen. Undo`, and OpenCode's tick under its model is off

#### Scenario: A server that does not answer
- **WHEN** `qwen3-8b · lmstudio` is Kilo CLI's model and `lmstudio` does not answer
- **THEN** its From reads `⚠ lmstudio`, the server named in its title

#### Scenario: A model of an agent CLI LADO does not know
- **WHEN** a configured model's CLI is not one LADO knows
- **THEN** it is listed last, its Agent CLI the CLI's name as saved, and it can be renamed and
  removed

### Requirement: Your models marks a CLI's default

A model that is an agent CLI's default SHALL read `<CLI> · default` in its Agent CLI cell, so the
human sees that × clears that default too.

#### Scenario: Kilo CLI's default
- **WHEN** `qwen3-8b · lmstudio` is Kilo CLI's default
- **THEN** its row's Agent CLI reads `Kilo CLI · default`

### Requirement: Renaming a model in Your models

A click on a name, or Enter on it, SHALL turn it into a field no wider than its cell, the name
selected; Enter or leaving it SHALL rename the model under the rules of a model's name, Esc SHALL
restore it; there SHALL be no Save or Cancel button. A refused name SHALL keep the field with the
refusal under it; leaving it then restores the name. On hover the name SHALL show a frame and the
title `Click to rename`.

#### Scenario: A renamed model
- **WHEN** the human renames `qwen3-8b · LM Studio · OpenCode` to `Alpha`
- **THEN** `Alpha` shows in OpenCode's place of the table by name, `lado model list` shows it, and
  a default on it stays

#### Scenario: A name taken
- **WHEN** the human renames a model to the name of another, in another case, and presses Enter
- **THEN** under the field it shows the name-taken line, and nothing changes

#### Scenario: Esc
- **WHEN** the human types a new name and presses Esc
- **THEN** the old name shows and nothing is saved

### Requirement: Your models fits a narrow window

At 900 px and narrower Your models SHALL have no header row, and each model SHALL show its name
and × on one line, then `<model> · <server> · <agent CLI>` on the next, wrapped whole, the model
left out when it is the name ignoring case; × SHALL be 32 px, and 44 px on a phone.

#### Scenario: Tablet
- **WHEN** the human opens Model servers in a window 768 px wide with four models
- **THEN** each model takes two lines, no name or id is cut, and the page does not scroll sideways

#### Scenario: A model named by its id on a phone
- **WHEN** the human opens Model servers on a phone with Kilo CLI's default `qwen3.8-27b`, the
  model `qwen3.8-27b` on `LM Studio`
- **THEN** its second line reads `LM Studio · Kilo CLI · default`

### Requirement: A default saved says so

Each save of a CLI's default that succeeds from its row on Agent CLIs SHALL show `✓ Saved` in
the done colour beside the field (at the right of the `Default model` line in a row too narrow
for both), in a place the row keeps for it, so nothing moves or narrows; it SHALL stay until the human's next save on the
page, a login sheet opened, ↻ or leaving the page, never on a timer. A refused save SHALL show
no `✓ Saved`.

#### Scenario: A model of the list
- **WHEN** the human picks `Рабочая Qwen` in OpenCode's field and the save succeeds
- **THEN** `✓ Saved` shows beside the field, and neither the field nor the row below it moves

#### Scenario: Every way of saving
- **WHEN** the human picks `Kilo CLI's settings`, uses `Other name…`, presses `Use Kilo CLI's
  settings` under a warning, or picks the value the field already holds
- **THEN** each save that succeeds shows `✓ Saved` in Kilo CLI's row

#### Scenario: A refusal
- **WHEN** the server refuses a pick
- **THEN** the refusal shows under the field, and the row shows no `✓ Saved`

#### Scenario: The next change
- **WHEN** `✓ Saved` shows in OpenCode's row and the human then saves Kilo CLI's default
- **THEN** `✓ Saved` shows in Kilo CLI's row only

#### Scenario: No timer
- **WHEN** `✓ Saved` shows and the human does nothing for a minute
- **THEN** it still shows; opening a login sheet, ↻ or leaving the page removes it

#### Scenario: A screen reader
- **WHEN** a save succeeds
- **THEN** a screen reader hears `Saved` once from the row's status region

### Requirement: A CLI that cannot use the server says why

Under a server's model, an agent CLI that cannot use the server SHALL have its tick disabled,
on only when a model of it is saved (then with `as <name>`), and under its title `cannot use
this server: <why>`, the core's why: its provider refuses the server's type, the server has no
API of the CLI, or that API did not answer in time. One the server suits but not installed
here SHALL say `not installed`.

#### Scenario: Codex CLI on LM Studio
- **WHEN** LM Studio answers chat completions and the Responses API, all four agent CLIs are
  installed, and the human opens `qwen3-8b`
- **THEN** the list shows Claude Code, Codex CLI, Kilo CLI and OpenCode in that order, and
  Codex CLI's tick is off and disabled with `cannot use this server: its Responses API loses
  Codex CLI's MCP tools, so the agent could not talk to LADO`

#### Scenario: A model saved on a CLI that cannot use the server now
- **WHEN** `qwen3-8b` on `LM Studio` is saved for Kilo CLI as `Kilo qwen`, and Kilo CLI is no
  longer installed
- **THEN** Kilo CLI's tick is on and disabled, with `as Kilo qwen` and `not installed`

#### Scenario: A server without the Anthropic Messages API
- **WHEN** a server answers chat completions and the Responses API only
- **THEN** Claude Code's tick is off and disabled with `cannot use this server: it has no
  Anthropic Messages API`

#### Scenario: An API that did not answer in time
- **WHEN** the server's Anthropic Messages API did not answer either time
- **THEN** Claude Code's tick is off and disabled with `cannot use this server: its Anthropic
  Messages API did not answer in time`

#### Scenario: A CLI not installed
- **WHEN** the server suits Kilo CLI and Kilo CLI is not installed here
- **THEN** Kilo CLI's tick is off and disabled with `not installed`

#### Scenario: No installed CLI can use the server
- **WHEN** the server suits only Claude Code and Claude Code is not installed
- **THEN** the server says `No installed CLI can use this server.`, and a model still opens to
  the list of CLIs, none of them tickable, each with its reason
