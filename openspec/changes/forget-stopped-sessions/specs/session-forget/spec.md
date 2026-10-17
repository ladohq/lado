## ADDED Requirements

### Requirement: The Stopped group's band offers to forget its sessions

The session list's Stopped band SHALL carry, after its count, an icon button (a bin, in
the colour of a dangerous action) whose accessible name and tooltip are "Forget stopped
sessions…", whenever the band is drawn, its group folded or open, with or without text in
the search. The Needs you and Running bands SHALL have no such button, and the list
collapsed to a strip SHALL have none. Pressing it SHALL NOT fold or open the group.

#### Scenario: Seven stopped sessions
- **WHEN** the list holds two running and seven stopped sessions and the Stopped group is
  folded
- **THEN** the Stopped band shows "Forget stopped sessions…" and the Running band shows no
  such button

#### Scenario: No stopped session
- **WHEN** no session is stopped
- **THEN** there is no Stopped band and no "Forget stopped sessions…" button

#### Scenario: On a phone
- **WHEN** the Sessions page is opened in the phone layout with stopped sessions
- **THEN** the Stopped band shows the button and it opens the same window

### Requirement: The window lists the stopped sessions with a tick each

"Forget stopped sessions…" SHALL open a modal window titled "Forget stopped sessions?"
that says their history (messages, runs, notes, gates) is deleted for good, and lists the
stopped sessions the list shows when it opens (with text in the search, only the matching
ones), in the list's order, each with a tick, ticked, its title or name and when it
stopped. A tick "All N" SHALL tick or clear them all. The window SHALL load each session's
forget preview: a session with open runs SHALL say "1 open run" or "N open runs"; a
session whose preview is refused (it is no longer stopped) SHALL show the core's reason,
unticked and off. The worktrees and branches the ticked sessions leave on disk SHALL be
listed under a folded line "Left on disk: N worktrees of M sessions (remove them yourself
if you need to)". The forget button SHALL say `Forget 1 session` or `Forget N sessions`,
N the sessions it will forget, and SHALL be off while previews load or N is 0. Cancel and
Esc SHALL close the window with nothing forgotten.

#### Scenario: All ticked
- **WHEN** the human presses "Forget stopped sessions…" with seven stopped sessions and
  none with open runs
- **THEN** the window lists the seven, all ticked, and the button says `Forget 7 sessions`

#### Scenario: Two cleared
- **WHEN** the human clears the ticks of lad-97 and lad-67
- **THEN** the button says `Forget 5 sessions`, and clearing "All 7" turns it off

#### Scenario: The search narrows the window
- **WHEN** the search holds "lad-8" and the human presses the button
- **THEN** the window lists only the stopped sessions whose name or title matches

### Requirement: A session with open runs is forgotten only with the switch

When a ticked session has open runs, the window SHALL show the switch "Also forget their
N open runs (<sessions>)", off. While it is off such sessions SHALL NOT be forgotten nor
counted on the button, and a line SHALL name them as staying; with it on they SHALL be
forgotten with their runs (the forget's `force`).

#### Scenario: Off
- **WHEN** seven are ticked, lad-88 has one open run and lad-80 two, and the switch is off
- **THEN** the button says `Forget 5 sessions` and pressing it leaves lad-88 and lad-80

#### Scenario: On
- **WHEN** the human turns the switch on and presses `Forget 7 sessions`
- **THEN** all seven are forgotten, lad-88 and lad-80 with their runs

### Requirement: The sessions are forgotten one at a time, each reported

Pressing the forget button SHALL forget the counted sessions one after another, each
through the same forget as the session head's Forget… (`DELETE /api/sessions/{name}`), so
the core decides each. While it works the button SHALL say `Forgetting K of N…`, the ticks
and Cancel be off and Esc do nothing, and each row SHALL say "forgotten" or the core's
reason when its turn ends; a refused session SHALL NOT stop the others. Each forgotten
session SHALL leave the list as the change feed brings it. When every one is forgotten the
window SHALL close by itself; when any is refused it SHALL stay open with the reasons and
a Close button. When the session open in the page is among the forgotten, the UI SHALL go
to `/sessions`.

#### Scenario: All forgotten
- **WHEN** the human presses `Forget 5 sessions`
- **THEN** the five leave the list one by one and the window closes

#### Scenario: One resumed meanwhile
- **WHEN** lad-85 is resumed in another tab after the window opened, and the human
  presses `Forget 5 sessions`
- **THEN** the other four are forgotten, lad-85 stays in the list, and the window stays
  open with lad-85's reason and Close

#### Scenario: The open session
- **WHEN** the page shows lad-97 and the window forgets it
- **THEN** the page goes to `/sessions`

### Requirement: Stop can forget the session in one go

The Stop popover of a running session SHALL have, before `Stop <name>`, a second
dangerous button `Stop and forget` (its tooltip "Stops it, then deletes its history for
good"). It SHALL stop the session, then forget it without `force`, then go to
`/sessions`. When the stop preview names open runs the button SHALL be off and the
popover SHALL say "It has open runs: stop it, then forget it from the Stopped list."
When the stop succeeds and the forget is refused, the session SHALL stay stopped and the
popover SHALL show the core's reason.

#### Scenario: A session with no open runs
- **WHEN** the human opens Stop on running lad-92 and presses `Stop and forget`
- **THEN** lad-92 is stopped and forgotten, and the page is `/sessions`

#### Scenario: A session with open runs
- **WHEN** the human opens Stop on lad-80, which has two open runs
- **THEN** `Stop and forget` is off with the line about open runs, and `Stop lad-80`
  works as before
