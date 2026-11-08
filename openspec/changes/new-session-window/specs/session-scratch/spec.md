## MODIFIED Requirements

### Requirement: The New session window starts from scratch

The New session window SHALL offer a fresh start as **New empty folder…** in Where's group
Somewhere else. It SHALL open on New empty folder when there are no recent places
(`/api/folders/recent` answers none), else on the last place (capability
new-session-window); the human's own pick SHALL be kept. The Resume window SHALL offer no
other place, as before.

#### Scenario: A developer's window
- **WHEN** a human with past sessions opens New session
- **THEN** Where shows the place of the latest started session, not New empty folder

### Requirement: From scratch shows the name, the folder and the author

New empty folder SHALL show **Folder name** (a text field, placeholder `Coffee shop site`)
with an info button reading `LADO creates it in <workspace>.`, a quiet note `folder <name>`
when the name differs from the text, the name's refusal or the folder's (a folder with
files, a file, a folder in a repository), and the author's refusal with its hint and Copy;
then Task and Team as for a folder, Team's Name being the folder's name.

#### Scenario: The first window
- **WHEN** a human with no sessions opens New session and types `Сайт кофейни` in Folder
  name
- **THEN** Where shows New empty folder, the note reads `folder sait-kofeini`, and Team
  reads `Name sait-kofeini`

### Requirement: Create and start goes on only with a fresh start that can

**Create and start** SHALL be on only with a name, a folder `new` or `empty`, an author known
and a name free; while off, the footer SHALL say what is missing (`name the folder`, `tell
git who you are`). It sends `where: {kind: "scratch", path}`, the name and the title. A start
refused after the repository was made SHALL turn Where to that folder and show the refusal.

#### Scenario: No author
- **WHEN** git does not know the author
- **THEN** the window shows the author's text and hint with Copy, Create and start is off,
  and the footer reads `To start: tell git who you are`

### Requirement: In Folder an empty folder offers Start from scratch here

A folder picked or typed in Where with `FolderInfo.scratch` SHALL show `There is no such
folder — LADO will create it.` for `missing`, else `The folder is empty: LADO can start it
from scratch.`, in a neutral note with the button **Start from scratch here**, which turns
Where to New empty folder with that folder as its target and its last segment in Folder name.

#### Scenario: Start from scratch here
- **WHEN** the human picks an empty folder `/Users/ann/Documents/coffee-site` in Where
- **THEN** the window shows Start from scratch here, and pressing it shows New empty folder
  with Folder name `coffee-site`, that folder as the target, and Create and start
