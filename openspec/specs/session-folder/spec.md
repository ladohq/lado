# session-folder Specification

## Purpose
Whether a folder can hold a LADO session, and when it cannot, what it lacks and what the
human can do about it: the one folder check behind `lado start` and the UI's New session
window, and how LADO's own git calls behave when git cannot run.

## Requirements

### Requirement: The folder check names what a folder lacks

LADO SHALL check a folder for a session (`runtime.check_repo`, asked by `lado start` and
the UI's folder check alike) in this order and refuse with the first case that holds,
each with its own kind and text:

| Kind | Text |
|---|---|
| `missing` | `<path> does not exist` |
| `not_folder` | `<path> is a file, not a folder` |
| `no_git` | `git is not installed or not on PATH (<PATH of LADO's process>)` |
| `git_broken` | `git does not run: <the first line git printed>` |

#### Scenario: A folder that does not exist
- **WHEN** the path does not exist
- **THEN** the check refuses with kind `missing` and `<path> does not exist`

#### Scenario: A file instead of a folder
- **WHEN** the path is a file
- **THEN** the check refuses with kind `not_folder` and `<path> is a file, not a folder`

#### Scenario: git is not installed
- **WHEN** no `git` is found on the PATH of LADO's process
- **THEN** the check refuses with kind `no_git`, naming that PATH, and no exception other
  than LADO's own error leaves the core

#### Scenario: git is on PATH but does not run
- **WHEN** `git --version` fails (the macOS stub without the command line tools)
- **THEN** the check refuses with kind `git_broken` and git's first line, not with
  `not_repo`

### Requirement: The folder check then names what git says of the folder

After the cases of a missing folder and a missing or broken git, the folder check SHALL
go on in this order and refuse with the first case that holds, each with its own kind
and text:

| Kind | Text |
|---|---|
| `not_repo` | `<path> is not inside a git repository` |
| `git_refused` | `git cannot read <path>: <the first line git printed>` |
| `no_commits` | `<path> has no commits yet` |

`not_repo` SHALL be only git's own "not a git repository" answer; any other failure of
git in the folder SHALL be `git_refused` with git's words.

#### Scenario: A folder outside any repository
- **WHEN** git answers that the folder is not a git repository
- **THEN** the check refuses with kind `not_repo`

#### Scenario: git refuses to read the folder
- **WHEN** git fails in the folder for another reason (e.g. "detected dubious ownership")
- **THEN** the check refuses with kind `git_refused` and git's first line

#### Scenario: A repository without commits
- **WHEN** the folder is in a repository whose HEAD has no commit
- **THEN** the check refuses with kind `no_commits` and `<path> has no commits yet`

### Requirement: A refusal the human can fix carries a hint

A refusal of kind `no_git`, `git_broken`, `not_repo` or `no_commits` SHALL carry a hint:
one sentence and one command to copy, the same in the CLI and the UI. Other kinds SHALL
carry none.

#### Scenario: lado start prints the hint
- **WHEN** `lado start` is refused with a kind that has a hint
- **THEN** it exits 1 printing `lado: <text>` and on the next line `lado: <sentence>
  <command>`, and no traceback

#### Scenario: No hint where git said it
- **WHEN** the refusal is `git_refused`
- **THEN** it carries no hint: git's own line says what to do

### Requirement: Each hint gives the command that fixes its kind

`no_git` SHALL name
this OS's install command (macOS: `xcode-select --install`; Linux and WSL:
`sudo apt install git`, the sentence naming the distribution's package manager as the
other way); `git_broken` on macOS `xcode-select --install`, on Linux and WSL
`sudo apt install --reinstall git`; `not_repo`
`git init && git add -A && git commit -m 'First commit'`; `no_commits`
`git add -A && git commit -m 'First commit'`, both "in that folder".

#### Scenario: A folder outside git on Linux
- **WHEN** the check refuses a folder with `not_repo` on Linux
- **THEN** its hint's command is `git init && git add -A && git commit -m 'First commit'`,
  to run in that folder

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
  "✓ git repository · branch X" as before

### Requirement: The New session window shows the folder check's hint

The New session window SHALL show the folder check's text under the Where field and,
with a hint, its sentence and its command in a code field with a Copy button, and keep
Start off; for a folder with `FolderInfo.scratch` it SHALL show Start from scratch here
in place of the command (capability session-scratch).

#### Scenario: No git on the server's machine
- **WHEN** the server's process finds no git and the window checks a folder
- **THEN** the answer is 200 with `problem_kind: "no_git"` and the install hint, and the
  window shows the command with a Copy button

#### Scenario: An empty folder offers a fresh start instead of the command
- **WHEN** the window checks an empty folder outside git
- **THEN** the answer keeps `problem_kind: "not_repo"` and its hint, and the window shows
  Start from scratch here instead of the `git init` command

### Requirement: LADO's git calls never crash for a missing git

Every place LADO runs git itself SHALL turn "git cannot be run" into its usual error
with the `no_git` text: `runtime.git` (a `LadoError`), `gitcache._git` (a `GitError`, so
`lado kits add`, `update`, `outdated` and the Kits page refuse with it). `providers/gitpaths`
SHALL read it as "outside git", as it reads any git failure.

#### Scenario: Installing a kit without git
- **WHEN** `lado kits add <url>` runs with no git on PATH
- **THEN** it exits 1 with `lado: git is not installed or not on PATH (...)`, no traceback
