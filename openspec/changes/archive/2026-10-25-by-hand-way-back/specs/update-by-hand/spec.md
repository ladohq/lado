## ADDED Requirements

### Requirement: The commands by hand name an installer that is there

When LADO knows no installer of its prefix (`update.installer()` is None), the install
line of the commands by hand (printed by `lado update`, the API's `by_hand`) SHALL name,
in this order, the prefix's `bin/pip` when it exists, `uv tool install` when the prefix
holds `uv-receipt.toml`, `pipx install --force` when it holds `pipx_metadata.json`, and
otherwise a comment line saying LADO does not know the installer. Paths SHALL be
shell-quoted.

#### Scenario: A virtual environment with pip
- **WHEN** LADO runs from a venv `<venv>` that has `bin/pip`, and the human runs
  `lado update`
- **THEN** the commands by hand have `<venv>/bin/pip install lado==99.0.0`

#### Scenario: Pip beside another installer's file
- **WHEN** LADO's prefix has `bin/pip` and also `uv-receipt.toml`
- **THEN** the install line is `<prefix>/bin/pip install lado==99.0.0`

#### Scenario: An installer LADO does not know
- **WHEN** LADO's prefix has neither `bin/pip`, nor `uv-receipt.toml`, nor
  `pipx_metadata.json`
- **THEN** the install line is `# install lado==99.0.0 with the installer of <prefix>:
  LADO does not know it`, and the other commands are as with pip

### Requirement: The uv and pipx lines by hand install where LADO is

The `uv tool` line of the commands by hand SHALL set `UV_TOOL_DIR` to the prefix's parent
folder, and `UV_TOOL_BIN_DIR` to the folder of the receipt's install-path of `lado` when
the receipt can be read and names one. The `pipx` line SHALL set `PIPX_HOME` to the
folder above `venvs` when the prefix is `<folder>/venvs/<name>`. Neither folder SHALL be
guessed otherwise. Paths SHALL be shell-quoted.

#### Scenario: A uv tool from a local wheel
- **WHEN** LADO's prefix holds `uv-receipt.toml` whose `lado` comes from a wheel file and
  whose `lado` entrypoint has the install-path `<bin>/lado`, and no `bin/pip`
- **THEN** the commands by hand have `UV_TOOL_DIR=<prefix's parent> UV_TOOL_BIN_DIR=<bin>
  uv tool install lado==99.0.0` and no `pip`

#### Scenario: A uv tool whose receipt names no executable
- **WHEN** LADO's prefix holds a `uv-receipt.toml` that cannot be read or has no
  install-path of `lado`
- **THEN** the uv line is `UV_TOOL_DIR=<prefix's parent> uv tool install lado==99.0.0`,
  without `UV_TOOL_BIN_DIR`

#### Scenario: A pipx install from a folder
- **WHEN** LADO's prefix `<home>/venvs/lado` holds `pipx_metadata.json` whose package is a
  folder, and no `bin/pip`
- **THEN** the commands by hand have `PIPX_HOME=<home> pipx install --force lado==99.0.0`

#### Scenario: A pipx prefix outside a venvs folder
- **WHEN** LADO's prefix holds `pipx_metadata.json` and its parent is not named `venvs`
- **THEN** the pipx line is `pipx install --force lado==99.0.0`, without `PIPX_HOME`

### Requirement: The commands by hand of an update to an older schema put the copy back

When the plan of `lado update X` warns that `lado.db` goes back to the migration's copy
and LADO knows no installer, its commands by hand SHALL put that copy into `lado.db`
after the install line and before any `lado start`, removing `lado.db-wal` and
`lado.db-shm` first, with absolute paths of the real `LADO_HOME`; they SHALL stop every
planned session and start again only those the copy has.

#### Scenario: Back from 0.43.0 to 0.42.0 by hand
- **WHEN** LADO 0.43.0 from a venv with `bin/pip` runs with `lado.db` at schema 35,
  `backups/lado.db.schema-31` exists, sessions `app` (in the copy) and `web2` (made after
  the migration) run with the UI server, and the human runs `lado update 0.42.0`
- **THEN** the commands by hand are, in order: `lado stop app`, `lado stop web2`,
  `lado server stop`, `<venv>/bin/pip install lado==0.42.0`,
  `rm -f <home>/lado.db-wal <home>/lado.db-shm && cp <home>/backups/lado.db.schema-31
  <home>/lado.db`, `lado start <app's repo> --name app`, `lado ui`; nothing is stopped
  and exit is 1

#### Scenario: An older version of the same schema by hand
- **WHEN** X's wheel holds the schema of `lado.db`
- **THEN** the commands by hand have no `cp` of a copy and start every planned session
  again
