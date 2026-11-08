## Purpose
Settings as a page per section beside a list of their names and icons: the sections'
addresses and the old ones that lead to them, a phone's list and pages, setting rows, General's
theme and notifications, and Agent CLIs' rows that hold each CLI's login and default model.

## ADDED Requirements

### Requirement: Settings is a page per section beside a list

Settings SHALL show each section on a page of its own at `/settings/<section>`: General
`/settings/general`, Agent CLIs `/settings/agent-clis`, Model servers `/settings/model-servers`
and Statistics `/settings/statistics`, in that order, with the list of sections beside the page
above 600 px. The list, the routes and the pages' headings SHALL come from one list of sections.
`/settings` SHALL open General above 600 px.

#### Scenario: Settings from the rail on a computer
- **WHEN** the human clicks Settings on the rail in a window 1440 px wide
- **THEN** the address is `/settings/general`, the list shows General as the current item and
  the page's heading reads `General`

#### Scenario: Another section
- **WHEN** the human clicks Model servers in the list
- **THEN** the address is `/settings/model-servers`, the page's heading reads `Model servers`, and
  the focus is on that heading

### Requirement: The list of sections shows names and icons only

Each item of the list SHALL show the section's icon and name and nothing else: no line of
state, no mark or count, in any state of the section. The current item SHALL be marked as the
current page.

#### Scenario: A CLI needs a login
- **WHEN** Claude Code needs a login and an agent waits for it, and the human opens Settings
- **THEN** the list's item Agent CLIs reads `Agent CLIs` with its icon, and no mark

### Requirement: On a phone the list is a page of its own

In the phone layout `/settings` SHALL show the list alone, each item at least 52 px high with a
chevron, and a section's address SHALL show its page alone with a link `‹ Settings` back to the
list.

#### Scenario: A section on a phone
- **WHEN** the human taps Statistics in the list on a phone
- **THEN** the Statistics page shows alone with `‹ Settings`, and `‹ Settings` leads back to the
  list

### Requirement: Old addresses of Settings lead to the new pages

The old addresses of Settings' sections SHALL be replaced by their pages, with no new history
entry: the anchors of the one page (`#providers-and-environment`, `#models`, `#statistics`,
`#notifications`, `#appearance`) and the addresses of the earlier designs
(`/settings/agent-clis-and-environment`, `/settings/models`, `/settings/usage-statistics`); any
other `/settings/<unknown>` SHALL be replaced by `/settings`.

#### Scenario: A bookmark of the models
- **WHEN** the human opens `/settings#models` or `/settings/models`
- **THEN** the address becomes `/settings/model-servers`, and Back leaves Settings

#### Scenario: The logins
- **WHEN** the human opens `/settings#providers-and-environment` or
  `/settings/agent-clis-and-environment`
- **THEN** the address becomes `/settings/agent-clis`

#### Scenario: The statistics
- **WHEN** the human opens `/settings#statistics` or `/settings/usage-statistics`
- **THEN** the address becomes `/settings/statistics`

#### Scenario: General's anchors
- **WHEN** the human opens `/settings#notifications`, then `/settings#appearance`
- **THEN** the addresses become `/settings/general#notifications`, with the row in view, then
  `/settings/general`

#### Scenario: An unknown section
- **WHEN** the human opens `/settings/kits`
- **THEN** the address becomes `/settings`

### Requirement: A setting is a row with its name and its control

A setting SHALL be a row with no card around it: its name and at most one short line on the
left, its control on the right, a thin line between rows; a control too wide to sit beside its
name SHALL go under it at 900 px and narrower. The name SHALL label the control and the line
describe it.

#### Scenario: General
- **WHEN** the human opens General
- **THEN** it has two rows: `Theme` with System, Light and Dark, and `Browser notifications`
  with `When something waits for you and this tab is hidden.` and a switch

### Requirement: Browser notifications is a switch

The row Browser notifications at `/settings/general#notifications` SHALL be a switch, which on
turning on asks the browser and, refused, stays off with the reason under the row in one line;
Needs you SHALL show the same words.

#### Scenario: Blocked by the browser
- **WHEN** the browser blocks notifications for the page and the human turns the switch on
- **THEN** the switch stays off and the row says `Blocked by the browser: allow them in the site
  settings (icon left of the address), then switch on again.`

#### Scenario: The other refusals
- **WHEN** the page is not secure, the browser has no notifications, the human dismissed the
  browser's question, or the browser will ask again
- **THEN** the row says `Needs a secure page: open LADO at 127.0.0.1 or localhost.`, `Not
  supported by this browser.`, `Not allowed: switch on again and allow them.` or `The browser
  asks again: switch on and allow them.`

#### Scenario: From the message on Needs you
- **WHEN** the human follows `Settings` in Needs you's line that notifications are on
- **THEN** General opens with the row Browser notifications in view

### Requirement: A CLI's row on Agent CLIs holds its default model

Agent CLIs SHALL show under the heading the line `Changes apply to agents started afterwards.`
and, in each installed CLI's row under its login, the label `Default model` and the CLI's picker,
whatever its login, with the picker's warnings and their ways out under it. With no model server
saved a line under the rows SHALL read `Models of your own come from a model server: Model
servers`, its last words a link to that page.

#### Scenario: A default on a server's model
- **WHEN** Kilo CLI is installed with no login and its default is `qwen3-8b · lmstudio`
- **THEN** Kilo CLI's row shows `No login`, `Log in…` and, under them, `Default model` with
  `qwen3-8b · lmstudio` in its picker

#### Scenario: No model server
- **WHEN** no model server is saved
- **THEN** every picker shows its CLI's settings, and the line under the rows leads to Model
  servers

### Requirement: A CLI not installed has no picker

A CLI that is not installed SHALL have no picker in its row. When it has a default model its
row SHALL say `Default model: <name> — cannot run: not installed` with `Use <CLI>'s settings`,
which clears the default.

#### Scenario: Kilo CLI removed with a default
- **WHEN** Kilo CLI is not installed and its default is `Локальная Qwen`
- **THEN** its row says `Default model: Локальная Qwen — cannot run: not installed`, and `Use
  Kilo CLI's settings` clears the default

#### Scenario: Not installed, no default
- **WHEN** OpenCode is not installed and has no default
- **THEN** its row shows its name, `not installed` and its install hint, and nothing about a
  model

### Requirement: A link to a CLI's row focuses its login button

`/settings/agent-clis#<cli>`, with the provider's name (`claude`, `codex`, `kilo`, `opencode`),
SHALL scroll that CLI's row into view once its rows are read and put the focus on its login
button, else on its name; a later read of the rows SHALL NOT scroll again. An unknown `<cli>`
SHALL leave the page at its top.

#### Scenario: From Needs you
- **WHEN** the supervisor of a session waits for Claude Code's login and the human presses its
  `Log in…` on Needs you
- **THEN** `/settings/agent-clis#claude` opens, Claude Code's row is in view and its primary `Log
  in…` has the focus

#### Scenario: From the New session window
- **WHEN** the human chose Codex CLI, not logged in, in the New session window and follows `Log in
  first`
- **THEN** `/settings/agent-clis#codex` opens with the focus on Codex CLI's `Log in…`

#### Scenario: A row read again
- **WHEN** the human moved the focus elsewhere and the rows are read again
- **THEN** the page does not scroll
