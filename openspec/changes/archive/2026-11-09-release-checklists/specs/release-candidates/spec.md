## MODIFIED Requirements

### Requirement: A final tag differs from its last release candidate only in its version

For a final tag `vX.Y.Z` with tags `vX.Y.ZrcN`, the check SHALL compare the final tag's
commit with that of the RC tag of the highest N and fail, naming each file or line, when a
file other than `CHANGELOG.md`, `docs/releases/X.Y.Z.md`, `pyproject.toml` and `uv.lock`
differs, a changed line of `pyproject.toml` is not a `version = "…"` line, or one of
`uv.lock` is not the `lado` package's own `version = "…"` line.

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

#### Scenario: The release's checklist edited after its last release candidate
- **WHEN** `v0.37.0`'s commit also changes `docs/releases/0.37.0.md` against `v0.37.0rc2`
- **THEN** the check passes

#### Scenario: Another release's checklist edited after the last release candidate
- **WHEN** `v0.37.0`'s commit also changes `docs/releases/0.36.0.md` against `v0.37.0rc2`
- **THEN** the check fails naming `docs/releases/0.36.0.md`, and nothing is published

## REMOVED Requirements

### Requirement: The release candidate's checklist names what is left by hand

**Reason**: The checks left by hand were the script's own two lines and every item of CHANGELOG.md's `(unreleased)` section, which matched neither docs/release.md nor the release's real checks.
**Migration**: Replaced by "The release candidate's checklist is docs/release.md's and the release's own": the every-RC list of docs/release.md, then the RC's section of `docs/releases/X.Y.Z.md`.

## ADDED Requirements

### Requirement: The release candidate's checklist is docs/release.md's and the release's own

`sandbox` and `upgrade` SHALL end with the checks left to the human: each `- [ ] ` line of
docs/release.md's list of the checks of every RC, then each top-level `- [ ] ` item of the
section `## X.Y.ZrcN` (the RC's version) of `docs/releases/X.Y.Z.md`, the item's first
line only, both read from the current folder. A missing file, list or section SHALL be one
warning line in its place, never a failure.

#### Scenario: The every-RC checks, then the RC's own
- **WHEN** docs/release.md's list has two checks, `docs/releases/0.38.0.md` has a section
  `## 0.38.0rc1` with two items, one of them with nested lines, and the human ran
  `sandbox 0.38.0rc1`
- **THEN** the checklist is the two checks, then the two items, each on one line with
  `[ ]`, the nested lines left out

#### Scenario: Only the RC's own section
- **WHEN** `docs/releases/0.38.0.md` has the sections `## 0.38.0rc1` and `## 0.38.0rc2`,
  and the human ran `upgrade 0.38.0rc2`
- **THEN** the checklist holds the every-RC checks and the items of `## 0.38.0rc2` only

#### Scenario: A release without its checklist
- **WHEN** there is no `docs/releases/0.39.0.md`, or it has no `## 0.39.0rc1`, and the
  human ran `sandbox 0.39.0rc1`
- **THEN** the checklist ends with one warning line naming the file and the section, and
  the script's exit code is that of its checks

#### Scenario: Not the repository's root
- **WHEN** the script runs in a folder without docs/release.md
- **THEN** the checklist is one warning line saying to run it from the repository's root
