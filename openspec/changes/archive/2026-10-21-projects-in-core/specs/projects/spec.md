## Purpose

The human's projects: a project is an id, a title and a record in `lado.db`, with its folder
`<workspace>/projects/<id>` derived from the id and made by LADO; `lado project` makes,
lists, shows, renames and deletes them, agents only read them, and `lado doctor` checks
them.

## ADDED Requirements

### Requirement: A project is an id, a title and a record in lado.db

LADO SHALL keep a project as a record of the table `projects` in `lado.db` (schema 32): its
id, its title or none, and when it was made. The id SHALL match `[a-z0-9][a-z0-9-]*` and
be 1 to 40 characters long, and SHALL never change. The title SHALL follow the session
title's rule (`runtime.check_title`): trimmed, none when empty or equal to the id, at most
80 characters, one line of visible text; two projects MAY have the same title. Where a
project has no title, LADO SHALL show its id.

#### Scenario: A project with a title
- **WHEN** the human runs `lado project create shop --title "  Shop  "`
- **THEN** `lado.db` has the project `shop` with the title `Shop`

#### Scenario: A title equal to the id
- **WHEN** the human runs `lado project create acme --title acme`
- **THEN** the project `acme` has no title, and `lado project list` shows `acme` in its
  title's place

### Requirement: A project's folder is derived from its id

A project's folder SHALL be `<workspace>/projects/<id>` (`projects.workspace`), computed
each time and stored nowhere; another folder SHALL NOT be accepted. A project whose folder
does not exist (the workspace changed, or the folder was deleted by hand) SHALL be shown
with `(folder not found)` and SHALL keep its record.

#### Scenario: Another workspace
- **WHEN** the project `shop` was made with `LADO_REPOS=/srv/a` and `lado project list`
  runs with `LADO_REPOS=/srv/b`, where `/srv/b/projects/shop` does not exist
- **THEN** the line of `shop` names `/srv/b/projects/shop  (folder not found)`

### Requirement: lado project create makes the record and the folder

`lado project create <id> [--title TEXT]` SHALL make the record and the folder
`<workspace>/projects/<id>`, making the workspace and `projects/` when they are missing,
and SHALL print `Made project <id> "<title>": <folder>` (without `"<title>"` when there is
none). When the folder cannot be made, the record SHALL NOT stay.

#### Scenario: The first project in a new workspace
- **WHEN** `~/workspace` does not exist, `LADO_REPOS` is unset and the human runs
  `lado project create shop --title Shop`
- **THEN** `~/workspace/projects/shop` exists, the project `shop` is in `lado.db`, and the
  output is `Made project shop "Shop": /Users/ann/workspace/projects/shop`

### Requirement: lado project create refuses with its reason and makes nothing

`lado project create` SHALL refuse, exit 1 with `lado: <reason>`, and make no record and
no folder, when the id breaks the id rule, a project of that id exists,
`<workspace>/projects/<id>` exists, `projects/` is the human's own folder, or the
workspace is not a folder LADO can make or write in (`lado doctor`'s reason).

#### Scenario: A bad id
- **WHEN** the human runs `lado project create Shop`
- **THEN** it exits 1 with `lado: the project id Shop is not valid: lowercase Latin
  letters, digits and -, starting with a letter or digit, at most 40 characters`, and
  nothing is made

#### Scenario: A taken id
- **WHEN** LADO has the project `shop` and the human runs `lado project create shop`
- **THEN** it exits 1 with `lado: project shop exists`

#### Scenario: The folder exists
- **WHEN** `~/workspace/projects/shop` exists with no project `shop` in LADO and the human
  runs `lado project create shop`
- **THEN** it exits 1 with `lado: <folder> already exists: LADO makes a project's folder
  itself; choose another id or move that folder away`, and LADO has no project `shop`

#### Scenario: A workspace that is a file
- **WHEN** `LADO_REPOS=/srv/notes`, a regular file, and the human runs `lado project create
  shop`
- **THEN** it exits 1 with `lado: LADO_REPOS is not a folder: /srv/notes`

### Requirement: projects/ is the human's own folder when no project of LADO is in it

`<workspace>/projects` SHALL be the human's own folder when it exists, holds an entry
whose name does not start with `.`, and none of its entries is the folder of a project in
`lado.db`; then `create` SHALL refuse. Entries whose names start with `.` SHALL NOT
count, and once a project's folder is in `projects/`, another entry SHALL NOT block a new
project.

#### Scenario: The human's own projects folder
- **WHEN** `~/workspace/projects` holds `notes` and `drafts` and LADO has no project
- **THEN** `lado project create shop` exits 1 with `lado: <ws>/projects is your own folder
  (it holds drafts, notes): LADO keeps projects there only; move it away or set
  LADO_REPOS to another workspace`, naming at most three entries

#### Scenario: Only Finder's file
- **WHEN** `~/workspace/projects` holds only `.DS_Store`
- **THEN** `lado project create shop` makes the project

#### Scenario: A foreign folder beside a project
- **WHEN** `~/workspace/projects` holds `shop` (project `shop`) and `old`
- **THEN** `lado project create acme` makes the project, `old` stays as it is, and
  `lado doctor` names `old` as foreign

### Requirement: lado project list and show print projects with their folders

`lado project list` SHALL print one line per project, by id: the id, the title (the id
when none) and the folder, with `  (folder not found)` when the folder does not exist; with
no project it SHALL print `No projects. Make one with: lado project create <id>`.
`lado project show <id>` SHALL print `<id> "<title>"` (the id alone without a title), then
`  folder:  <folder>` (with the same mark) and `  made:    <local date and time>`; an
unknown id SHALL exit 1 with `lado: unknown project "<id>"`.

#### Scenario: Two projects
- **WHEN** LADO has `shop` titled `Shop` with its folder and `acme` without a title whose
  folder is gone
- **THEN** `lado project list` prints `acme  acme  <ws>/projects/acme  (folder not
  found)` and `shop  Shop  <ws>/projects/shop`

### Requirement: lado project rename changes only the title

`lado project rename <id> <title>` SHALL set the title by the title rule (an empty text
clears it) and print `<id>: title "<title>"` or `<id>: no title`; the id, the folder and
everything in it SHALL stay as they are. An unknown id SHALL exit 1.

#### Scenario: Rename
- **WHEN** the human runs `lado project rename shop "Shop EU"`
- **THEN** `lado project show shop` prints `shop "Shop EU"` and the same folder

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL list the unpushed work of the project folder: for each
git repository directly in it, and each worktree of one, its uncommitted changes
(untracked files included) and each local branch with no upstream or ahead of it. Without
`--yes` it SHALL then refuse, exit 1, changing nothing.

#### Scenario: Unpushed work
- **WHEN** the project folder holds the repository `frontend` with an uncommitted file and
  a branch `feature-x` with no upstream, and the human runs `lado project delete shop`
- **THEN** the output has `Unpushed work in <folder>:` and `  frontend: uncommitted
  changes; branch feature-x not pushed`, then `lado: deleting project shop removes its
  folder <folder> with everything in it; run again with --yes`; it exits 1, and the
  folder and the record stay

#### Scenario: A repository git cannot read
- **WHEN** a subfolder `broken` has a `.git` git cannot read
- **THEN** the list has `  broken: could not check: <git's first line>`

#### Scenario: Nothing unpushed
- **WHEN** every repository of the folder is pushed and clean
- **THEN** no list is printed, and without `--yes` the command still refuses

### Requirement: lado project delete --yes removes the folder, then the record

`lado project delete <id> --yes` SHALL remove the project folder whole, then the record,
and print `Deleted project <id>`. A project whose folder is not found SHALL lose its record
only. When the folder cannot be removed whole, the record SHALL stay and the command SHALL
exit 1 naming what stayed.

#### Scenario: Confirmed
- **WHEN** the human runs `lado project delete shop --yes`
- **THEN** `<ws>/projects/shop` and the record are gone, and `<ws>/projects` and the rest
  of the workspace are as they were

#### Scenario: The folder already gone
- **WHEN** the folder of `acme` is not found and the human runs `lado project delete acme
  --yes`
- **THEN** the record is gone and no folder is touched

### Requirement: lado project delete removes nothing outside the project folder

`lado project delete` SHALL remove only `<workspace>/projects/<id>`, whose real path
SHALL be a direct child of the real path of `<workspace>/projects`, or else refuse. When
`<workspace>/projects/<id>` is a symbolic link, it SHALL remove the link and never its
target.

#### Scenario: A link to a folder elsewhere
- **WHEN** `<ws>/projects/shop` is a symbolic link to `/srv/shop` and the human runs
  `lado project delete shop --yes`
- **THEN** the link is gone, `/srv/shop` and its files stay, and the record is gone

### Requirement: Agents cannot change projects

`lado project create`, `rename` and `delete` SHALL refuse, exit 1 with `lado: lado project
<command> is for the human; agent "<agent>" cannot use it` and change nothing, when
`LADO_AGENT` is set (every agent of LADO has it). `list` and `show` SHALL work for agents.
LADO SHALL offer no MCP tool that makes, changes or deletes a project.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

### Requirement: lado doctor checks projects

Once LADO has a project or `<workspace>/projects` exists, `lado doctor` SHALL print one
check `Projects`: `ok` with `<n> in <workspace>/projects` when nothing is wrong, else
`warn` with each finding joined by `; ` (a project whose folder is not found, foreign
folders, `projects/` that is the human's own). With no project and no `projects/` it SHALL
print no such line.

#### Scenario: All well
- **WHEN** LADO has `shop` and `acme`, both with their folders
- **THEN** `lado doctor` prints `[ok  ] Projects: 2 in <ws>/projects`

#### Scenario: A foreign folder and a missing one
- **WHEN** LADO has `shop` (folder there) and `acme` (folder gone), and `projects/` also
  holds `old`
- **THEN** `lado doctor` prints `[warn] Projects: acme: folder not found <ws>/projects/acme;
  foreign folder in projects/: old`

#### Scenario: The human's own folder
- **WHEN** LADO has no project and `<ws>/projects` holds `notes`
- **THEN** `lado doctor` prints `[warn] Projects: <ws>/projects is your own folder (it holds
  notes): LADO cannot make projects there`

#### Scenario: Nothing yet
- **WHEN** LADO has no project and `<ws>/projects` does not exist
- **THEN** `lado doctor` prints no Projects line

