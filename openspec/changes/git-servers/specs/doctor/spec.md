## MODIFIED Requirements

### Requirement: lado doctor checks git

`lado doctor` SHALL have a `git` check, after `tmux`, by the same look as the folder check
(`git --version` on the PATH of its process): `FAIL` when git is not found (with the
`no_git` hint for this OS) or does not run (with git's first line and the `git_broken`
hint); `WARN` when its version is older than 2.31, saying that the folder-trust lookup of
the providers (`git rev-parse --path-format=absolute`) and git servers
(`lado git-server`) need 2.31; `OK` with the version otherwise.

#### Scenario: git missing
- **WHEN** no git is on PATH
- **THEN** the `git` line is `[FAIL]` with the install hint, and `lado doctor` exits 1

#### Scenario: The macOS stub
- **WHEN** `git --version` fails
- **THEN** the `git` line is `[FAIL]` with `git does not run: <its first line>` and
  `xcode-select --install`

#### Scenario: An old git
- **WHEN** `git --version` reports 2.30.2
- **THEN** the `git` line is `[warn]` naming 2.31 as the version LADO needs, the hint names
  git servers among what needs it, and the exit status is that of the other checks

#### Scenario: A current git
- **WHEN** `git --version` reports 2.47.1
- **THEN** the `git` line is `[ok  ]` with `git version 2.47.1`
