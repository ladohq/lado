## MODIFIED Requirements

### Requirement: Settings has a section Models

The Settings page SHALL show a section **Models** after Agent CLIs and environment and
before Usage statistics, at the anchor `#models`, with no tabs: an intro line, `Choose a default model for each
agent CLI, and add the models of your own servers.`, then two blocks one under the other,
each headed by its name and its count where it has one: **Your agent CLIs**, a card per agent
CLI; **Model servers**, the saved servers and `Add server`.

#### Scenario: The anchor
- **WHEN** the human opens `/settings#models`
- **THEN** the page scrolls to the section Models once, its two blocks one under the
  other

#### Scenario: Four models
- **WHEN** four models and two servers are saved, three of OpenCode, one of Kilo CLI
- **THEN** OpenCode's card reads `Your models 3`, Kilo CLI's `Your models 1`, and the block
  reads `Model servers 2`

### Requirement: Nothing moves under the pointer

No change in the section SHALL scroll the page or move the element the human acts on or
holds the focus on, whatever it changes above it: a tick, a rename, × and Undo, a default
picked, a server added, changed or removed, the reload after any of them, and a list's read
ending. The page SHALL keep that element at its place on the screen by scrolling by the height
changed above it, and SHALL scroll to `#models` only when it opens with that anchor. No row
SHALL leave the section on a timer.

#### Scenario: A tick adds a card above
- **WHEN** the human ticks an agent CLI under a model in the middle of a server's open list
  and the model adds a row to that CLI's card above
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
- **WHEN** the human opens `/settings` and presses nothing in Models while the sections above
  grow and Models renders its rows
- **THEN** the page stays where it is: only what the human acts on in Models is held in place

#### Scenario: A section above grows
- **WHEN** the human opened a source in Models and a section above grows while its list is
  read
- **THEN** the list's read ending scrolls nothing to make up for the section above

#### Scenario: The focus out of view
- **WHEN** the focus is on a server's row, the human scrolled up so that the first card shows
  and the server is below the view, and the blocks between them grow
- **THEN** the page scrolls nothing: what shows stays where it is

#### Scenario: Undo runs out while the human is below
- **WHEN** the human pressed × on a model, then works in Model servers, and ten
  seconds pass
- **THEN** nothing under the pointer moves: only the Undo of that row goes

### Requirement: Opening the section reads no list

Opening the section Models SHALL send no request to any model server and SHALL read the list
of models only of an agent CLI whose default is built-in, in the background, the page not
waiting for it, as the launch window's Model field reads it; every source SHALL show closed.

#### Scenario: Two servers saved
- **WHEN** `LM Studio дома` and `LiteLLM` are saved and the human opens Settings → Models
- **THEN** no request reaches either server, and every source is closed

#### Scenario: A built-in default
- **WHEN** Kilo CLI's default is built-in, OpenCode's is `Локальная Qwen` and Claude Code has
  none, and the human opens Settings → Models
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

### Requirement: Opening a source reads its list now

Opening a source SHALL read its models now, and **Refresh** (↻, at the right above the
list) SHALL read them again, by a probe with its kept key; while it reads, the source SHALL say `reading
the models…`. LADO SHALL keep no source's list between reads.

#### Scenario: A new model on the server
- **WHEN** LM Studio got the model `gemma-3-12b` since the source was opened, and the human
  presses Refresh
- **THEN** `gemma-3-12b` shows in the list without a tick

### Requirement: A tick of several models

When several configured models have the same CLI, model and server, their tick SHALL be on
and disabled, its title naming them; they SHALL be removed on its card.

#### Scenario: Two names for one model
- **WHEN** `Быстрая` and `Сильная` are both OpenCode's `qwen3-8b` on `LM Studio дома`
- **THEN** the tick of OpenCode under `qwen3-8b` is on and disabled, and its title names
  both

### Requirement: A model its source no longer lists

When a source's list was read and lacks the model of a configured model of that source,
the model SHALL show first in the list, ticked, marked `no longer listed`, and on its CLI's card
with `⚠ not in list`, its title saying agents on it stop at their first turn.
Nothing SHALL remove it but the human; unticking it SHALL remove it from the list too.

#### Scenario: A model gone from the server
- **WHEN** `mistral-7b · LiteLLM` is saved and `LiteLLM` no longer lists `mistral-7b`, and
  the human opens `LiteLLM`
- **THEN** `mistral-7b` shows first, ticked, marked `no longer listed`, and the model stays
  saved

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

### Requirement: The section fits a phone

On a window narrower than 600 px the section's forms SHALL show their fields one under the
other; its icon buttons, ×, Undo, the Default model field and the picker's search SHALL be at
least 44 px high and a list's row 44 px high; a card's label SHALL show over its field; the
field SHALL hide the id and keep the name and the server's mark; a server's list of up to 20
models SHALL not scroll within itself; and no part of the section SHALL make the page scroll
sideways.

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
  a card holds `claude-opus-4-1-20250805` on it, in a window 390 px wide
- **THEN** the server's name and the model's id show whole, wrapped, never cut with `…`

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server, model or default by themselves, and SHALL NOT
change how `lado start`, the launch window, a resume or any agent behaves.

#### Scenario: Models saved through the page
- **WHEN** the human saved servers and models through the page and starts a session
  without `--model`
- **THEN** the session's agents start on their CLI's default, as without them

#### Scenario: A default set through the page
- **WHEN** the human set a CLI's default model and starts a session on that CLI
- **THEN** the session's agents start as without it, and the page says nothing of sessions
  using it

## REMOVED Requirements

### Requirement: Your models without a model

**Reason**: the block goes: its models are on the cards; a card without models shows none, and the lead says how to add them.
**Migration**: see the ADDED requirements of this delta.

### Requirement: A source's row

**Reason**: the row of an agent CLI goes with its source.
**Migration**: see the ADDED requirements of this delta.

### Requirement: A source's list keeps its height

**Reason**: only a server's list stays a source.
**Migration**: see the ADDED requirements of this delta.

### Requirement: A tick is a configured model

**Reason**: a CLI's own models are no entries.
**Migration**: see the ADDED requirements of this delta.

### Requirement: A model's default name

**Reason**: a CLI's own models get no name.
**Migration**: see the ADDED requirements of this delta.

### Requirement: Search in a long list

**Reason**: a server's list keeps it; the picker has its own.
**Migration**: see the ADDED requirements of this delta.

### Requirement: A model id only where the list is not whole

**Reason**: only a server's list can lack a model; a CLI's other name is the picker's.
**Migration**: see the ADDED requirements of this delta.

### Requirement: Your models by CLI

**Reason**: the models move to the card of their agent CLI.
**Migration**: see the ADDED requirements of this delta.

### Requirement: Agent CLIs without models, and one not installed

**Reason**: every agent CLI has a card.
**Migration**: see the ADDED requirements of this delta.

### Requirement: Renaming a model in place

**Reason**: the same rule on the card, under a scenario of an external model.
**Migration**: see the ADDED requirements of this delta.

## ADDED Requirements

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

A model ticked or added SHALL be named `<model> · <server>`, and `<model> · <server> · <CLI
title>` when the server suits more than one CLI. A name taken SHALL get ` · <CLI title>` added,
and then ` (2)`, ` (3)` until free.

#### Scenario: A server several CLIs suit
- **WHEN** `LM Studio дома` suits OpenCode and Kilo CLI and the human ticks OpenCode for
  `qwen3-8b`
- **THEN** the model is named `qwen3-8b · LM Studio дома · OpenCode`

#### Scenario: A taken name
- **WHEN** `qwen3-8b · lms` is saved as a name of another model and the human ticks Codex CLI
  under `qwen3-8b` on `lms`, which suits Codex CLI alone
- **THEN** the new model is named `qwen3-8b · lms · Codex CLI`

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

### Requirement: A card per agent CLI

Your agent CLIs SHALL show a card per agent CLI LADO knows, the installed ones in LADO's order,
then the ones not installed, then one for a model of a CLI LADO does not know, its field off.
A card's head SHALL give the title and the login state. Its row **Default model** SHALL hold the
picker.

#### Scenario: First open
- **WHEN** Claude Code, Codex CLI and OpenCode are installed and logged in, Kilo CLI is not
  installed, and nothing is saved
- **THEN** the cards are Claude Code, Codex CLI, OpenCode, then Kilo CLI, each with its Default
  model on its settings and no list of models

### Requirement: The lead of Your agent CLIs

The block's lead SHALL say `A default model for each agent CLI. Left on its settings, the agent
CLI chooses. Your models come from the model servers below.`, and with no configured model at all `A default model
for each agent CLI. To add models of your own, add a model server below and tick the agent CLIs
that run them.`

#### Scenario: Nothing saved
- **WHEN** no model is saved and the human opens Settings
- **THEN** the lead says how to add models and no card has a list of models

### Requirement: An agent CLI's models on its card

A card with configured models SHALL list them under its Default model, the card's default first,
the others by name ignoring case, under the head `Your models <n>`, Model, From: the name (wrapped,
never cut), the model, its server (the address on hover) and ×.

#### Scenario: Removing a model
- **WHEN** the human presses × on `Рабочая Qwen`, no agent CLI's default
- **THEN** its row says `Removed Рабочая Qwen. Undo`, and OpenCode's tick under its model is off

### Requirement: A long table of models folds

A card with more than five models SHALL show five, with `Show all <n> models` under them, and
`Show fewer` when unfolded; the state SHALL last while the page stays open, and no new model,
removal or Undo SHALL fold it. The focus SHALL stay on the button.

#### Scenario: Nine models of OpenCode
- **WHEN** OpenCode has nine models, `Локальная Qwen` its default
- **THEN** the card shows `Локальная Qwen` and the first four others by name, and `Show all 9
  models`

### Requirement: Renaming a model on its card

A click on a name, or Enter on it, SHALL turn it into a field no wider
than its cell, the name selected; Enter or leaving it SHALL rename the model under the rules of a
model's name, Esc SHALL restore it; there SHALL be no Save or Cancel button. A refused name
SHALL keep the field with the refusal under it; leaving it then restores the name. On hover the
name SHALL show a frame and the title `Click to rename`.

#### Scenario: A renamed model
- **WHEN** the human renames `qwen3-8b · LM Studio · OpenCode` to `Alpha`
- **THEN** `Alpha` shows first on OpenCode's card, no other card moves, `lado model list` shows
  it, and a default on it stays

#### Scenario: A name taken
- **WHEN** the human renames a model to the name of another, in another case, and presses Enter
- **THEN** under the field it shows the name-taken line, and nothing changes

#### Scenario: Esc
- **WHEN** the human types a new name and presses Esc
- **THEN** the old name shows and nothing is saved

### Requirement: One picker of a model

The field Default model SHALL be a picker over the list the core computes for the CLI, read when
it opens, in this order, an empty group not shown: `<CLI>'s settings` with `no model set: the
agent CLI chooses`; YOUR MODELS, with their id and server; BUILT-IN, the CLI's list or its
aliases (`BUILT-IN · aliases`); `Other name…`, kept at the bottom, only when the CLI gives no
full list. Any later place that picks a model SHALL use this component.

#### Scenario: OpenCode with a server
- **WHEN** the human opens the picker of OpenCode with two of its models saved
- **THEN** it shows OpenCode's settings, those two with `LM Studio дома`, then its built-in
  models, and no `Other name…`

#### Scenario: Codex CLI on OpenAI
- **WHEN** the human opens the picker of Codex CLI logged in to OpenAI
- **THEN** it shows the full list and no `Other name…`

### Requirement: Picking saves at once

Picking a row SHALL close the list, save the default as `lado model default` does, keep the
focus on the field and show the value. A refusal SHALL show under the field and leave the value
as it was. `<CLI>'s settings` SHALL clear the default. The page SHALL NOT say that sessions use
the value.

#### Scenario: A model of the list
- **WHEN** the human picks `anthropic/claude-sonnet-4-5` on Kilo CLI's card
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
- **WHEN** the human opens the picker of the last card at the bottom of the window
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
- **WHEN** the human types `claude-opus-4-1-20250805` and presses Use on Claude Code's card
- **THEN** it is Claude Code's default and the warning that LADO cannot check it stays under the
  field

### Requirement: A list that cannot be read

While a list is read the picker SHALL show the CLI's configured models and `reading the
models…`. When it cannot be read the picker SHALL say why above the configured models, with
`Read again` when reading may help, and offer `Other name…`. With a built-in default the card
SHALL show the same warning under the field with `Check again`.

#### Scenario: kilo models times out
- **WHEN** `kilo models` does not end in time and the human opens Kilo CLI's picker
- **THEN** it says the command timed out, shows Kilo CLI's external models and `Other name…`

#### Scenario: Codex CLI on another provider
- **WHEN** Codex CLI's model provider is not OpenAI
- **THEN** the picker says Codex CLI gives no list for that provider, with no `Read again`, and
  offers `Other name…`

### Requirement: A CLI not installed on its card

A card of an agent CLI not installed SHALL say in its head `⚠ not installed`, `⚠ not installed:
its default model cannot run` when it has a default, or `⚠ not installed: its models cannot run`
when it has models and no default; its field SHALL be off and show
the value, and SHALL NOT open. Its default SHALL be cleared by `Use <CLI>'s settings` under the
field. Its models SHALL still be renamed and removed.

#### Scenario: Kilo CLI removed with a default
- **WHEN** Kilo CLI is not installed and its default is `Локальная Qwen`
- **THEN** the card shows the value, the field does not open, and `Use Kilo CLI's settings`
  clears it

### Requirement: A built-in default the list lost

When a CLI's list was read and lacks its built-in default, the field SHALL show it with `⚠ no
longer listed`, the picker SHALL show it first in BUILT-IN with `no longer listed`, and under the
field a warning SHALL say `<CLI> no longer lists <model>: agents on it stop at their first
turn.` with `Use <CLI>'s settings`. Nothing but the human SHALL change the default.

#### Scenario: A model gone from Kilo CLI
- **WHEN** Kilo CLI's default is `old/model`, and the list read when the page opened lacks it
- **THEN** the card shows it with the warning, and it stays Kilo CLI's default

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
server's model takes the whole process: the agent runs only on that server.`, and with an
external default the card SHALL say `On <CLI> this model takes the whole process: an agent on it runs only on
<server>.` under the field. Which CLIs say so SHALL come from the provider, not from the page.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `work`
- **THEN** the card says `On Claude Code this model takes the whole process: an agent on it runs
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
- **THEN** the question names it, and once confirmed OpenCode's card shows `OpenCode's settings`
  and `Its default model Локальная Qwen was removed with LM Studio дома.` until the human's next
  change in the section

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
  default again; removed by its tick, the card says `Its default model Локальная Qwen was
  removed.`

### Requirement: The picker works from the keyboard

The field SHALL be a combobox named `Default model of <CLI>`: Enter, Space, ↓ and ↑ open it on the
selected row; ↑ ↓ Home End move; Enter or Space picks; Esc and Tab close without a pick; a click
outside closes. With search the focus SHALL be in the search field, Esc first clearing its text.
Esc, a pick and a press on nothing SHALL return the focus to the field; Tab and a press on
another control SHALL go on from there.

#### Scenario: Esc in a search
- **WHEN** the human types in the picker's search and presses Esc twice
- **THEN** the first clears the text, the second closes the list, and the focus is on the field

### Requirement: The notes under the field

Notes under the field SHALL be tied to it by `aria-describedby`; a warning after a background
read SHALL be a status, a refusal an alert.

#### Scenario: A refused pick
- **WHEN** a pick is refused
- **THEN** the refusal under the field is an alert the field is described by
