## ADDED Requirements

### Requirement: A final release offers only final releases

A LADO whose own version is a final release (no `aN`, `bN`, `rcN` or `.devN`) SHALL be
offered only final releases: `update.check` (the daily check behind `lado ls`,
`lado doctor`, `GET /api/update` and the System panel), `lado update` without a version
and the UI's update plan (`GET /api/update/plan`) SHALL take the newest release of PyPI's
index that is no pre-release and not wholly yanked, and offer it only when it is newer
than this LADO. A pre-release SHALL be installed only when its version is named
(`lado update X.Y.ZrcN`).

#### Scenario: A newer release candidate is not offered to a final release
- **WHEN** LADO 0.36.0 runs and PyPI's index holds 0.36.0 and 0.37.0rc1
- **THEN** `update.check` finds 0.36.0, nothing is available, `lado update` prints
  `LADO 0.36.0 is the latest version.`, and the System panel shows no Update block

#### Scenario: A named release candidate is installed
- **WHEN** LADO 0.36.0 runs `lado update 0.37.0rc1` and PyPI has 0.37.0rc1
- **THEN** the plan is `LADO 0.36.0 -> 0.37.0rc1` and the update installs it as any
  named version

#### Scenario: A newer final release is offered
- **WHEN** LADO 0.36.0 runs and PyPI's index holds 0.37.0rc1 and 0.37.0
- **THEN** 0.37.0 is available

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
release candidate: tag vX.Y.0rc1 first`), and, when such tags exist, SHALL compare the
final tag's commit with the commit of the RC tag of the highest N and fail when a file
other than `CHANGELOG.md`, `pyproject.toml` and `uv.lock` differs, or a changed line of
`pyproject.toml` or `uv.lock` is not a `version = "…"` line, naming each such file or line.
A pre-release tag and a patch tag without RC tags SHALL pass.

#### Scenario: A final release after its release candidate
- **WHEN** `v0.37.0` points to a commit that differs from `v0.37.0rc2`'s only in
  CHANGELOG.md and the version lines of pyproject.toml and uv.lock
- **THEN** the check passes and the workflow publishes 0.37.0

#### Scenario: A final release with code the release candidate did not have
- **WHEN** `v0.37.0`'s commit also changes `src/lado/runtime.py` against `v0.37.0rc2`
- **THEN** the check fails naming `src/lado/runtime.py`, and nothing is published

#### Scenario: A minor release without a release candidate
- **WHEN** `v0.38.0` is pushed and no tag `v0.38.0rcN` exists
- **THEN** the check fails with `v0.38.0 needs a release candidate: tag v0.38.0rc1 first`

#### Scenario: A patch release without a release candidate
- **WHEN** `v0.37.1` is pushed and no tag `v0.37.1rcN` exists
- **THEN** the check passes
