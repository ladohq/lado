## ADDED Requirements

### Requirement: The GitHub release carries the installers stamped with its version

The GitHub release of every release, a release candidate and a final alike, SHALL carry
`install.sh` and `install.ps1`, the tag's `docker/install.sh` and `docker/install.ps1`
with their version placeholder replaced by the version (the tag without its `v`), so that
`releases/latest/download/install.sh` (and `install.ps1`) give the newest final's
installer and `releases/download/v<version>/install.sh` one version's.

#### Scenario: The workflow attaches the stamped files
- **WHEN** `tests/test_release_workflow.py` reads the job `github-release`
- **THEN** it runs `scripts/stamp_installers.py` with the tag's version before `gh release
  create`, which uploads the stamped `install.sh` and `install.ps1` beside `compose.yaml`
  under those names

#### Scenario: The stamp
- **WHEN** `scripts/stamp_installers.py 0.44.0rc1 <dir>` runs
- **THEN** `<dir>/install.sh` has `LADO_INSTALL_VERSION=0.44.0rc1` and `<dir>/install.ps1`
  `$LadoVersion = '0.44.0rc1'`, every other line as in the repository

#### Scenario: A lost placeholder
- **WHEN** `docker/install.sh` has no placeholder line
- **THEN** the stamp exits non-zero naming the file, and the release is not created

### Requirement: The stamp replaces one placeholder or fails

`scripts/stamp_installers.py <version> <dir>` SHALL write the stamped copies into `<dir>`
and SHALL fail, naming the file, when a placeholder line is not found exactly once.
README's and the guide's install lines SHALL use the latest address.

#### Scenario: The guide's lines
- **WHEN** `tests/test_docker.py` reads README's and the guide's Docker install
- **THEN** they use `releases/latest/download/install.sh` and
  `releases/latest/download/install.ps1`
