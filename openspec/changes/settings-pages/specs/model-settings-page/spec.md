## ADDED Requirements

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
and × on one line, then `<model> · <server> · <agent CLI>` on the next, wrapped whole; × SHALL be
32 px, and 44 px on a phone.

#### Scenario: Tablet
- **WHEN** the human opens Model servers in a window 768 px wide with four models
- **THEN** each model takes two lines, no name or id is cut, and the page does not scroll sideways

## MODIFIED Requirements

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

### Requirement: A tick of several models

When several configured models have the same CLI, model and server, their tick SHALL be on
and disabled, its title naming them; they SHALL be removed in Your models.

#### Scenario: Two names for one model
- **WHEN** `Быстрая` and `Сильная` are both OpenCode's `qwen3-8b` on `LM Studio дома`
- **THEN** the tick of OpenCode under `qwen3-8b` is on and disabled, and its title names
  both

### Requirement: A model its source no longer lists

When a source's list was read and lacks the model of a configured model of that source,
the model SHALL show first in the list, ticked, marked `no longer listed`, and in Your models with `⚠ not in list`, its title saying agents on it stop at their first turn.
Nothing SHALL remove it but the human; unticking it SHALL remove it from the list too.

#### Scenario: A model gone from the server
- **WHEN** `mistral-7b · LiteLLM` is saved and `LiteLLM` no longer lists `mistral-7b`, and
  the human opens `LiteLLM`
- **THEN** `mistral-7b` shows first, ticked, marked `no longer listed`, and the model stays
  saved

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

### Requirement: An external model on Claude Code or Codex CLI

The picker of Claude Code or Codex CLI with external models SHALL say above them `On <CLI> a
server's model takes the whole process: the agent runs only on that server.`, and with an external default the CLI's row SHALL say `On <CLI> this model takes the whole process: an agent on it runs only on
<server>.` under the field. Which CLIs say so SHALL come from the provider, not from the page.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `work`
- **THEN** the row says `On Claude Code this model takes the whole process: an agent on it runs
  only on work.`

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

### Requirement: A request LADO's server did not answer promises nothing

A failed request of Settings → Agent CLIs or Model servers that got no answer from LADO's server SHALL read `LADO's server does not answer: your request may or may not have reached it.`, and SHALL NOT say that nothing was done.

#### Scenario: The server stops during a save
- **WHEN** a request of Settings → Agent CLIs or Model servers gets no answer from LADO's server
- **THEN** the page shows that line

### Requirement: The UI calls Claude Code, Codex CLI, OpenCode and Kilo CLI agent CLIs

The UI SHALL name what runs an agent "agent CLI": the New session window's field `Agent
CLI`, Settings' page `Agent CLIs`, the system panel's `Agent CLIs`, and
every line pointing to that page `Settings → Agent CLIs`; Model servers SHALL say `agent CLI`, or `CLI` where room is short. The commands' options (`--provider`, `--cli`) SHALL stay as they are.

#### Scenario: A worker refused for a CLI not logged in
- **WHEN** a session starts with Claude Code not logged in
- **THEN** the refusal says `log in in Settings → Agent CLIs`, and that heading shows in Settings

#### Scenario: An old link
- **WHEN** the human opens `/settings#providers-and-environment`
- **THEN** the address becomes `/settings/agent-clis`

### Requirement: The section fits a phone

On a window narrower than 600 px the forms of Model servers SHALL show their fields one under the
other; their icon buttons, ×, Undo, Agent CLIs' pickers and the picker's search SHALL be at
least 44 px high and a list's row 44 px high; `Default model` SHALL show over the field; the
field SHALL hide the id and keep the name and the server's mark; a server's list of up to 20
models SHALL not scroll within itself; and no part of either page SHALL make the page scroll
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
- **WHEN** a server `LiteLLM на работе` has the badges `OpenAI-compatible` and `key`, and Claude Code's row holds `claude-opus-4-1-20250805` on it, in a window 390 px wide
- **THEN** the server's name and the model's id show whole, wrapped, never cut with `…`

## REMOVED Requirements

### Requirement: Settings has a section Models
**Reason**: Settings is a page per section (capability `settings-pages`); the models' section
is the page Model servers and the default models are in Agent CLIs' rows.
**Migration**: "Settings has a page Model servers" and `settings-pages`' "A CLI's row on Agent
CLIs holds its default model".

### Requirement: Opened at its anchor, Models stays at the top
**Reason**: the page Model servers has nothing above it that grows; `#models` is replaced by
`/settings/model-servers`.
**Migration**: `settings-pages`' "Old addresses of Settings lead to the new pages".

### Requirement: A card per agent CLI
**Reason**: the per-CLI cards go; a CLI's default model is in its row on Agent CLIs.
**Migration**: `settings-pages`' "A CLI's row on Agent CLIs holds its default model".

### Requirement: The lead of Your agent CLIs
**Reason**: the block Your agent CLIs goes; Agent CLIs' lede and its line about model servers say it.
**Migration**: `settings-pages`' "A CLI's row on Agent CLIs holds its default model".

### Requirement: An agent CLI's models on its card
**Reason**: the models are one table on Model servers.
**Migration**: "Your models is one table of the human's models".

### Requirement: A long table of models folds
**Reason**: one table of all models replaces the cards; it does not fold.
**Migration**: "Your models is one table of the human's models".

### Requirement: Renaming a model on its card
**Reason**: renaming moves to the one table.
**Migration**: "Renaming a model in Your models".

### Requirement: A CLI not installed on its card
**Reason**: the cards go; a CLI not installed has no picker in its row.
**Migration**: `settings-pages`' "A CLI not installed has no picker".
