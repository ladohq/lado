## Purpose
The New session window and its Resume mode: the place first as one list of recent places and other ways, the task second, the team as one line, a footer that says what is missing, and the agent's default for a new session.

## ADDED Requirements

### Requirement: The window asks for the place, then the task, then shows the team

The New session window SHALL show, top to bottom: **Where** (one combobox), **Task** (a text
field), **Team** (a one-line summary with Change), then a footer that never scrolls with
Cancel and the start button. The window SHALL have no source switch and no Advanced row.

#### Scenario: The fields in order
- **WHEN** the human opens New session with past sessions
- **THEN** the window shows Where, Task and Team in that order, and no From scratch |
  Folder | Clone from URL | Project switch

### Requirement: Where lists the recent places and the other ways

Where's list SHALL show a group **Recent**: the places of the latest started sessions, at most
10, latest first, a folder by its last segment and a project repository by its name with the
badge `Project <title>`, each with its path muted and the time its session started (a running
one) or stopped; then a
group **Somewhere else**: Other folder…, Clone from URL…, New empty folder… and Project….

#### Scenario: A folder and a project repository
- **WHEN** the human started a session in `~/workspace/webapp` today and one in the
  repository `backend` of the project Shop yesterday, and opens Where's list
- **THEN** Recent lists `webapp` first, then `backend` with the badge `Project Shop`

#### Scenario: Another way
- **WHEN** the human picks Clone from URL…
- **THEN** Where shows Clone from URL with the fields Repository URL, Branch and Clone into
  under it, and the start button reads `Clone and start in <folder>`

### Requirement: Where takes a typed path

Typing a path (starting with `/` or `~`) in Where SHALL list `Use folder <path>` first, then
the subfolders of its parent that start with what follows the last `/`, as the folder check
gives them; the arrow keys and Enter pick one, the first Esc closes only the list.

#### Scenario: A typed path
- **WHEN** the human types `~/workspace/we`
- **THEN** the list shows `Use folder ~/workspace/we` and `webapp/`, and Enter on `webapp/`
  puts `~/workspace/webapp` in Where

### Requirement: The window opens on the last place

The New session window SHALL open with Where on the first recent place and the focus in
Task; with no recent places, on New empty folder with the focus in Folder name; opened from a
project's page, on that project (and repository). It SHALL show no message above Where.

#### Scenario: Back where the human worked
- **WHEN** the latest started session ran in `~/workspace/webapp`, and the human opens New
  session
- **THEN** Where shows `webapp`, the folder is checked, the focus is in Task, and the start
  button names the place

#### Scenario: The first session ever
- **WHEN** LADO has no sessions and the human opens New session
- **THEN** Where shows New empty folder and no message stands above it

### Requirement: Task is a visible field sent as the first message

Task SHALL be a visible text field of three lines with the placeholder `What should the team
do?`, Enter making a new line; its trimmed text SHALL go as `prompt` of the start or the
resume, none for white space; over `Limits.max_message` it SHALL say `<n> characters, the
limit is <limit>` and keep the start button off.

#### Scenario: A task sent
- **WHEN** the human types `Add a contact form` in Task and starts the session
- **THEN** the request carries `prompt: "Add a contact form"`, and the session's Activity
  shows it as the human's message

### Requirement: Team is a summary that opens the rarely changed fields

Team SHALL read `Setup <kits> · Agent <CLI title> · Permissions <mode's summary> · Name
<name>` with **Change**; Change SHALL open Session name, Agent, Team setup, Permissions, Model
and Switch off, and read Hide while open. A refusal of one of these fields SHALL open Team
and put the focus on that field.

#### Scenario: The summary
- **WHEN** the folder's last session ran Claude Code with the kit `default` in mode `default`
- **THEN** Team reads `Setup default`, `Agent Claude Code`, `Permissions Asks before
  changes` and `Name webapp-2`

#### Scenario: A refused model opens Team
- **WHEN** the start is refused for the model
- **THEN** Team opens, the Model field shows the refusal and has the focus

### Requirement: The agent comes from the folder, else from the last session

A new session with no provider given SHALL take, in order: the provider of the folder's last
session if installed, else that of the latest started session of any folder if installed,
else the only one installed; else none, and `lado start` refuses and names the installed
ones. `lado start` and the window SHALL use this one rule.

#### Scenario: A new folder after a Claude session
- **WHEN** Claude Code and Codex CLI are installed, the latest session ran `claude`, and the
  human starts in a folder with no sessions
- **THEN** `lado start` takes `claude` and prints `claude (your last session)`, and the
  window's Team reads `Agent Claude Code`

#### Scenario: No session at all
- **WHEN** two CLIs are installed and LADO has no sessions
- **THEN** `lado start` refuses with `which agent CLI should the session run?` and the
  window shows Agent `choose…`

### Requirement: Permissions are named in words

Permissions SHALL list the agent's modes as radio rows titled by the provider's words for
each, the description shown under the chosen row and always under a risky one; a mode with
no words SHALL be listed by its CLI value; an agent with no modes SHALL show `No permission
modes.` and Team no Permissions.

#### Scenario: Claude Code's risky mode
- **WHEN** Team is open for Claude Code
- **THEN** the row `Full access, never ask ⚠` shows its description even when not chosen,
  and `Ask before changes (recommended)` is chosen by default

#### Scenario: A mode with no words
- **WHEN** a provider lists a mode `manual` with no words
- **THEN** the row reads `manual` and has no description

### Requirement: A stopped session of the place offers Resume beside a new start

When the place has a stopped session of its default name, the window SHALL name the new
session by the free name, say `Session <name> stopped here <when>` under Where, and show
`Resume <name>` and `Start new session <free name>` in the footer; the primary SHALL be Resume
while Task is empty and Start new while Task holds text.

#### Scenario: Back to a stopped session
- **WHEN** `~/workspace/webapp` has the stopped session `webapp` and the window opens on it
- **THEN** Team reads `Name webapp-2`, the footer shows `Resume webapp` as the primary and
  `Start new session webapp-2` beside it

#### Scenario: A new task
- **WHEN** the human types a task
- **THEN** `Start new session webapp-2` becomes the primary, the buttons keep their places,
  and pressing it starts `webapp-2` with the task

#### Scenario: Resume with a task
- **WHEN** the human presses `Resume webapp` with a task typed
- **THEN** the window resumes `webapp` with the task as `prompt` and the Team fields changed

### Requirement: A name taken elsewhere gives the free name

When another running session or a session of another folder has the default name, the window
SHALL take the free name with one start button; a name the human typed that is taken SHALL be
refused under Session name with `aria-invalid` and Team open; a `409` after the press SHALL
open Team, focus Session name and offer `Use <next free name>`.

#### Scenario: A running session has the name
- **WHEN** the session `webapp` runs and the window opens on `~/workspace/webapp`
- **THEN** Team reads `Name webapp-2` and the footer has one start button

### Requirement: The footer says what is missing

While the start button is off, the footer SHALL show `To start: ` and the missing items as
links that focus their fields (opening Team when needed): choose a place, wait for the check,
name the folder, wait for the agent CLIs, choose an agent (also when their list failed),
choose a team setup, choose a smaller folder, choose another folder, tell git who you are,
wait for the count, fix the model, shorten the task, log in to `<CLI>`.

#### Scenario: The agent CLIs not known yet
- **WHEN** the folder will do and `/api/providers` has not answered
- **THEN** the start button is off and the footer reads `To start: wait for the agent CLIs`

#### Scenario: Enter beside a stopped session
- **WHEN** the place has a stopped session, Task is empty and the human presses Enter in a
  field of the window
- **THEN** the window resumes that session, as its blue button `Resume <name>` would

#### Scenario: No agent chosen
- **WHEN** two CLIs are installed and none is suggested
- **THEN** Team shows Agent `choose…` in its summary and the footer reads `To start: choose
  an agent`; the link puts the focus on Agent

### Requirement: Secondary explanations are behind an info button

An explanation that is not needed to act SHALL be behind an info button beside its label,
named `About <field>`, opened and closed by a press or Enter, closed by Esc (the window
stays), by a press outside, by another info button or by Tab; hover SHALL open nothing.

#### Scenario: About Task
- **WHEN** the human presses the info button beside Task
- **THEN** a popover reads `The team gets this as its first message and answers in the chat.
  You can leave it empty.`, the focus stays on the button, and Esc closes it without closing
  the window

### Requirement: The window's frame keeps the footer in view

The window SHALL stand 40 px from the top and grow down, its body scrolling and its footer
not; at 760 px or less it SHALL be a full-screen sheet with targets of at least 44 px and the
footer above the screen's safe area.

#### Scenario: A phone
- **WHEN** the window is open with Team open on a 390×844 screen
- **THEN** the start button is in view without scrolling, and the body scrolls under it

### Requirement: The start button keeps the focus and a refusal takes it to the field

While a start, set-up or resume runs, the button SHALL stay focusable, marked
`aria-disabled`, and read `Starting…`, `Setting up…` or `Resuming…`; a refusal SHALL put the
focus on the field to fix, else on the refusal. Each note under a field SHALL be in the
field's `aria-describedby`, and a refusal SHALL set `aria-invalid` on it.

#### Scenario: A refused start
- **WHEN** a start is refused for the session's name
- **THEN** the focus is on Session name, which has `aria-invalid="true"`, never on the
  page's body

### Requirement: The window keeps its draft until a start

Closing the New session window without a start SHALL keep Where's choice, Task and the Team
fields, the model picked too (for the agent CLI it was picked for), for its next opening in
the page; a start SHALL clear them, and a reload of the page loses them.

#### Scenario: Esc with a task typed
- **WHEN** the human types a task, presses Esc and opens New session again
- **THEN** Task holds the text and Where the same place

### Requirement: The Resume window says what resuming keeps

The Resume window SHALL be titled `Resume session`, show `<name> · stopped <when>` with an
info button and `Start a new session instead`, Where fixed, a field **Message** sent as
`prompt`, and the button `Resume <name>`; `Start a new session instead` SHALL turn it into
New session on the same place with the free name.

#### Scenario: Start a new session instead
- **WHEN** the human presses `Start a new session instead` in the Resume window of `webapp`
- **THEN** the window becomes New session on `~/workspace/webapp` with Team's name `webapp-2`

### Requirement: The rail's item is New session

The rail's item that opens the window SHALL be named `New session`, as the list's `+` and the
window's title are.

#### Scenario: The rail
- **WHEN** the human hovers the rail's item that opens the window
- **THEN** its name and tooltip read `New session`
