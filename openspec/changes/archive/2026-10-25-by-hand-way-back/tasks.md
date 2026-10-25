## 1. The commands by hand

- [x] 1.1 `tests/test_update.py`, beside `test_update_of_another_install_prints_the_commands_and_stops_nothing`
  (unit: the CLI with the fake tmux and a published index, the lowest layer that prints
  the list): that test's venv gets an executable `bin/pip` and keeps its expected output
  (AC-3); new tests, each failing before 1.3: a prefix with a `uv-receipt.toml` of lado
  from a wheel file and no `bin/pip` prints `uv tool install lado==99.0.0` (AC-4); one
  with `pipx_metadata.json` of a folder prints `pipx install --force lado==99.0.0` (AC-4);
  an empty prefix prints `# install lado==99.0.0 with the installer of <prefix>: LADO does
  not know it` (AC-5).
- [x] 1.2 `tests/test_self_update.py`, beside
  `test_a_plan_to_an_older_schema_says_what_it_loses` (unit, its fixtures `older` and
  `two_sessions`: the wheel of schema 31, a copy that has one session only), with a venv
  prefix that has `bin/pip` and a UI server: `plan(...).by_hand()` is exactly the list of
  the scenario "Back from 0.43.0 to 0.42.0 by hand", with `state.home()` as `<home>`
  (AC-1, AC-2); beside `test_a_plan_to_an_older_version_of_the_same_schema_warns_of_nothing`,
  the list has no `cp` and starts every session (AC-6). One CLI test in
  `tests/test_update.py` (or there, as the fixtures allow) that `lado update 0.42.0
  --yes` with no installer prints that list and stops nothing (AC-1). They fail before
  1.3.
- [x] 1.3 `src/lado/self_update.py`, `Plan.by_hand`: the install line by the prefix's
  installer (D1), shell-quoted paths; with `self.restore`, the restore command after it
  (D2) and `lado start` only for the sessions not in `restore.missing` (D3). Its docstring
  says so.
- [x] 1.4 `tests/test_server_system.py`, `test_update_says_whether_this_lado_can_update_itself`:
  the fixture's prefix (`tmp_path / "prefix"`, empty) now gives the comment line
  `# install lado==<NEW> with the installer of <prefix>: LADO does not know it`, which the
  assertion names (or the test makes `bin/pip` there and keeps its assertion); `make web` is not needed (no API model
  changes).

## 2. Documents

- [x] 2.1 `docs/install.md`, "Installed otherwise": the install line names the installer
  found in the environment (`pip` there, else `uv tool install`, else `pipx install
  --force`, else a comment), and for a way back to an older schema the list holds the
  copy's restore and leaves out the sessions the copy lacks.
- [x] 2.2 `docs/design/modules.md`, `self_update.py`: `by_hand` as in 1.3.
- [x] 2.3 `CHANGELOG.md`, `## 0.43.0 (unreleased)`, Fixed: a line in the user's words,
  e.g. **The commands `lado update` shows to run by hand go back to an older version
  too.** They put the database's backup back, skip the sessions it lacks, and name the
  installer you have instead of a `pip` that is not there.

## 3. Checks

- [x] 3.1 `make lint`, `make test` pass; `openspec validate by-hand-way-back --strict`
  passes; CI green on the pull request's last commit (AC-7).

## 4. The install's folders and review round 1

- [x] 4.1 The uv line sets `UV_TOOL_DIR` to the prefix's parent, and `UV_TOOL_BIN_DIR` to
  the folder of the receipt's install-path of `lado` (`update.uv_bin_dir`), none for a
  receipt that cannot be read or names none; the pipx line sets `PIPX_HOME` for a prefix
  `<home>/venvs/<name>`, none otherwise (requirement "The uv and pipx lines by hand
  install where LADO is"); unit tests in `tests/test_update.py`, red first.
- [x] 4.2 The restore line's paths are absolute also for a relative `LADO_HOME` (review
  F1); `tests/test_self_update.py`, red first.
- [x] 4.3 A test that pip goes first beside a `uv-receipt.toml` (review F2), shown to
  fail with the order swapped.
- [x] 4.4 CI green on the pull request's last commit.
