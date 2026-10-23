# session-scratch Specification

## Purpose
Starting a session from scratch, with no repository yet: from a name the human types, LADO
derives the folder, the session's name and its title, checks that the folder is new or
empty outside any git repository and that git knows the commits' author, makes the folder
a repository with an empty first commit, and starts the session there, from
`lado start --new`, the server's API and the New session window's From scratch.

## Requirements

### Requirement: A typed name gives the folder, the session and the title

LADO SHALL derive, from a name the human types for a fresh start (one rule,
`scratch.names`), the folder's and the session's name and the session's title. The title SHALL be the trimmed text, and none when it equals the name (the rule
of `runtime.set_title`).

#### Scenario: A name that is already a name
- **WHEN** the human types `coffee-site`
- **THEN** the name is `coffee-site` and there is no title

### Requirement: A typed name is refused when empty, long or with a hidden character

The text of a fresh start's name
SHALL be trimmed; it SHALL be refused when it is then empty (`type a name`), longer than
`runtime.MAX_TITLE` (80) characters (`a name is at most 80 characters`), or holds a hidden
character (capability visible-text: `a name is one line of visible text: <the
character> is not allowed`).

#### Scenario: Only spaces
- **WHEN** the human types `   ` as the name
- **THEN** it is refused with `type a name`

### Requirement: The name is the slug of the text in Latin letters

The name SHALL be `runtime.slug` of the text after Cyrillic
letters are transliterated by one table (а a, б b, в v, г g, ґ g, д d, е e, ё e, є ie,
ж zh, з z, и i, і i, ї i, й i, к k, л l, м m, н n, о o, п p, р r, с s, т t, у u, ф f,
х kh, ц ts, ч ch, ш sh, щ shch, ъ —, ы y, ь —, э e, ю iu, я ia; capitals alike) and Latin
letters lose their diacritics (NFKD).

#### Scenario: A Cyrillic name
- **WHEN** the human types `Сайт кофейни`
- **THEN** the name is `sait-kofeini` and the title is `Сайт кофейни`

#### Scenario: A name with accents
- **WHEN** the human types `Café Noël`
- **THEN** the name is `cafe-noel` and the title is `Café Noël`

### Requirement: A name with no Latin letter or digit is refused

A text whose name would be empty (no Latin letter or
digit left) SHALL be refused with `the name needs a Latin letter or digit for its folder:
type one`.

#### Scenario: Another script
- **WHEN** the human types `東京`
- **THEN** it is refused with `the name needs a Latin letter or digit for its folder: type
  one`

### Requirement: The folder of a fresh start is checked before anything is made

LADO SHALL check a folder for a fresh start (`scratch.check_target`) and give one of these
states; only `new` and `empty` SHALL let a fresh start go on, and LADO SHALL change nothing
in a folder of another state:

| State | When | Text |
|---|---|---|
| `new` | the path does not exist, and its nearest existing folder is in no git repository | `a new folder` |
| `empty` | a folder with nothing in it but `.DS_Store`, in no git repository | `an empty folder` |

#### Scenario: A folder Finder made
- **WHEN** the folder holds only `.DS_Store`
- **THEN** its state is `empty`

### Requirement: A folder in a repository, with files, or a file is no fresh start's folder

The check of a fresh start's folder SHALL also give these states, each of which lets no
fresh start go on:

| State | When | Text |
|---|---|---|
| `inside_repo` | the path, or its nearest existing folder, is in a git repository | `<path> is inside the git repository <root>: choose a folder outside it` |
| `not_empty` | a folder with anything else in it | `<path> is not empty: choose a new or empty folder` |
| `not_folder` | a file | `<path> is a file, not a folder` |

#### Scenario: A folder of a repository
- **WHEN** the path is `/Users/ann/lado/app/site`, and `/Users/ann/lado/app` is a git
  repository
- **THEN** its state is `inside_repo`, naming `/Users/ann/lado/app`

### Requirement: A fresh start's default folder is in the workspace

The default folder of a fresh start SHALL be `<workspace>/<name>`, the workspace being the
clone's (`projects.workspace`: `LADO_REPOS`, else `~/workspace`), made when missing. A
given folder SHALL be a full path (`~` allowed).

#### Scenario: The default folder in the container
- **WHEN** `LADO_REPOS=/Users/ann/projects` and the human types the name `Сайт кофейни`
- **THEN** the folder is `/Users/ann/projects/sait-kofeini`, state `new`

#### Scenario: The default folder without LADO_REPOS
- **WHEN** `LADO_REPOS` is unset, `~/workspace` does not exist and the human types the
  name `shop`
- **THEN** the folder is `~/workspace/shop` (expanded), state `new`, and Create and start
  makes `~/workspace` with it

### Requirement: A fresh start needs git to know the commits' author

Before it makes anything, a fresh start SHALL check that git, in the target's nearest
existing folder, has both `user.name` and `user.email` (`git config --get`), and SHALL
refuse otherwise with the text `git doesn't know who signs the agents' commits: it has no
user.name or user.email`. LADO SHALL NOT set an author of its own.

#### Scenario: A developer's machine
- **WHEN** git's global config has `user.name` and `user.email`
- **THEN** the check passes, and the first commit is theirs

### Requirement: The author's refusal says how to set the author where LADO runs

The refusal of a fresh start for a missing author SHALL carry a hint: in LADO's container (`LADO_CONTAINER`) `Set
LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to compose.yaml, then restart LADO
there:` with the command `docker compose up -d`; elsewhere `Tell git who you are, once for
this computer:` with the command `git config --global user.name "Your Name" && git config
--global user.email you@example.com`.

#### Scenario: The container without the variables
- **WHEN** LADO runs in its container whose `.env` has no `LADO_GIT_NAME`
- **THEN** a fresh start is refused with the text and the `.env` hint, and nothing is made

### Requirement: A fresh start makes a repository with an empty first commit

For a folder of state `new` or `empty` and a git that knows the author, LADO
(`scratch.make`) SHALL make the folder (and the folders above it) when it is new, make it
a git repository whose branch is git's `init.defaultBranch` when set, else `main`, and
make one empty commit, `Start from scratch`, adding none of the folder's files, with no
signing, no hooks and no prompt. It SHALL check the target, the author and the session's
name (as `runtime.check_name`) again right before.

#### Scenario: A new folder
- **WHEN** a fresh start makes `/Users/ann/lado/sait-kofeini`
- **THEN** the folder holds only `.git`, `git log` shows one commit `Start from scratch` on
  `main`, and `git status` is clean

### Requirement: A failed fresh start removes what it made

When a step of `scratch.make` fails, it SHALL remove what
it made (the folder it created, or the `.git` it made in an empty folder) and refuse with
git's first line. A start refused after the repository was made SHALL keep it.

#### Scenario: A failed commit
- **WHEN** the commit fails
- **THEN** the folder LADO made is gone, and the refusal carries git's line

### Requirement: A new session can start with a title

`runtime.start_session` SHALL take `title` for a new session, checked by the rule of
`runtime.set_title` before anything starts, and stored with the session; a resume SHALL
refuse a `title`.

#### Scenario: A fresh start's title
- **WHEN** the session `sait-kofeini` starts with the title `Сайт кофейни`
- **THEN** its title is `Сайт кофейни` in the session list and its head

### Requirement: lado start --new makes the folder a repository first

`lado start --new [<folder>]` SHALL run the fresh start's checks and `scratch.make` on the
folder (default: the current one), then start the session as `lado start <folder>` does,
named by `--name` or the folder's name (`runtime.slug`), and print `Made <folder> a git
repository with an empty first commit` before the start's lines. `--new` with a git URL SHALL be a usage error (exit 2).
Without `--new`, `lado start` SHALL behave as before.

#### Scenario: A new folder from the terminal
- **WHEN** `lado start --new ~/lado/shop --no-attach` runs on a machine whose git knows the
  author
- **THEN** `~/lado/shop` is a repository with one empty commit, and the session `shop`
  runs there

### Requirement: lado start --new refuses a folder it cannot start, with a hint

`lado start --new` SHALL refuse with exit
1 and no traceback: a folder `not_empty` with LAD-5's `not_repo` hint (`git init && git
add -A && git commit -m 'First commit'` in that folder), `inside_repo` with the hint `Start
a session in that repository:` `lado start <root>`, `not_folder`, and a git without the
author with its hint. A start
refused after the repository was made SHALL print `the repository stays in <folder>`.

#### Scenario: A folder with files
- **WHEN** `lado start --new ~/Documents/notes` and the folder holds files
- **THEN** it exits 1 with `lado: /Users/ann/Documents/notes is not empty: choose a new or
  empty folder` and LAD-5's hint, and the folder is unchanged

### Requirement: The server checks and starts a fresh start

`GET /api/scratch-target?text=<name>[&path=<folder>]` SHALL answer 200 with `path` (the
folder given, else the default one), `name`, `title`, `problem` (the name's refusal, or
null), `state` and `text` (the folder's), `author` (`{text, hint}` when git does not know
the author, else null), `name_state` (as `FolderInfo`'s), `provider` (as `CloneTarget`'s)
and `warning` (as `FolderInfo`'s, `runtime.outside_workspace`). With a name refused and no
folder given, `path` SHALL be null.

#### Scenario: A name checked
- **WHEN** the window asks `GET /api/scratch-target?text=Сайт кофейни` with no
  `LADO_REPOS`
- **THEN** the answer has `path` `~/workspace/sait-kofeini` (expanded), `name`
  `sait-kofeini`, `title` `Сайт кофейни`, `state` `new`

### Requirement: The server starts a fresh start and its folder check offers one

`POST /api/sessions` SHALL take `where: {kind:
"scratch", path}` and `title`: it runs `scratch.make`, then starts the session as for a
folder; a refusal before the repository is made SHALL be 400 with its text and nothing
made. `FolderInfo.scratch` SHALL be true for a folder whose check fails with `missing` or
`not_repo` and whose fresh-start state is `new` or `empty`, else false.

#### Scenario: An empty folder in the folder check
- **WHEN** `GET /api/folders` checks an empty folder outside git
- **THEN** it answers `ok: false`, `problem_kind: "not_repo"` and `scratch: true`

### Requirement: The New session window starts from scratch

The New session window SHALL have the source **From scratch** first in its switch, before
Folder and Clone from URL. It SHALL open in From scratch when the recent folders
(`/api/folders/recent`) are empty, and in Folder otherwise; the human's own pick SHALL be
kept. Resume SHALL have no switch, as before.

#### Scenario: A developer's window
- **WHEN** a human with past sessions opens New session
- **THEN** Folder is chosen, as before this change

### Requirement: From scratch shows the name, the folder and the author

From scratch SHALL show **Name** (a text field) with the note `folder and session:
<name>` and, with a title, ` · title: <title>`, or the name's refusal; **Create in**, the
default folder until the human edits it, with its state (`✓ a new folder`, `✓ an empty
folder`, or the refusal); the author's refusal with its hint and Copy; then Kits,
Provider, Permission mode, the first message and Advanced as for a folder, and no separate
session Name field.

#### Scenario: The first window
- **WHEN** a human with no sessions opens New session
- **THEN** From scratch is chosen, and typing `Сайт кофейни` shows `folder and session:
  sait-kofeini · title: Сайт кофейни` and `✓ a new folder`

### Requirement: Create and start goes on only with a fresh start that can

**Create and start** SHALL be on only with a name, a folder `new` or
`empty`, an author known and a name free. It sends `where: {kind: "scratch", path}`, the
name and the title. A start refused after the repository was made SHALL switch the window
to Folder with that folder and show the refusal there.

#### Scenario: No author
- **WHEN** git does not know the author
- **THEN** the window shows the author's text and hint with Copy, and Create and start is
  off

### Requirement: In Folder an empty folder offers Start from scratch here

In Folder, a folder with
`FolderInfo.scratch` SHALL show `The folder is empty: LADO can start it from scratch.`
(for `missing`: `LADO can make this folder and start it from scratch.`) and the button
**Start from scratch here**, which switches to From scratch with that folder in Create in
and its last segment in Name.

#### Scenario: Start from scratch here
- **WHEN** in Folder the human picks an empty folder `/Users/ann/Documents/coffee-site`
- **THEN** the window shows Start from scratch here, and pressing it shows From scratch
  with Name `coffee-site`, Create in that folder and `✓ an empty folder`

### Requirement: A folder inside LADO's projects/ is no fresh start's folder

The check of a fresh start's folder SHALL also give this state, which lets no fresh start
go on, checked before the others:

| State | When | Text |
|---|---|---|
| `in_project` | the folder, by its real path, is inside LADO's `<workspace>/projects` (capability `projects`) | the refusal of a new session there, with its hint |

#### Scenario: A fresh start in a project's folder
- **WHEN** the human runs `lado start --new ~/workspace/projects/shop/site`, `shop` is a
  project and `site` does not exist
- **THEN** it exits 1 with the refusal naming the project and `lado: Add a repository to
  the project: lado project repo add shop --new site`, and no folder `site` is made
