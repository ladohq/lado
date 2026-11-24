## MODIFIED Requirements

### Requirement: A fresh start needs git to know the commits' author

Before it makes anything, a fresh start SHALL check that its commits have an author: LADO's
commit author, the project's author for a project's repository (capability
commit-authors), or else git's `user.name` and `user.email` in the target's nearest
existing folder (`git config --get`), and SHALL refuse otherwise with the text `nobody signs
the agents' commits: LADO has no commit author and git has no user.name or user.email`.
LADO SHALL NOT write an author into any git config.

#### Scenario: A developer's machine
- **WHEN** git's global config has `user.name` and `user.email` and LADO has no author
- **THEN** the check passes, and the first commit is theirs

#### Scenario: LADO's author on a machine without git's
- **WHEN** git has no `user.name` and LADO's author is `Ann Lee <ann@example.com>`
- **THEN** the check passes, and the first commit carries `Ann Lee <ann@example.com>`

### Requirement: The author's refusal says how to set the author where LADO runs

The refusal of a fresh start for a missing author SHALL carry the hint `Set the commit
author in Settings → Git servers, or run:` with the command `lado git-server author --name
"Your Name" --email you@example.com`, in LADO's container (`LADO_CONTAINER`) as elsewhere.

#### Scenario: The container without the variables
- **WHEN** LADO runs in its container whose `.env` has no `LADO_GIT_NAME` and LADO has no
  commit author
- **THEN** a fresh start is refused with the text and the hint naming Settings → Git
  servers, and nothing is made

### Requirement: From scratch shows the name, the folder and the author

New empty folder SHALL show **Folder name** (a text field, placeholder `Coffee shop site`)
with an info button reading `LADO creates it in <workspace>.`, a quiet note `folder <name>`
when the name differs from the text, the name's refusal or the folder's (a folder with
files, a file, a folder in a repository), and the note of the missing author; the note
`Also the session’s name.` under Folder name; then Task, without a Name field, and Team as
for a folder.

#### Scenario: The first window
- **WHEN** a human with no sessions opens New session and types `Сайт кофейни` in Folder
  name
- **THEN** Where shows New empty folder, the note reads `folder sait-kofeini`, Folder name
  notes `Also the session’s name.`, and Task's label row has no Name field

### Requirement: Create and start goes on only with a fresh start that can

**Create and start** SHALL be on only with a name, a folder `new` or `empty`, an author known
and a name free; while off, the footer SHALL say what is missing (`name the folder`, `set
the commit author`). It sends `where: {kind: "scratch", path}`, the name and the title. A
refused start SHALL show the refusal and keep Where on New empty folder when the folder is
not a repository after it, else turn Where to that folder.

#### Scenario: No author
- **WHEN** nobody signs the commits
- **THEN** the window shows the note of the missing author, Create and start is off, and the
  footer reads `To start: set the commit author`

#### Scenario: A kit's refusal
- **WHEN** the human presses Create and start with the kit `sdlc` and no tracker kit
- **THEN** Where stays on New empty folder with Folder name as typed, the refusal shows with the Team section open, and no folder was made

## ADDED Requirements

### Requirement: The missing author's note leads to Settings and checks again

When nobody signs the commits, New empty folder, the folder set-up and a project's Add
repository → From scratch SHALL show one note: `Agents need a name and email to sign their
commits, and none is set yet.`, a link `Set it in Settings ↗` (`/settings/git-servers?author`,
a new tab) and `Check again`; no author fields. The window SHALL check again when it gets
the focus back, and an author found SHALL replace the note with `✓ Agents commit as <name>
<<email>>.`.

#### Scenario: Back from Settings
- **WHEN** the note shows, the human sets LADO's author in the other tab and comes back
- **THEN** the note goes, `✓ Agents commit as Ann Lee <ann@example.com>.` shows, and the
  footer no longer reads `set the commit author`

#### Scenario: The note's words
- **WHEN** nobody signs the commits and the human types a folder name
- **THEN** the note also reads `Then come back: this window checks again by itself.`, and
  no field for a name or an email shows

#### Scenario: Still nobody
- **WHEN** the human presses Check again and nobody is known yet
- **THEN** the note adds `Checked again: still nobody. Save the name and email in Settings
  first.`
