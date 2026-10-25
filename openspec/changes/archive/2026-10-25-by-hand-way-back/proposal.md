Task: LAD-144

## Why

Symptom: when LADO was not installed from an index with `uv tool` or `pipx`
(`update.installer()` is None: a venv's pip, a local wheel, a folder, git), `lado update X`
prints its plan and then the commands to run by hand. For an update to an older schema
(0.43.0 → 0.42.0) the plan warns that `lado.db` goes back to
`backups/lado.db.schema-<S>`, but the list of commands:

- has no step that puts that copy back, so the older LADO, run as the list says, meets
  `lado.db` at the newer schema and refuses it;
- starts again the sessions the copy lacks, which the warning just said are not started;
- names `<prefix>/bin/pip install lado==X` for an environment of `uv tool` or `pipx`,
  where there is no `pip`.

No data is lost (`lado update` back to the newer version brings everything back), and
docs/install.md's way by hand is right. Found by the lead's check of LAD-143 on a real
0.42.0, 2026-10-25.

Cause: `Plan.by_hand` (`src/lado/self_update.py:167-174`) predates the way back to an
older schema (the copy, `Plan.restore`) and never reads it; and it takes the installer for
granted as the prefix's `pip`, while `installer()` returns None also for a `uv tool` or
`pipx` environment of lado from a wheel, a folder or git.

Options weighed:

- A (taken): `by_hand` follows the automatic path: with `restore` it adds, after the
  installer, the one command that puts the copy back (absolute paths of the real
  `LADO_HOME`), and starts only the sessions the copy has; it names the installer of the
  prefix it finds (`pip` there, else `uv tool`, else `pipx`), and when it finds none says
  so in a comment line. A few lines in one function and unit tests; the list stays the
  same in the CLI and the UI's System panel (one source).
- B: print no commands for a way back to an older schema, only a pointer to
  docs/install.md. Less code, but the human copies paths and the schema by hand, and the
  plan already knows both; the docs then are the second place that must stay right.
- C: make `installer()` recognise `uv tool`/`pipx` from a wheel or folder and update them
  automatically. It would replace the human's own wheel with PyPI's without being asked
  (why `installer()` refuses them); far larger, and not a fix for the RC.

## What Changes

- The commands by hand of an update whose plan warns about `lado.db` (`Plan.restore`) put
  the migration's copy back after the installer:
  `rm -f <home>/lado.db-wal <home>/lado.db-shm && cp <copy> <home>/lado.db`, paths
  absolute and shell-quoted.
- They start again only the planned sessions the copy has; the sessions it lacks are still
  stopped.
- The install line names an installer that is there: `<prefix>/bin/pip install lado==X`
  when that `pip` exists; else `uv tool install lado==X` when the prefix holds
  `uv-receipt.toml`; else `pipx install --force lado==X` when it holds
  `pipx_metadata.json`; else the comment line
  `# install lado==X with the installer of <prefix>: LADO does not know it`.
- The uv and pipx lines name the install's folders, so neither puts a second lado
  elsewhere: `UV_TOOL_DIR` (the prefix's parent) and `UV_TOOL_BIN_DIR` (from the
  receipt's install-path, when it names one), or `PIPX_HOME` (for `<home>/venvs/<name>`).
- docs/install.md ("Installed otherwise") and docs/design/modules.md (`self_update.py`)
  say so; CHANGELOG.md's 0.43.0 gets a line under Fixed.

## Scope

- `Plan.by_hand` and its tests; the CLI's `print_by_hand` and the API's `by_hand` take it
  unchanged.

## Out of scope

- Recognising a `uv tool`/`pipx` install from a wheel, folder or git as one `lado update`
  can upgrade (option C): it would silently swap the human's own build for PyPI's.
- The install line's extras and options of the receipt (`--with`, `--python`): the
  install is not from an index, so LADO cannot say which of them still apply; the plain
  command is what the human edits if needed.
- The UI's System panel: it only offers newer versions, so it never shows the restore
  step; its list changes only in the install line, with no change to its code.
- The automatic path: it already restores the copy and leaves the missing sessions out.

## Impact

- Code: `src/lado/self_update.py` (`Plan.by_hand`).
- Tests: `tests/test_update.py`, `tests/test_server_system.py` (unit).
- Docs: `docs/install.md`, `docs/design/modules.md`, `CHANGELOG.md`.
- Version: a fix in the 0.43.0 release candidate (0.43.0rc2); no new minor, no schema
  change, no API field.
