## ADDED Requirements

### Requirement: A release candidate is checked in a scratch install

`python3 scripts/rc_check.py sandbox [VERSION]` SHALL install the release candidate
`VERSION` (by default the newest release in PyPI's index; when that is a final release it
SHALL refuse, exit 2, asking for the RC's version) with `uv tool install` into a new
temporary folder, and run every LADO process of it with `LADO_HOME`, `LADO_TMUX_SOCKET`,
`UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` inside that folder and `LADO_TELEMETRY=0`. It SHALL
check, printing one `[ok  ]` or `[FAIL]` line each: that the installed `lado --version`
is `VERSION`; that `lado telemetry status` says statistics are off; that `lado doctor`
exits 0 and names `VERSION (pre-release)`; that `lado start` of a scratch git repository
with one commit (provider `claude`, or `--provider`) exits 0 and `lado ls` shows its
session; then, unless `--no-ui`, it SHALL start the sandbox's UI, print its link and wait
for Enter; then that `lado stop` of the session exits 0 and `lado uninstall --yes` of the
sandbox exits 0 and leaves no `LADO_HOME` and no tmux server on its socket. It SHALL then
remove the folder and exit 0. It SHALL never read or change the human's own `LADO_HOME`.

#### Scenario: A good release candidate
- **WHEN** the human runs `python3 scripts/rc_check.py sandbox 0.38.0rc1 --no-ui` and
  every check passes
- **THEN** each check prints `[ok  ]`, the temporary folder, its LADO home and its tmux
  server are gone, the script prints the checklist of what is left by hand and exits 0

#### Scenario: Statistics stay off in the scratch install
- **WHEN** the sandbox runs any LADO command
- **THEN** its environment has `LADO_TELEMETRY=0` and a `LADO_HOME` inside the
  temporary folder

#### Scenario: The newest release on PyPI is a final
- **WHEN** the human runs `python3 scripts/rc_check.py sandbox` and PyPI's newest release
  is 0.38.0
- **THEN** the script installs nothing and exits 2 saying that 0.38.0 is a final release
  and to name the RC to check

#### Scenario: A failed check keeps the sandbox
- **WHEN** `lado doctor` of the RC reports a FAIL
- **THEN** that check prints `[FAIL]` with the reason, no later check runs, the folder is
  kept, the script prints its path and one command that stops and removes it, and exits 1

#### Scenario: Ctrl-C removes the sandbox
- **WHEN** the human presses Ctrl-C while the sandbox's UI waits for Enter
- **THEN** the script stops the session, uninstalls the sandbox, removes the folder and
  exits 130

### Requirement: Moving onto a release candidate keeps the final's database

`python3 scripts/rc_check.py upgrade VERSION` SHALL run the human's own `lado update
VERSION` on the terminal, without `--yes`, then read `lado --version`. When that is not
`VERSION`, it SHALL keep nothing and exit with the update's exit code (1 when that was 0).
When it is `VERSION`, it SHALL keep the copy below also when the update exited non-zero
(an update that installed the RC exits 1 when a session did not resume on it), and then
exit with that code, saying that LADO is on `VERSION` now.
When the LADO it updated was a final release and `~/.lado/backups/lado.db.<final>` exists
(under `LADO_HOME` when set), it SHALL copy that file to `~/.lado-rc/lado.db.<final>` and
remove every other file of `~/.lado-rc/`; when the LADO it updated was a pre-release, it
SHALL leave `~/.lado-rc/` as it is. It SHALL refuse inside an agent (`LADO_AGENT` set).

#### Scenario: The first release candidate of a cycle
- **WHEN** LADO 0.37.1 runs and the human runs `python3 scripts/rc_check.py upgrade
  0.38.0rc1` and answers `y` to `lado update`'s question
- **THEN** LADO is 0.38.0rc1 and `~/.lado-rc/` holds only `lado.db.0.37.1`, a copy of
  the backup that update made

#### Scenario: The next release candidate keeps the final's copy
- **WHEN** LADO 0.38.0rc1 runs and the human runs `upgrade 0.38.0rc2`
- **THEN** `~/.lado-rc/lado.db.0.37.1` stays as it was, although `lado update` replaced
  its own backup with `lado.db.0.38.0rc1`

#### Scenario: The RC is installed but a session did not resume
- **WHEN** LADO 0.37.1 runs, the human runs `upgrade 0.38.0rc1`, and `lado update`
  installs 0.38.0rc1 but exits 1 as a session did not resume on it
- **THEN** `~/.lado-rc/` holds `lado.db.0.37.1`, and the script exits 1 saying that LADO
  is 0.38.0rc1 now

#### Scenario: The update did not install the RC
- **WHEN** the human answers `n` to `lado update`'s question, or its installer fails
- **THEN** `lado --version` is still the final, `~/.lado-rc/` is not changed, and the
  script exits with the update's exit code

### Requirement: Going back from a release candidate

`python3 scripts/rc_check.py rollback` SHALL go back to the final release whose copy
`~/.lado-rc/lado.db.<final>` holds. Before it changes anything it SHALL print its plan:
the sessions that run (not stopped in lado.db) and will be started again, whether the UI
server runs and will be started again, the final it installs, and whether lado.db will be
restored from the copy, which is when its schema (`PRAGMA user_version`) is newer than the
copy's, with what that loses (everything done on the RC); and it SHALL ask
`Roll back? [y/N]`. On yes it SHALL run `lado stop --all`, `lado server stop`,
`lado update <final>` (on the terminal, without `--yes`), check that `lado --version` is
the final, restore lado.db from the copy by SQLite's backup API when the plan said so,
then run `lado start <repo> --name <session> --no-attach` for each planned session and
`lado ui --no-open` with the server's host and port when it ran. It SHALL refuse,
changing nothing, inside an agent, when the human's LADO is no pre-release, and when
`~/.lado-rc/` holds no copy.

#### Scenario: Back to the final after a schema migration
- **WHEN** LADO 0.38.0rc1 runs with schema 27, `~/.lado-rc/lado.db.0.37.1` has schema 26,
  session `app` runs, and the human answers `y` to both questions
- **THEN** LADO is 0.37.1, lado.db has schema 26 and the copy's content, session `app`
  runs again, and the UI server runs on its port again when it ran before

#### Scenario: Back to the final without a schema change
- **WHEN** lado.db's schema equals the copy's
- **THEN** the plan says lado.db is kept, and the rollback restores nothing

#### Scenario: The update back is refused
- **WHEN** the human answers `n` to `lado update <final>`'s own question, or it fails
- **THEN** lado.db is not restored, no session is started, and the script exits 1 naming
  the stopped sessions with the `lado start <repo> --name <session>` that resumes each

#### Scenario: No copy to go back to
- **WHEN** `~/.lado-rc/` holds no `lado.db.<version>`
- **THEN** the script changes nothing and exits 1 saying that `upgrade` from a final
  makes the copy, and that without a schema change `lado update <final>` is enough

### Requirement: The release candidate's checklist names what is left by hand

`sandbox` and `upgrade` SHALL end with the checks left to the human: the sdlc session
through one run to its first gate answered in the UI; the UI's chat, a gate's card and
the System panel's `pre-release` pill; and one line per item of the section
`## X.Y.Z (unreleased)` of the CHANGELOG.md in the current folder, X.Y.Z being the RC's,
read by `scripts/release_notes.py`'s rules. A missing or empty section SHALL be one
warning line in place of the items, never a failure.

#### Scenario: The CHANGELOG items as a checklist
- **WHEN** CHANGELOG.md's `## 0.38.0 (unreleased)` has two items and the human ran
  `sandbox 0.38.0rc1`
- **THEN** the checklist ends with those two items, each on one line with `[ ]`

#### Scenario: A checkout without the RC's section
- **WHEN** CHANGELOG.md has no `## 0.38.0 (unreleased)`
- **THEN** the checklist says so in one line, and the script's exit code is that of its
  checks
