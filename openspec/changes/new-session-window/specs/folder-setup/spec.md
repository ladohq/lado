## Purpose
Setting up a plain folder outside git for a session: a preview of what the first commit takes and leaves out, the commit itself with what is left out written to .gitignore, and the window's one button that sets up and starts.

## ADDED Requirements

### Requirement: The set-up's preview counts what the first commit would take

For a folder of files outside git, LADO SHALL tell, changing nothing on disk, how many files
and bytes `git add -A` would take there, an existing `.gitignore` respected, and which paths
it leaves out with their reason: `secret` (by name), `large` (over 50 MiB) or `repository` (a
folder with its own `.git`).

#### Scenario: A folder of notes
- **WHEN** `~/workspace/notes` holds 128 files of 4.2 MB, a `.env`, `keys.pem`, a 240 MB
  `talk.mp4` and `old-site/` with its own `.git`
- **THEN** the preview gives 128 files, 4.2 MB, and leaves out `.env` and `keys.pem` as
  `secret`, `talk.mp4` as `large` and `old-site/` as `repository`

#### Scenario: A file the folder's .gitignore ignores
- **WHEN** the folder's `.gitignore` names `build/`
- **THEN** nothing under `build/` is counted or listed

### Requirement: A secret is told by its name

A path SHALL be left out as `secret` when its name matches `.env*`, `*.pem`, `*.key`,
`*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `credentials*`, `.npmrc` or `.netrc`, in any
subfolder.

#### Scenario: A key in a subfolder
- **WHEN** the folder holds `deploy/server.key`
- **THEN** the preview leaves it out as `secret`

### Requirement: A home folder or a folder too big is refused

The preview SHALL refuse, before any listing, the home folder, `/`, the workspace itself and
a folder that holds the workspace (`home`), and SHALL stop and refuse past 20,000 files or 2
GiB (`too_big`, with the count so far).

#### Scenario: Too many files
- **WHEN** the folder holds 180,000 files
- **THEN** the preview refuses with `too_big` and the window says `Choose a smaller folder:
  this one holds 180,000 files.`

### Requirement: The set-up makes one commit and leaves out what it was told

Setting a folder up SHALL check git's author first, then `git init`, append the left-out paths
not included to `.gitignore` (made when missing), `git add -A` and make one commit `First
commit` with no signing and no hooks; a `repository` path SHALL never be included.

#### Scenario: A secret left out
- **WHEN** the folder is set up with nothing included
- **THEN** the repository has one commit with the 128 files, `.gitignore` names `.env`,
  `keys.pem`, `talk.mp4` and `old-site/`, and `.env` is still on disk

#### Scenario: A secret ticked in
- **WHEN** the human ticks `.env` and the folder is set up
- **THEN** `.env` is in the commit and not in `.gitignore`

### Requirement: A failed set-up leaves the folder as it was

When a step of the set-up fails, LADO SHALL remove the `.git` it made and put `.gitignore`
back as it was (removed when it made it), and refuse with git's line.

#### Scenario: The commit fails
- **WHEN** git's commit fails during the set-up
- **THEN** the folder has no `.git`, its `.gitignore` is as before, and the start is refused
  with git's line

### Requirement: The server previews and starts a set-up

`GET /api/folders` SHALL give `setup` (files, bytes, left out, refusal, author problem, the
manual command) for a folder of files outside git; `POST /api/sessions` SHALL take `where:
{kind: "setup", path, include}`, set the folder up, then start as for a folder; a start
refused after the set-up SHALL leave the repository made.

#### Scenario: Set up and start
- **WHEN** `POST /api/sessions` gets `where: {kind: "setup", path: "~/workspace/notes",
  include: []}`
- **THEN** the folder becomes a repository of one commit and the session starts there; a
  worker's worktree has the saved files and not `.env`

### Requirement: The window sets up and starts a plain folder with one button

For a folder with `setup`, the window SHALL show under Where `Not yet set up for LADO.
Starting saves <n> files (<size>) as the starting point.`, `<k> left out · Review` with a
tick per path (a `repository` one off), `Do it yourself` with the command rebuilt from the
ticks and Copy, and the button `Set up and start in <folder>`.

#### Scenario: Review and tick
- **WHEN** the human opens Review and ticks `.env`
- **THEN** the line counts 129 files, the row of `.env` says `Will be saved in the history`,
  and the command under Do it yourself no longer names `.env`

#### Scenario: While counting
- **WHEN** the preview has not answered yet
- **THEN** the panel reads `Not yet set up for LADO. Counting files…`, the button is off and
  the footer reads `To start: wait for the count`

### Requirement: Git's missing author keeps the set-up off

When git has no `user.name` or `user.email` where the folder is, the window SHALL show `Git
doesn't know who you are yet. Tell it once for this computer:` with the command, Copy and
Check again (in LADO's container the `.env` text and no Check again), and keep the button off.

#### Scenario: No author
- **WHEN** git has no `user.email` and the human picks a plain folder
- **THEN** the author's text and command show, the footer reads `To start: tell git who you
  are`, and Check again checks the folder anew
