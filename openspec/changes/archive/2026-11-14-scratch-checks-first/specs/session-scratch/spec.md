## ADDED Requirements

### Requirement: A new session is checked whole before its folder is made

Before a fresh start, a set-up or `lado start <git-url>` makes a folder, a repository or a clone for a new session, LADO SHALL run every check `runtime.start_session` runs for a new session that needs no repository (one function, which `start_session` calls too) and SHALL refuse with that check's text, the folder as it was.

#### Scenario: A kit that lacks a skill
- **WHEN** `POST /api/sessions` gets `where: {kind: "scratch", path: "~/workspace/rc-check"}` with the kits `["sdlc"]`, and no kit gives the skill `tracker`
- **THEN** it answers 400 with `kit "sdlc" expects skill "tracker"…`, and `~/workspace/rc-check` does not exist

#### Scenario: lado start --new with a kit that lacks a skill
- **WHEN** `lado start --new ~/lado/shop --kit sdlc` runs and no kit gives the skill `tracker`
- **THEN** it exits 1 with the kit's refusal, and `~/lado/shop` does not exist

#### Scenario: Kits that fit
- **WHEN** New empty folder starts `shop` with kits whose skills are all there
- **THEN** the folder is made and the session starts, as before

### Requirement: A fresh start refused late removes its unused folder

When `runtime.start_session` refuses after `scratch.make` made the repository, LADO SHALL remove what `scratch.make` made (the folder it created, or the `.git` it made in an empty folder) when the folder still holds only `.git` (and `.DS_Store`), its history is the one commit `Start from scratch`, and no session of lado.db has that folder; otherwise it SHALL keep it.

#### Scenario: The name taken in the same second
- **WHEN** a fresh start made `~/workspace/shop` and `start_session` then refuses because another folder's session took the name `shop`
- **THEN** `~/workspace/shop` is gone and the refusal is the start's

#### Scenario: A file written meanwhile
- **WHEN** the start is refused late and the folder now holds a file `notes.md`
- **THEN** the folder and its repository stay

## MODIFIED Requirements

### Requirement: A failed fresh start removes what it made

When a step of `scratch.make` fails, it SHALL remove what
it made (the folder it created, or the `.git` it made in an empty folder) and refuse with
git's first line. A start refused after the repository was made SHALL follow the requirement
"A fresh start refused late removes its unused folder".

#### Scenario: A failed commit
- **WHEN** the commit fails
- **THEN** the folder LADO made is gone, and the refusal carries git's line

### Requirement: lado start --new refuses a folder it cannot start, with a hint

`lado start --new` SHALL refuse with exit
1 and no traceback: a folder `not_empty` with LAD-5's `not_repo` hint (`git init && git
add -A && git commit -m 'First commit'` in that folder), `inside_repo` with the hint `Start
a session in that repository:` `lado start <root>`, `not_folder`, and a git without the
author with its hint. A start refused after the repository was made SHALL print `lado:
removed <folder>, which this start made` when it removed it, else `the repository stays in
<folder>`.

#### Scenario: A folder with files
- **WHEN** `lado start --new ~/Documents/notes` and the folder holds files
- **THEN** it exits 1 with `lado: /Users/ann/Documents/notes is not empty: choose a new or
  empty folder` and LAD-5's hint, and the folder is unchanged

#### Scenario: A start refused after the repository was made
- **WHEN** `lado start --new ~/lado/shop` made the repository and the supervisor's window then failed to open
- **THEN** it exits 1 with the start's refusal and `lado: removed /Users/ann/lado/shop, which this start made`, and `~/lado/shop` does not exist

### Requirement: The server starts a fresh start and its folder check offers one

`POST /api/sessions` SHALL take `where: {kind:
"scratch", path}` and `title`: it checks the new session whole, runs `scratch.make`, then
starts the session as for a folder; a refusal before the repository is made SHALL be 400
(409 for a taken name or a model's refusal) with its text and nothing made.
`FolderInfo.scratch` SHALL be true for a folder whose check fails with `missing` or
`not_repo` and whose fresh-start state is `new` or `empty`, else false.

#### Scenario: An empty folder in the folder check
- **WHEN** `GET /api/folders` checks an empty folder outside git
- **THEN** it answers `ok: false`, `problem_kind: "not_repo"` and `scratch: true`

### Requirement: Create and start goes on only with a fresh start that can

**Create and start** SHALL be on only with a name, a folder `new` or `empty`, an author known
and a name free; while off, the footer SHALL say what is missing (`name the folder`, `tell
git who you are`). It sends `where: {kind: "scratch", path}`, the name and the title. A
refused start SHALL show the refusal and keep Where on New empty folder when the folder is
not a repository after it, else turn Where to that folder.

#### Scenario: No author
- **WHEN** git does not know the author
- **THEN** the window shows the author's text and hint with Copy, Create and start is off,
  and the footer reads `To start: tell git who you are`

#### Scenario: A kit's refusal
- **WHEN** the human presses Create and start with the kit `sdlc` and no tracker kit
- **THEN** Where stays on New empty folder with Folder name as typed, the refusal shows with the Team section open, and no folder was made
