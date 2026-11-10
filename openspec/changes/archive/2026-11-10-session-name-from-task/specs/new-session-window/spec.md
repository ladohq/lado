## ADDED Requirements

### Requirement: Name stands on Task's label row

The New session window SHALL show the session's name as a field **Name** with an info button on
the right of Task's label row, for a folder, a project's repository and a clone, and SHALL NOT
show it in Team. A new empty folder SHALL have no Name field, its Folder name noting `Also the
session’s name.`; the Resume window SHALL have none. At 760 px or less the free room of the row
SHALL fall between Task's info button and `Name`.

#### Scenario: The name beside Task
- **WHEN** the human opens New session on the project `lado`'s repository `lado`
- **THEN** Task's label row reads `Task`, its info button, then `Name`, its info button and a
  field holding `lado`, and Team's summary has no Name

#### Scenario: A phone
- **WHEN** the window is 390 px wide with the Name field
- **THEN** `Task ⓘ` stands at the left, `Name ⓘ` and its field at the right, and the gap
  between them is wider than the gap inside either

#### Scenario: A new empty folder
- **WHEN** Where is New empty folder
- **THEN** Task's label row has no Name field and Folder name notes `Also the session’s name.`

### Requirement: LADO names the session from the task's tracker key, else from the place

Until the human types in Name, the field SHALL hold the automatic name: the first tracker key
anywhere in the task, in small letters; else the place's `default_name`. The task's other words
SHALL NOT make a name. The next
free number added when a session has it, with the note `Name: <base> exists already, so this
one is <id>.` It SHALL follow the task 300 ms after the last keystroke, the place and the
sessions.

#### Scenario: A tracker key
- **WHEN** the human types `LAD-263: the codex model must win`, `[LAD-263] the codex model` or
  `LAD-263 Fix the login` in Task
- **THEN** Name reads `lad-263`

#### Scenario: A key anywhere in the task
- **WHEN** the task is `Fix LAD-263 in the doctor text`, or `Fix the login` with `LAD-263` on its
  second line, or `Fix LAD-263, then LAD-264`
- **THEN** Name reads `lad-263`

#### Scenario: Not a key
- **WHEN** the task holds no word of two or more capital Latin letters, `-` and digits with no
  letter or digit right before or after it (`xLAD-263 glued`, `LAD-263a`, `lad-263`, `L-1`), and
  Where is the folder `webapp`
- **THEN** Name reads `webapp`

#### Scenario: A word with a key's shape
- **WHEN** the task is `HTTP-2 support for the proxy`
- **THEN** Name reads `http-2`, which the human may change before the start

#### Scenario: No key
- **WHEN** Task is empty, or reads `Fix the login redirect after the session expires` or
  `Поправить вход`, and Where is the project `lado`'s repository `lado`
- **THEN** Name reads `lado`

#### Scenario: The name taken
- **WHEN** a session `lad-263` exists and the task starts with `LAD-263:`
- **THEN** Name reads `lad-263-2` and the note under Task says `Name: lad-263 exists already, so
  this one is lad-263-2.`

#### Scenario: Another place
- **WHEN** Task is empty and the human changes Where from `lado` to the folder `webapp`
- **THEN** Name reads `webapp` once the folder is checked

### Requirement: A typed name is kept as the session's title

A name the human typed SHALL stay when the task or the place changes and SHALL be checked again
for being taken; the start SHALL send its plain form as `name` and the typed text as `title`
when they differ, with the note `Name shown as “<title>” · in links and branches: <id>`; a text
with no plain form SHALL be the title of the automatic name. Clearing the field SHALL give the
automatic name back.

#### Scenario: A typed name
- **WHEN** the human types `Review Kao` in Name and starts the session
- **THEN** the request carries `name: "review-kao"` and `title: "Review Kao"`, and the task typed
  afterwards does not change Name

#### Scenario: Another script
- **WHEN** the human types `Вход после сессии` in Name
- **THEN** the start sends the automatic name as `name` and `Вход после сессии` as `title`

#### Scenario: Cleared
- **WHEN** the human empties Name while the task is `LAD-263 Fix the login redirect`
- **THEN** the field shows `lad-263` as its placeholder, and holds it again once the
  focus leaves the field

#### Scenario: A typed name that is taken
- **WHEN** the human types `review-kao` and a session `review-kao` is stopped in `lado`
- **THEN** Name has `aria-invalid="true"`, the note under Task says `Name: a session named
  review-kao exists (stopped, in lado).` with `Use review-kao-2` and no Resume, and the footer
  reads `To start: choose another name`

#### Scenario: Too long
- **WHEN** the human types 81 characters in Name
- **THEN** the note says `Name: at most 80 characters.` and the footer reads `To start: shorten
  the name`

### Requirement: Where shows a place on one line

Where's closed box and each Recent row SHALL show the place's icon, its name, then a muted
secondary on the same line: a project's repository `in project <title>`, a folder its path, New
empty folder the workspace, Clone from URL none; the secondary SHALL be cut first, keeping about
12 characters, then the name. The box SHALL carry `<name> — <secondary>` as its tooltip.

#### Scenario: A project's repository on a phone
- **WHEN** Where is the repository `customer-portal-frontend` of the project `Northwind Traders`
  in a window 390 px wide
- **THEN** the box is one line, the name and the start of `in project Nor…` both showing, cut
  with an ellipsis

#### Scenario: A short pair
- **WHEN** Where is New empty folder in a window 390 px wide
- **THEN** the box reads `New empty folder ~/workspace` whole, on one line

## MODIFIED Requirements

### Requirement: Where lists the recent places and the other ways

Where's list SHALL show a group **Recent**: the places of the latest started sessions, at most
10, latest first, a folder by its last segment and its path muted, a project repository by its
name and `in project <title>` muted, each with the time its session started (a running one) or
stopped, on one line; then a group **Somewhere else**: Other folder…, Clone from URL…, New empty
folder… and Project….

#### Scenario: A folder and a project repository
- **WHEN** the human started a session in `~/workspace/webapp` today and one in the
  repository `backend` of the project Shop yesterday, and opens Where's list
- **THEN** Recent lists `webapp` first, then `backend` with `in project Shop`

#### Scenario: Another way
- **WHEN** the human picks Clone from URL…
- **THEN** Where shows Clone from URL with the fields Repository URL, Branch and Clone into
  under it, and the start button reads `Clone and start in <folder>`

### Requirement: Team is a summary that opens the rarely changed fields

Team SHALL read `Kits <kits> · Agent <CLI title> · Permissions <mode's summary>` with
**Change**; Change SHALL open Agent, Model, Kits (with `+ Add kit` and an info button that says
what kits are), Permissions and Switch off, and read Hide while open. A refusal of one of these
fields SHALL open Team and put the focus on that field.

#### Scenario: The summary
- **WHEN** the folder's last session ran Claude Code with the kit `default` in mode `default`
- **THEN** Team reads `Kits default`, `Agent Claude Code` and `Permissions Asks before
  changes`, and no Name

#### Scenario: A refused model opens Team
- **WHEN** the start is refused for the model
- **THEN** Team opens, the Model field shows the refusal and has the focus

### Requirement: A name taken elsewhere gives the free name

When another session has the automatic name, the window SHALL take the next free one; a name the
human typed that is taken SHALL be refused under Task with `aria-invalid` on Name and `Use <next
free name>`; a `409` after the press SHALL show the core's text there, focus Name and offer `Use
<next free name>`, leaving Team as it is.

#### Scenario: A running session has the name
- **WHEN** the session `webapp` runs and the window opens on `~/workspace/webapp` with Task empty
- **THEN** Name reads `webapp-2` and the footer has one start button

#### Scenario: A race
- **WHEN** another window starts `webapp-2` before the press and the start is refused with 409
- **THEN** the core's text stands under Task with `Use webapp-3`, and the focus is on Name

### Requirement: The footer says what is missing

While the start button is off, the footer SHALL show `To start: ` and the missing items as
links that focus their fields (opening Team when needed): choose a place, wait for the check,
name the folder, name the session, choose another name, shorten the name, wait for the agent
CLIs, choose an agent (also when their list failed), choose a kit, choose a smaller folder,
choose another folder, tell git who you are, wait for the count, fix the model, shorten the
task, log in to `<CLI>`.

#### Scenario: The agent CLIs not known yet
- **WHEN** the folder will do and `/api/providers` has not answered
- **THEN** the start button is off and the footer reads `To start: wait for the agent CLIs`

#### Scenario: Enter beside a stopped session
- **WHEN** the place has a stopped session, Task is empty and the human presses Enter in a
  field of the window
- **THEN** the window starts the new session under the free name, as its button `Start new
  session <free name>` would; the stopped session stays stopped

#### Scenario: No agent chosen
- **WHEN** two CLIs are installed and none is suggested
- **THEN** Team shows Agent `choose…` in its summary and the footer reads `To start: choose
  an agent`; the link puts the focus on Agent

#### Scenario: No kit
- **WHEN** the human removes the last kit
- **THEN** the footer reads `To start: choose a kit`; the link opens Team with the focus on
  `+ Add kit`

### Requirement: The start button keeps the focus and a refusal takes it to the field

While a start, set-up or resume runs, the button SHALL stay focusable, marked
`aria-disabled`, and read `Starting…`, `Setting up…` or `Resuming…`; a refusal SHALL put the
focus on the field to fix, else on the refusal. Each note under a field SHALL be in the
field's `aria-describedby`, and a refusal SHALL set `aria-invalid` on it.

#### Scenario: A refused start
- **WHEN** a start is refused for the session's name
- **THEN** the focus is on Name, which has `aria-invalid="true"`, never on the page's body

### Requirement: The Resume window says what resuming keeps

The Resume window SHALL be titled `Resume session`, show `<name> · stopped <when>` with an
info button and `Start a new session instead`, Where fixed, a field **Message** sent as
`prompt`, and the button `Resume <name>`; `Start a new session instead` SHALL turn it into
New session on the same place with the free name.

#### Scenario: Start a new session instead
- **WHEN** the human presses `Start a new session instead` in the Resume window of `webapp`
- **THEN** the window becomes New session on `~/workspace/webapp` with Name `webapp-2`

### Requirement: A stopped session of the place leaves the new session the free name

When the place has a stopped session of its default name, the New session window SHALL name the
new session by the free name, say `Session <name> stopped here <when>` under Where, and show one
start button, `Start new session <name>`, the primary; it SHALL NOT offer to resume the
stopped session, which the human resumes from its page or the session list.

#### Scenario: Back to a stopped session
- **WHEN** `~/workspace/webapp` has the stopped session `webapp` and the window opens on it
- **THEN** Name reads `webapp-2`, the line under Where says `Session webapp stopped here`,
  and the footer shows Cancel and `Start new session webapp-2` as the primary, no `Resume webapp`

#### Scenario: A new task
- **WHEN** the human types a task without Latin words (`Добавить форму`) and presses `Start new
  session webapp-2`
- **THEN** the window starts `webapp-2` with the task, and `webapp` stays stopped

#### Scenario: The last launch was on another CLI's model
- **WHEN** the Claude Code session `nologin` on `CloudClaude` is stopped in a folder whose last
  launch is a Codex session on `CloudCodex`, neither CLI logged in, and the window opens there
- **THEN** it offers no Resume, and the Resume window of `nologin` (from its page) resumes it on
  Claude Code and `CloudClaude`

#### Scenario: A task names the session
- **WHEN** `~/workspace/webapp` has the stopped session `webapp` and the human types `LAD-263
  Fix the login redirect` in Task
- **THEN** the line under Where still says `Session webapp stopped here`, and the button reads
  `Start new session lad-263`
