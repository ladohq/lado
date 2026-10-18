## MODIFIED Requirements

### Requirement: The New session window clones from a URL

The New session window SHALL have a switch **From scratch | Folder | Clone from URL** in
its first field (capability session-scratch).
With Clone from URL it SHALL show a URL field, **Clone into** (the default folder, which
follows the URL until the human edits it) with the target folder's state, **Branch**
(listed by the server half a second after the URL stops changing, `fetching branches…`
meanwhile; the default branch chosen and marked `(default)`; a field that filters as the
human types when there are more than 30), and the folder's Name, Kits, Provider and Permission mode. Its
button **Clone and start** SHALL be on only when the branches are listed and the folder is
`new` or `empty`. A listing failure SHALL show under the URL with its hint and Copy. For
`same_repo` the button SHALL be **Use this clone**, with the note `LADO will use it as it
is: no clone, no pull, no branch switch`; it switches the window to Folder with that
folder and changes nothing on disk. While the clone runs the window SHALL show the phase,
the percent with a bar and the elapsed time, lock its fields, keep its ×, Esc and Cancel
from closing it, and offer **Cancel clone**. After the clone it SHALL start the session
as Start does for a folder; a refused start SHALL switch the window to Folder with the
cloned folder and show the refusal there.

#### Scenario: Branches come by themselves
- **WHEN** the human types a URL and stops
- **THEN** the Branch field lists the remote's branches with the default one chosen, and
  Clone and start turns on

#### Scenario: The window cannot be closed during a clone
- **WHEN** a clone runs and the human presses Esc or ×
- **THEN** the window stays; only Cancel clone ends the clone

#### Scenario: A name taken after the clone
- **WHEN** the clone ends and the start is refused because the name is taken
- **THEN** the window shows Folder with the cloned folder and the refusal, and the clone
  stays
