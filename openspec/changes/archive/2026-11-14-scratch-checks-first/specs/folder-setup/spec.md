## MODIFIED Requirements

### Requirement: The server previews and starts a set-up

`GET /api/folders` SHALL give `setup` (files, bytes, the left-out paths each with its line of
the manual command, refusal, author problem, the manual command's rest and the file limit) for
a folder of files outside git; `POST /api/sessions` SHALL take `where: {kind: "setup", path,
include}`, refuse what a new session's start refuses (session-scratch) before any change,
set the folder up, then start as for a folder; a start refused after the set-up SHALL leave the repository made.

#### Scenario: Set up and start
- **WHEN** `POST /api/sessions` gets `where: {kind: "setup", path: "~/workspace/notes",
  include: []}`
- **THEN** the folder becomes a repository of one commit and the session starts there; a
  worker's worktree has the saved files and not `.env`

#### Scenario: A kit's refusal before the set-up
- **WHEN** `POST /api/sessions` gets `where: {kind: "setup", path: "~/workspace/notes", include: []}` with the kit `sdlc` and no kit gives the skill `tracker`
- **THEN** it answers 400 with the kit's refusal, and `~/workspace/notes` has no `.git`
