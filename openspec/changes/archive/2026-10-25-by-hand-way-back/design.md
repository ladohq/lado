## Context

`Plan.by_hand` (`src/lado/self_update.py`) is the list of commands that `lado update`
prints (`print_by_hand`) and the API returns as `by_hand` (the UI's System panel) when
`update.installer()` knows no installer of LADO's prefix. It was written before the way
back to an older schema (`Plan.restore`, LAD-143) and takes the installer to be the
prefix's `pip`.

## Decisions

### D1. The install line by what the prefix holds

`<prefix>/bin/pip` when that file exists; else `uv tool install lado==X` for
`uv-receipt.toml`; else `pipx install --force lado==X` for `pipx_metadata.json`; else a
comment line `# install lado==X with the installer of <prefix>: LADO does not know it`.
The checks are of files only, as `update.installer()` does; pip first, since a venv
made by hand may also hold another tool's file. The `uv tool` and `pipx` commands are
those of `update._uv_tool` and `update._pipx` without the receipt's options: the install
is not from an index, so which options still apply is the human's to say. A comment line
keeps the list safe to paste into a shell whole. Paths are quoted with `shlex.quote`.

The uv and pipx lines name the folders of the install (checked by hand with uv 0.13.1
and pipx 1.18.4, a stub package installed in folders of its own):

- `UV_TOOL_DIR=<the prefix's parent>`: without it uv installs a second lado into its
  default tool folder. It is there always, not only when the folder differs from uv's
  default, so LADO keeps no copy of uv's rule for that default.
- `UV_TOOL_BIN_DIR=<the folder of the receipt's install-path of lado>`: without it uv
  moves the executable to its default bin folder, and the one on the human's PATH is
  gone. A receipt that cannot be read or names no install-path gives no
  `UV_TOOL_BIN_DIR` (`update.uv_bin_dir`), never a guess.
- `PIPX_HOME=<home>` when the prefix is `<home>/venvs/<name>`: without it pipx installs a
  second lado into its default home. Any other prefix gives none. No `PIPX_BIN_DIR`:
  pipx's executable is a link into the venv, so the human's old link runs the new
  version, and `pipx_metadata.json` does not record the link's folder.

Over an installed lado of another version, from a wheel or an index, `uv tool install
lado==X` reinstalls without `--force`; it answers "already installed" only for the same
version, which `lado update` never asks for. The automatic path (`update._uv_tool`,
`update._pipx`) passes none of these folders either; that is out of this change
(BACKLOG.md, P2).

### D2. The restore command after the installer

`rm -f <home>/lado.db-wal <home>/lado.db-shm && cp <copy> <home>/lado.db`, `<home>` =
`state.home()`, `<copy>` = `restore.copy`, both made absolute (`Path.absolute()`, for a
relative `LADO_HOME`) and quoted. After the install
line, as docs/install.md and the automatic path (`_Update`) do: until then no LADO runs
on the database, and a failed install leaves the newer LADO with its own database. One
line with `&&`, so a failed `rm` leaves `lado.db` alone. `cp`, not SQLite's backup API
(the automatic path's `restore`): the human runs it with every LADO stopped, and the
removed `-wal`/`-shm` cannot be replayed onto the copy.

### D3. Sessions the copy lacks: stopped, not started

`lado stop` stays for every planned session (they run on the database being replaced);
`lado start` only for those not in `restore.missing`, as the warning above the list says
and as the automatic path resumes.

### D4. One list for the CLI and the API

The change stays in `Plan.by_hand`; `print_by_hand`, `cli.cmd_update` and
`server.app.update_state` are untouched, so the terminal and the System panel cannot
disagree. The API model keeps `by_hand: list[str]`: no `web/openapi.json` change.

## Risks

- `uv tool install lado==X` over a tool from a wheel replaces it with PyPI's build of X:
  that is what `lado update X` asks for (its plan says "PyPI"), and the human reads the
  line before running it.
