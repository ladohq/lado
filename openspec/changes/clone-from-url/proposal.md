Task: LAD-6

## Why

A session starts only in a folder that already holds a git repository with a commit
(`runtime.check_repo`, LAD-5). A new user often has no clone yet, and with the UI open to
the network (`lado ui --host`) the human cannot make one from the browser at all: the
folder must exist on the server's machine, where they may have no shell.

The root cause is one: LADO's only way into a repository is a folder that exists; nothing
in the core gets a repository from its address. The coming projects (ROADMAP, Later:
"LADO itself makes … clones") need the same step, so it belongs to the core, not to the
UI.

## What Changes

- A core module, `lado.clone`, gets a repository from a git URL: it tells a URL from a
  folder, names the default folder (`~/lado/<repo>`), lists the remote's branches with
  its default one, checks the target folder, clones one branch with progress and
  cancellation into a temporary folder that becomes the target only when the clone is
  complete, and turns git's failures into LADO's texts with a hint where the human can act
  (LAD-5's sentence and one command). It uses only the access git already has on the
  machine (ssh keys, `gh auth`, a credential helper) and never asks for or keeps a
  password or token.
- LADO never touches a folder that exists and is not empty: no clone over it, no fetch or
  pull, no branch switch. A folder that already holds a clone of the same repository is
  named as such; the human starts a session in it explicitly.
- **CLI**: `lado start <git-url> [<folder>] [--branch NAME]` clones into the folder (by
  default `~/lado/<repo>`), with git's own progress lines, Ctrl-C cancelling and removing
  the temporary folder, then starts the session as `lado start <folder>` does. A folder
  that holds a clone of that repository is refused with the command
  `lado start <folder>` that starts a session in it as it is.
- **UI**: the New session window's Where field gets a switch, **Folder | Clone from URL**.
  With a URL the window lists the remote's branches by itself (the default one chosen
  and marked), checks the target folder, and its one button **Clone and start** clones
  with a progress bar and **Cancel clone**, then starts the session; the rest of the form
  is the folder's. While a clone runs the window cannot be closed; a clone whose window
  went away (tab closed or reloaded) is cancelled by the server. A folder holding a clone
  of the same repository offers **Use this clone**, which switches the window to Folder
  with that folder (mockup `mockup-clone.html`, v3).
- **API**: `POST /api/remote-branches` (the branches), `GET /api/clone-target` (the target folder),
  `POST /api/clones`, `GET /api/clones/{id}`, `DELETE /api/clones/{id}` (a clone job).
- New minor release: the feature goes into the unreleased 0.36.0. No schema migration,
  no MCP tool change.

## Scope

- The core clone module, shared by the CLI and the server.
- `lado start <git-url> [<folder>] [--branch NAME]`.
- The New session window's Clone from URL source, the five endpoints behind it.
- Docs: `docs/design/ui.md` (Launch and session control), AGENTS.md (Layout, the CLI
  sections), README's start (one line), CHANGELOG.md.

## Out of scope

- Tags and commits as the clone's ref: a session works on a branch, and a tag would need
  one made from it. The human's decision (branches only).
- Submodules (`--recurse-submodules`) and shallow clones: a worker needs the history, and
  no kit relies on submodules yet ("Only what is used").
- A clone that goes on in the background after its window is gone, and a start without
  the window: the human's decision (point 1): the window waits for its clone, and its
  failure is shown there.
- Setting up access or keeping tokens: LADO uses what the machine has (the task).
- Updating, fetching or switching the branch of an existing clone: LADO never changes a
  folder it did not make (the human's decision, point 3).
- Pull requests on services other than GitHub: not this task (the task).
- A local path or a bare repository on disk as the source: a folder is the Folder source;
  `file://` URLs are accepted (tests use them) but not offered.
- Remembering recent URLs: the recent folders already show a clone's folder after its
  first session.

## Acceptance criteria

- AC-1: `lado start <git-url>` clones the remote's default branch into `~/lado/<repo>`,
  showing git's progress, and starts a session there; `lado start <git-url> <folder>
  --branch dev` clones branch `dev` into `<folder>`.
- AC-2: Ctrl-C during `lado start <git-url>` stops git, removes the temporary folder,
  leaves no target folder and exits 130.
- AC-3: With a folder that already holds a clone of the same repository (same host and
  path; ssh or https, `.git` or not), `lado start <git-url>` changes nothing, exits 1 and
  prints the command `lado start <folder>`; the window shows "already a clone of this
  repository … on branch X; LADO will use it as it is" and **Use this clone**.
- AC-4: A folder that holds a clone of another repository, or is not empty, or is a file,
  is refused before any clone, in the CLI and the window alike, naming the other origin
  when there is one; the folder is not changed.
- AC-5: With a URL typed in the window, the Branch field lists the remote's branches by
  itself, the default branch chosen and marked `(default)`; Clone and start stays off
  until the list is there.
- AC-6: An access failure (an ssh key refused, an unknown host key, https needing a login,
  a repository not found, no network) shows git's line and, where the human can act, a
  hint with a command and Copy, under the URL before the button is pressed, and as the
  same text in the CLI; LADO never waits for a password.
- AC-7: Cancel clone stops git and removes the temporary folder; the target folder is not
  made. While the clone runs the window's ×, Esc and Cancel do not close it. A tab closed
  or reloaded during the clone cancels it at once (a beacon); a clone whose window stopped
  asking for it otherwise is cancelled by the server within `clone.ABANDONED` seconds
  (150), the same way.
- AC-8: After the clone the session starts; when the start is refused (e.g. a name
  taken), the clone stays, the window switches to Folder with it and shows the refusal.
