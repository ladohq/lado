# doctor Specification

## Purpose
What `lado doctor` and the UI's System panel check and show about the machine LADO runs
on, so the human sees what is missing before a session fails on it.

## Requirements

### Requirement: lado doctor checks git

`lado doctor` SHALL have a `git` check, after `tmux`, by the same look as the folder check
(`git --version` on the PATH of its process): `FAIL` when git is not found (with the
`no_git` hint for this OS) or does not run (with git's first line and the `git_broken`
hint); `WARN` when its version is older than 2.31, saying that the folder-trust lookup of
the providers (`git rev-parse --path-format=absolute`) needs 2.31; `OK` with the version
otherwise.

#### Scenario: git missing
- **WHEN** no git is on PATH
- **THEN** the `git` line is `[FAIL]` with the install hint, and `lado doctor` exits 1

#### Scenario: The macOS stub
- **WHEN** `git --version` fails
- **THEN** the `git` line is `[FAIL]` with `git does not run: <its first line>` and
  `xcode-select --install`

#### Scenario: An old git
- **WHEN** `git --version` reports 2.30.2
- **THEN** the `git` line is `[warn]` naming 2.31 as the version LADO needs, and the
  exit status is that of the other checks

#### Scenario: A current git
- **WHEN** `git --version` reports 2.47.1
- **THEN** the `git` line is `[ok  ]` with `git version 2.47.1`

### Requirement: The System panel shows git

The UI's system facts (`GET /api/system`, `doctor.system_info`) SHALL carry git's version,
or `not installed` / `does not run`, never its path; the System panel SHALL show it as a
`git` row beside `tmux`, and the issue report (`doctor.report`) SHALL have a `- git: ...`
line.

#### Scenario: The panel names git's version
- **WHEN** the human opens the System panel on a machine with git 2.47.1
- **THEN** it shows a row `git` with `2.47.1`, and the copied report has `- git: 2.47.1`

#### Scenario: No git
- **WHEN** the server finds no git
- **THEN** the row shows `not installed`
