## MODIFIED Requirements

### Requirement: From scratch shows the name, the folder and the author

New empty folder SHALL show **Folder name** (a text field, placeholder `Coffee shop site`)
with an info button reading `LADO creates it in <workspace>.`, a quiet note `folder <name>`
when the name differs from the text, the name's refusal or the folder's (a folder with
files, a file, a folder in a repository), and the author's refusal with its hint and Copy;
the note `Also the session’s name.` under Folder name; then Task, without a Name field, and Team
as for a folder.

#### Scenario: The first window
- **WHEN** a human with no sessions opens New session and types `Сайт кофейни` in Folder
  name
- **THEN** Where shows New empty folder, the note reads `folder sait-kofeini`, Folder name
  notes `Also the session’s name.`, and Task's label row has no Name field
