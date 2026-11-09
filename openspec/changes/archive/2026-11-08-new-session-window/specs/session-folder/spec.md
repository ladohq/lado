## MODIFIED Requirements

### Requirement: The UI's folder check gives the kind and the hint

`GET /api/folders` SHALL answer 200 for every case of the folder check with `ok: false`,
`problem` (the text), `problem_kind` and `hint` (`{text, command}` or null), and
`problem_kind: null`, `hint: null` for a folder that will do. `FolderInfo.has_commits`
SHALL be removed.

#### Scenario: Starting with no git is a refusal, not a server error
- **WHEN** `POST /api/sessions` is sent while the server finds no git
- **THEN** it answers 400 with the `no_git` text, never 500

#### Scenario: A folder that will do
- **WHEN** the folder is a repository with a commit
- **THEN** `ok` is true, `problem_kind` and `hint` are null, and the window shows
  `✓ Ready · branch X` under Where

### Requirement: The New session window shows the folder check's hint

The New session window SHALL show the folder check's text under Where and, with a hint, its
sentence and its command in a code field with Copy, and keep the start button off; a folder
with `FolderInfo.scratch` SHALL show Start from scratch here instead of the command, and a
folder with `FolderInfo.setup` the set-up panel (capability folder-setup).

#### Scenario: No git on the server's machine
- **WHEN** the server's process finds no git and the window checks a folder
- **THEN** the answer is 200 with `problem_kind: "no_git"` and the install hint, and the
  window shows the command with a Copy button

#### Scenario: An empty folder offers a fresh start instead of the command
- **WHEN** the window checks an empty folder outside git
- **THEN** the answer keeps `problem_kind: "not_repo"` and its hint, and the window shows
  Start from scratch here instead of the `git init` command

#### Scenario: A folder of files outside git offers the set-up
- **WHEN** the window checks a folder of files outside git
- **THEN** the answer keeps `problem_kind: "not_repo"` and its hint, has `setup`, and the
  window shows the set-up panel with `Set up and start in <folder>`, the command only under
  Do it yourself
