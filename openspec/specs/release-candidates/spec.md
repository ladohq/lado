# release-candidates Specification

## Purpose
How LADO's releases reach users: a minor release is first a release candidate on PyPI,
which only a LADO that names it or runs a pre-release itself is offered, a pre-release says
so wherever LADO shows its version, and a final release is the code of its last release
candidate (docs/release.md).

## Requirements

### Requirement: A final release offers only final releases

A LADO whose own version is a final release (no `aN`, `bN`, `rcN` or `.devN`) SHALL be
offered only final releases: `update.check` (the daily check behind `lado ls`,
`lado doctor`, `GET /api/update` and the System panel), `lado update` without a version
and the UI's update plan (`GET /api/update/plan`) SHALL take the newest release of PyPI's
index that is no pre-release and not wholly yanked, and offer it only when it is newer
than this LADO.

#### Scenario: A newer release candidate is not offered to a final release
- **WHEN** LADO 0.36.0 runs and PyPI's index holds 0.36.0 and 0.37.0rc1
- **THEN** `update.check` finds 0.36.0, nothing is available, `lado update` prints
  `LADO 0.36.0 is the latest version.`, and the System panel shows no Update block

#### Scenario: A newer final release is offered
- **WHEN** LADO 0.36.0 runs and PyPI's index holds 0.37.0rc1 and 0.37.0
- **THEN** 0.37.0 is available

### Requirement: A pre-release is installed only when its version is named

A LADO whose own version is a final release SHALL install a pre-release only when its
version is named (`lado update X.Y.ZrcN`).

#### Scenario: A named release candidate is installed
- **WHEN** LADO 0.36.0 runs `lado update 0.37.0rc1` and PyPI has 0.37.0rc1
- **THEN** the plan is `LADO 0.36.0 -> 0.37.0rc1` and the update installs it as any
  named version

### Requirement: A pre-release is offered newer pre-releases

A LADO whose own version is a pre-release SHALL be offered the newest release of PyPI's
index, pre-release or final, that is newer than this LADO and not wholly yanked, by the
same paths (`update.check`, `lado update` without a version, the UI's update plan). The
update check's cache (`update-check.json`) SHALL record whether its look included
pre-releases, and a cache of the other kind SHALL count as stale, so a LADO that moved
between a pre-release and a final release looks again at once.

#### Scenario: The next release candidate is offered to a tester
- **WHEN** LADO 0.37.0rc1 runs and PyPI's index holds 0.36.0, 0.37.0rc1 and 0.37.0rc2
- **THEN** 0.37.0rc2 is available, and `lado ls` ends with
  `LADO 0.37.0rc2 is available: lado update`

#### Scenario: The final release is offered to a tester
- **WHEN** LADO 0.37.0rc2 runs and PyPI's index holds 0.37.0rc2 and 0.37.0
- **THEN** 0.37.0 is available

#### Scenario: After the final, release candidates are no longer offered
- **WHEN** the tester updated to 0.37.0, whose cache was written by 0.37.0rc2's look, and
  PyPI's index holds 0.37.0 and 0.38.0rc1
- **THEN** the check looks again, finds 0.37.0, and nothing is available

### Requirement: A pre-release says so

When this LADO's version is a pre-release, `lado doctor`'s LADO line and the system report
(`doctor.report`) SHALL name the version with ` (pre-release)`; `UpdateInfo` SHALL carry
`prerelease` (this LADO is one) and `available_prerelease` (the available release is
one); and the System panel SHALL show a grey `pre-release` pill beside `LADO <version>`
in its head and beside an available pre-release in its Update block. A final release SHALL
show none of them.

#### Scenario: The doctor on a release candidate
- **WHEN** LADO 0.37.0rc2 runs `lado doctor` and nothing newer is out
- **THEN** it prints `[ok  ] LADO: 0.37.0rc2 (pre-release), the latest version`

#### Scenario: The System panel on a release candidate with the next one out
- **WHEN** LADO 0.37.0rc1's System panel opens and 0.37.0rc2 is available
- **THEN** its head reads `LADO 0.37.0rc1` with a `pre-release` pill, and its Update block
  reads `0.37.0rc2 is out` with a `pre-release` pill

#### Scenario: The final release offered to a release candidate has no pill
- **WHEN** LADO 0.37.0rc2's System panel opens and 0.37.0 is available
- **THEN** the head has the pill and the Update block `0.37.0 is out` has none

### Requirement: A final release is the code of its last release candidate

The Release workflow SHALL run `scripts/release_check.py <tag>` with the repository's full
history before it builds, and SHALL publish nothing when it fails. For a final tag
`vX.Y.Z` the check SHALL fail when Z is 0 and no tag `vX.Y.ZrcN` exists (`vX.Y.0 needs a
release candidate: tag vX.Y.0rc1 first`). A pre-release tag and a patch tag without RC
tags SHALL pass.

#### Scenario: A minor release without a release candidate
- **WHEN** `v0.38.0` is pushed and no tag `v0.38.0rcN` exists
- **THEN** the check fails with `v0.38.0 needs a release candidate: tag v0.38.0rc1 first`

#### Scenario: A patch release without a release candidate
- **WHEN** `v0.37.1` is pushed and no tag `v0.37.1rcN` exists
- **THEN** the check passes

### Requirement: A final tag differs from its last release candidate only in its version

For a final tag `vX.Y.Z` with tags `vX.Y.ZrcN`, the check SHALL
compare the final tag's commit with the commit of the RC tag of the highest N and fail when a file
other than `CHANGELOG.md`, `pyproject.toml` and `uv.lock` differs, a changed line of
`pyproject.toml` is not a `version = "…"` line, or a changed line of `uv.lock` is not
the `version = "…"` line of the `lado` package's own block (a dependency's version is
refused), naming each such file or line.

#### Scenario: A final release after its release candidate
- **WHEN** `v0.37.0` points to a commit that differs from `v0.37.0rc2`'s only in
  CHANGELOG.md, pyproject.toml's version line and the `lado` package's version line in
  uv.lock
- **THEN** the check passes and the workflow publishes 0.37.0

#### Scenario: A final release with code the release candidate did not have
- **WHEN** `v0.37.0`'s commit also changes `src/lado/runtime.py` against `v0.37.0rc2`
- **THEN** the check fails naming `src/lado/runtime.py`, and nothing is published

#### Scenario: A final release that bumps a dependency in uv.lock
- **WHEN** `v0.37.0`'s commit also changes the `version` line of another package than
  `lado` in uv.lock against `v0.37.0rc2`
- **THEN** the check fails naming that line, and nothing is published

### Requirement: A release candidate is checked in a scratch install

`python3 scripts/rc_check.py sandbox [VERSION]` SHALL install the release candidate
`VERSION` (by default the newest release in PyPI's index; when that is a final release it
SHALL refuse, exit 2, asking for the RC's version) with `uv tool install` into a new
temporary folder, and run every LADO process of it with `LADO_HOME`, `LADO_TMUX_SOCKET`,
`UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` inside that folder and `LADO_TELEMETRY=0`. It SHALL never read or change the human's own
`LADO_HOME`.

#### Scenario: Statistics stay off in the scratch install
- **WHEN** the sandbox runs any LADO command
- **THEN** its environment has `LADO_TELEMETRY=0` and a `LADO_HOME` inside the
  temporary folder

#### Scenario: The newest release on PyPI is a final
- **WHEN** the human runs `python3 scripts/rc_check.py sandbox` and PyPI's newest release
  is 0.38.0
- **THEN** the script installs nothing and exits 2 saying that 0.38.0 is a final release
  and to name the RC to check

### Requirement: The sandbox checks the release candidate's version, statistics and doctor

The sandbox SHALL
check, printing one `[ok  ]` or `[FAIL]` line each: that the installed `lado --version`
is `VERSION`; that `lado telemetry status` says statistics are off; that `lado doctor`
exits 0 and names `VERSION (pre-release)`.

#### Scenario: A failed check keeps the sandbox
- **WHEN** `lado doctor` of the RC reports a FAIL
- **THEN** that check prints `[FAIL]` with the reason, no later check runs, the folder is
  kept, the script prints its path and one command that stops and removes it, and exits 1

### Requirement: The sandbox starts and stops a session and uninstalls itself

After those checks the sandbox SHALL check, with one such line each:
that `lado start` of a scratch git repository
with one commit (provider `claude`, or `--provider`) exits 0 and `lado ls` shows its
session; then, unless `--no-ui`, it SHALL start the sandbox's UI, print its link and wait
for Enter; then that `lado stop` of the session exits 0 and `lado uninstall --yes` of the
sandbox exits 0 and leaves no `LADO_HOME` and no tmux server on its socket. It SHALL
then remove the folder and exit 0.

#### Scenario: A good release candidate
- **WHEN** the human runs `python3 scripts/rc_check.py sandbox 0.38.0rc1 --no-ui` and
  every check passes
- **THEN** each check prints `[ok  ]`, the temporary folder, its LADO home and its tmux
  server are gone, the script prints the checklist of what is left by hand and exits 0

#### Scenario: Ctrl-C removes the sandbox
- **WHEN** the human presses Ctrl-C while the sandbox's UI waits for Enter
- **THEN** the script stops the session, uninstalls the sandbox, removes the folder and
  exits 130

### Requirement: Moving onto a release candidate keeps the final's database

`python3 scripts/rc_check.py upgrade VERSION` SHALL run the human's own `lado update
VERSION` on the terminal, without `--yes`, then read `lado --version`.
When the LADO it updated was a final release and `~/.lado/backups/lado.db.<final>` exists
(under `LADO_HOME` when set), it SHALL copy that file to `~/.lado-rc/lado.db.<final>` and
remove every other file of `~/.lado-rc/`; when the LADO it updated was a pre-release, it
SHALL leave `~/.lado-rc/` as it is.

#### Scenario: The first release candidate of a cycle
- **WHEN** LADO 0.37.1 runs and the human runs `python3 scripts/rc_check.py upgrade
  0.38.0rc1` and answers `y` to `lado update`'s question
- **THEN** LADO is 0.38.0rc1 and `~/.lado-rc/` holds only `lado.db.0.37.1`, a copy of
  the backup that update made

#### Scenario: The next release candidate keeps the final's copy
- **WHEN** LADO 0.38.0rc1 runs and the human runs `upgrade 0.38.0rc2`
- **THEN** `~/.lado-rc/lado.db.0.37.1` stays as it was, although `lado update` replaced
  its own backup with `lado.db.0.38.0rc1`

### Requirement: upgrade keeps the copy only when the release candidate is installed

When the `lado --version` that `upgrade` reads is not
`VERSION`, it SHALL keep nothing and exit with the update's exit code (1 when that was 0).
When it is `VERSION`, it SHALL keep the copy also when the update exited non-zero
(an update that installed the RC exits 1 when a session did not resume on it), and then
exit with that code, saying that LADO is on `VERSION` now. It SHALL refuse inside an agent
(`LADO_AGENT` set).

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
`~/.lado-rc/lado.db.<final>` holds. It SHALL refuse,
changing nothing, inside an agent, when the human's LADO is no pre-release, and when
`~/.lado-rc/` holds no copy.

#### Scenario: No copy to go back to
- **WHEN** `~/.lado-rc/` holds no `lado.db.<version>`
- **THEN** the script changes nothing and exits 1 saying that `upgrade` from a final
  makes the copy, and that without a schema change `lado update <final>` is enough

### Requirement: rollback prints its plan and asks first

Before it changes anything `rollback` SHALL print its plan:
the sessions that run (not stopped in lado.db) and will be started again, whether the UI
server runs and will be started again, the final it installs, and whether lado.db will be
restored from the copy, which is when its schema (`PRAGMA user_version`) is newer than the
copy's, with what that loses (everything done on the RC); and it SHALL ask
`Roll back? [y/N]`.

#### Scenario: Back to the final without a schema change
- **WHEN** lado.db's schema equals the copy's
- **THEN** the plan says lado.db is kept, and the rollback restores nothing

### Requirement: rollback installs the final, restores lado.db and starts again what ran

On yes `rollback` SHALL run `lado stop --all`, `lado server stop`,
`lado update <final>` (on the terminal, without `--yes`), check that `lado --version` is
the final, restore lado.db from the copy by SQLite's backup API when the plan said so,
then run `lado start <repo> --name <session> --no-attach` for each planned session and
`lado ui --no-open` with the server's host and port when it ran.

#### Scenario: Back to the final after a schema migration
- **WHEN** LADO 0.38.0rc1 runs with schema 27, `~/.lado-rc/lado.db.0.37.1` has schema 26,
  session `app` runs, and the human answers `y` to both questions
- **THEN** LADO is 0.37.1, lado.db has schema 26 and the copy's content, session `app`
  runs again, and the UI server runs on its port again when it ran before

#### Scenario: The update back is refused
- **WHEN** the human answers `n` to `lado update <final>`'s own question, or it fails
- **THEN** lado.db is not restored, no session is started, and the script exits 1 naming
  the stopped sessions with the `lado start <repo> --name <session>` that resumes each

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
