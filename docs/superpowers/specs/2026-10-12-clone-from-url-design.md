# Clone from URL: design

Task: LAD-6. Change: `openspec/changes/clone-from-url/`. Mockup: run artifact
`task/lad-6/mockup-clone.html` (v3).

## Problem

A session starts only in a folder that already holds a repository with a commit. A new
user often has no clone yet, and with `lado ui --host` the human may have no shell on the
server's machine to make one. Root cause: nothing in the core gets a repository from its
address.

## What the user sees after the change

**In the New session window**

1. Where has a switch **Folder | Clone from URL**. Folder works as before.
2. With Clone from URL: the URL (ssh, https, `git@host:path`), **Clone into** (by default
   `~/lado/<repo>`, following the URL until edited) with the folder's state under it, and
   **Branch**: half a second after the URL stops changing the server lists the remote's
   branches (`fetching branches…` meanwhile); the default branch is chosen and marked
   `(default)`. Name, Kits, Provider and Permission mode are the folder's form: kits do
   not depend on the folder (LAD-22), and a fresh clone has no last session.
3. An access failure shows at once under the URL, before any button: git's line, and
   where the human can act a sentence and a command with Copy (`ssh -T git@github.com`,
   `gh auth login`, `gh auth status`). LADO never waits for a password.
4. **Clone and start**: a progress block (phase, percent with a bar, size and speed,
   elapsed time), the fields locked, × and Esc off, only **Cancel clone**, which stops
   git and removes the temporary folder. Then the session starts and its Activity opens.
   If the start is refused (a name taken), the window switches to Folder with the clone,
   which stays, and shows the refusal.
5. The folder is checked before anything is made. A clone of the same repository (same
   host and path, whatever the protocol or `.git`) offers **Use this clone**: the window
   switches to Folder with it, as it is (no clone, no pull, no branch switch). A clone of
   another repository with the same name, a folder with other files or a file is refused,
   naming the other origin and, when free, a folder `~/lado/<owner>-<repo>`.
6. A tab closed or reloaded during a clone: the server cancels the clone within 10 s.

**In the CLI**

```
lado start <git-url> [<folder>] [--branch NAME] [--name ...] [--kit ...] ...
```

Checks the folder and the name first, clones with git's own progress lines, Ctrl-C
cancels (`lado: clone cancelled`, exit 130, nothing left), then starts the session as
`lado start <folder>`. A folder with a clone of the same repository is refused with the
command `lado start <folder>`: LADO does nothing the human did not ask for.

## Architecture

- `src/lado/clone.py`: the core (URL rules, default folder, target check, branch listing,
  clone with progress and cancel, failure kinds and hints). Used by `cli.py` and
  `server/clones.py`; later by projects.
- `src/lado/server/clones.py`: clone jobs in the server's memory, one thread each, polled
  by the window; abandoned jobs cancelled; cancelled at shutdown.
- `web/src/Launch.tsx`: the Clone from URL source; the start after the clone is the
  folder's `POST /api/sessions`.

Options weighed and decisions D1–D14: `openspec/changes/clone-from-url/design.md`.

## Decisions for the record

- Clone jobs live in the server's memory and are polled (D9): no schema change; a
  streaming request could not tell a cancel from a dropped connection.
- No prompts at all, in the CLI too (D4): one behaviour for both, and the task's "only
  what the machine has".
- Failures are classified by git's words under `LC_ALL=C` (D5); an unknown one still
  shows git's line.
- `POST /api/remote-branches` sits under `Guard.changes` because it goes to the network
  with the server's credentials (D10).
- A start refused after the clone keeps the clone (D8, D12): it is a good repository the
  human asked for; deleting it would throw work away.
- The name is checked before the clone (D8, D11), so a taken name does not cost a clone.
