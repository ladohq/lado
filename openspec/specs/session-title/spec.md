# session-title Specification

## Purpose
A session's optional title: a label for the human shown over its name, which stays the
session's identifier; the one rule of what a title is, where the web UI shows it and lets
the human edit it in place, and `lado title` (docs/design/ui.md, Session title).

## Requirements

### Requirement: A session has an optional title over its name

A session SHALL have an optional title, a label for the human, stored with the session
(`sessions.title`, schema 28), while its name SHALL stay its identifier: setting or
clearing a title SHALL NOT change the session's name, its address in the UI, its tmux
session, its agents' environment, its branches or its worktrees. A title SHALL be set
and cleared only through the core's one rule (`runtime.set_title`), for a session of any
status, running or stopped. The rule SHALL trim white space at both ends of the text; a
text that is then empty or equal to the session's name SHALL clear the title (store
none). It SHALL refuse, with its reason and nothing changed, a text that holds a control
character (a line break, a tab and the other characters of Unicode category Cc) or is
longer than `runtime.MAX_TITLE` (80) characters after the trim, and a session that does
not exist. Two sessions MAY have the same title. A stop and a resume SHALL keep the
title; `lado forget` SHALL delete it with the session, and a new session of that name
SHALL start without one.

#### Scenario: A title is set on a running session
- **WHEN** the human sets the title `Rename sessions (LAD-66)` on the running session
  `lado-2`
- **THEN** the session keeps the name `lado-2`, its page stays at `/sessions/lado-2`, its
  agents keep running, and its title is `Rename sessions (LAD-66)`

#### Scenario: Trimmed, empty and equal to the name
- **WHEN** the human sets `  Ревью kit-sdlc  `, then `   `, then `lado-2` on the session
  `lado-2`
- **THEN** its title is first `Ревью kit-sdlc`, then none, then none

#### Scenario: A refused title
- **WHEN** the human sets a title of 81 characters, or one with a line break
- **THEN** the core refuses it with the reason (`a title is at most 80 characters`,
  `a title is one line`) and the session's title is what it was

#### Scenario: Stop, resume and forget
- **WHEN** a session with a title is stopped and resumed, then stopped and forgotten, and
  a new session of the same name is started
- **THEN** the title is there after the resume, and the new session has none

### Requirement: The UI shows a session by its title, with its name beside it

Wherever the UI names a session, it SHALL show its title when it has one, else its name:
the session list's row, the collapsed list's icon (its letters and accessible name), the
card of a row and of an icon, the session's head, the browser tab's title, the session's
line in Needs you, and the title of the browser's notification. Where it shows a title,
it SHALL also show the name: in the row, first in its grey line (`lado-2 · 3 agents ·
1h 12m`); in the head, small and grey after the title; in the cards, after the title. A
session without a title SHALL look as it does without this change. The list's search
SHALL find a session whose title or name holds the text. The title SHALL reach the page
in `SessionInfo.title` through the change feed, so a title set anywhere (the CLI, another
browser) shows without a reload.

#### Scenario: The list and the head
- **WHEN** the session `lado-2` has the title `Rename sessions (LAD-66)`
- **THEN** its row reads `Rename sessions (LAD-66)` over `lado-2 · …`, its head reads
  `Rename sessions (LAD-66)` with `lado-2` after it, and the browser tab's title names
  `Rename sessions (LAD-66)`

#### Scenario: Search by name or title
- **WHEN** the human types `rename` or `lado-2` in Find a session
- **THEN** the list keeps the session `lado-2` titled `Rename sessions (LAD-66)` both times

#### Scenario: A title set from the CLI while the page is open
- **WHEN** `lado title lado-2 "Review"` runs while the session's page is open
- **THEN** the page's row and head show `Review` without a reload

### Requirement: The human sets the title in place, in the head and in the list

The session's head SHALL have a button **Rename session** (a pencil) after the title,
shown on the title's hover and the button's focus and always on a device without hover;
it and a double click on the title SHALL turn the title into a text field holding the
title (empty without one, the name as its placeholder). The list row's ⋯ menu SHALL hold
**Rename…** first, which turns the row's title into the same field. In the field, Enter
and leaving it SHALL save through `PUT /api/sessions/{name}/title`, Esc SHALL cancel and
change nothing, and an empty field SHALL clear the title. A text over `Limits.max_title`
SHALL be shown as too long under the field and not sent; a refusal of the server SHALL
show under the field (`role="alert"`) with the field kept open and the text kept. After a
save or a cancel the focus SHALL go back to the button that opened the field (the pencil,
or the row's ⋯).

#### Scenario: Rename in the head
- **WHEN** the human presses the pencil in the head of `lado-2`, types `Review`, and
  presses Enter
- **THEN** the title is saved, the head and the row show `Review`, and the focus is on
  the pencil

#### Scenario: Rename from the row's menu and cancel
- **WHEN** the human chooses Rename… in the ⋯ of the row of `lado-2`, types `x`, and
  presses Esc
- **THEN** nothing is sent, the row shows what it showed before, and the focus is on ⋯

#### Scenario: Too long
- **WHEN** the human types 81 characters into the field
- **THEN** the field says it is too long and Enter sends nothing

### Requirement: `lado title` reads and sets a session's title

`lado title <session>` SHALL print the session's title, or that it has none. `lado title
<session> TEXT` SHALL set it and `lado title <session> --clear` SHALL clear it, both
through the core's rule, printing what the title is now; TEXT and `--clear` together
SHALL exit 2. Setting or clearing SHALL be refused inside an agent (`LADO_AGENT` set),
as `lado answer` and `lado flow-set` are; reading SHALL NOT. An unknown session SHALL be
refused with its name. `lado ls` SHALL print a session's title, quoted, after its name
(`lado-2 "Rename sessions (LAD-66)"  /path/to/repo`), and nothing more for a session
without one.

#### Scenario: Set, read, clear
- **WHEN** the human runs `lado title lado-2 "Review"`, `lado title lado-2`, then
  `lado title lado-2 --clear`
- **THEN** the first prints the title `Review`, the second prints `Review`, the third
  says the session has no title, and `lado ls` shows `lado-2` without a title

#### Scenario: Inside an agent
- **WHEN** an agent runs `lado title lado-2 "x"`
- **THEN** it is refused as the human's command and the title is unchanged
