## RENAMED Requirements

- FROM: `### Requirement: The install guide leads with compose and runs the headers' commands`
- TO: `### Requirement: The install guide leads with the installer, then compose by hand`

## MODIFIED Requirements

### Requirement: The install guide leads with the installer, then compose by hand

docs/install.md SHALL have a section `Docker` that leads with the installer (the
`install.sh` line, the `install.ps1` line, what they ask and do, the download-read-run
way, and that a rerun updates), then gives the manual way as "By hand", led by compose.
README's Install SHALL link to it.

#### Scenario: By hand keeps the manual steps
- **WHEN** `tests/test_docker.py` reads the guide's Docker section
- **THEN** "By hand" follows "Install with one command" and comes before the manual steps:
  check the shell, get `compose.yaml` and write `.env`, start; then the agents'
  variables, logins, ssh, update and going back, a second LADO, the sessions, removal and
  the pitfalls

#### Scenario: Secrets as a step of their own
- **WHEN** `tests/test_docker.py` reads the guide's Docker section and README's Docker
  install
- **THEN** neither start has `mkdir`, and the guide's "The agents' variables" has
  `LADO_SECRETS=./secrets` and `mkdir -m 700 secrets`

#### Scenario: The installer first
- **WHEN** `tests/test_docker.py` reads the guide's Docker section
- **THEN** its first code block is `curl -fsSL
  https://github.com/ladohq/lado/releases/latest/download/install.sh | sh`, the
  PowerShell line `irm https://github.com/ladohq/lado/releases/latest/download/install.ps1
  | iex` follows, and the manual `docker compose up -d` comes after both

### Requirement: The guide and README check the shell's variables first

The guide's manual way SHALL say to check `env | grep -E '^(LADO|COMPOSE)_'` and `unset`
what the shell sets, since a shell's variable beats `.env`. README's Docker install SHALL
be the installer's lines alone, with no `mkdir` and no `docker compose` command, since the
installer runs compose without the shell's `LADO_*` and `COMPOSE_*` variables and names
them.

#### Scenario: README checks the shell first
- **WHEN** `tests/test_docker.py` reads README's Docker install
- **THEN** its commands are the `install.sh` line and the `install.ps1` line, with no
  `docker compose up -d`, and the guide's manual way has `env | grep -E
  '^(LADO|COMPOSE)_'` and an `unset` naming `LADO_VERSION` and `COMPOSE_PROJECT_NAME`,
  both before its `docker compose up -d`

### Requirement: An update takes the version's compose.yaml

`docker/compose.yaml`'s header and the guide's update by hand SHALL, in the folder of
`compose.yaml`, keep a copy of it, download that version's `compose.yaml`, set the new
`LADO_VERSION` in `.env`, then `docker compose up -d`, in this order. README's Docker
update and the first way of the guide's "Update the container" SHALL be the installer's
line run again, which does the same steps.

#### Scenario: The update by hand
- **WHEN** `tests/test_docker.py` reads the header's and the guide's update by hand
- **THEN** its commands are `cp compose.yaml compose.yaml.bak`, `curl -fLO
  https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml` and `docker
  compose up -d`, in this order

#### Scenario: The address is the release's asset
- **WHEN** `tests/test_docker.py` reads the update's address and the release workflow's
  `gh release create`
- **THEN** the address's tag is `v` and the version, as `$GITHUB_REF_NAME` is, and its
  file is the asset `compose.yaml`

#### Scenario: README's update
- **WHEN** `tests/test_docker.py` reads README's `## Update`, `### Docker`
- **THEN** it runs the `install.sh` line (and names the `install.ps1` line for Windows),
  and links to the guide's update by hand

### Requirement: README and the guide present Docker first, then PyPI

README's Install and docs/install.md's opening SHALL present the two ways to install,
Docker first and recommended, then PyPI, each with what it is for and what it needs; the
Docker way's systems SHALL be macOS and Linux by `install.sh` and Windows by `install.ps1`
(Docker Desktop with Ubuntu in WSL2); PyPI's differences by system (macOS, Linux, Windows
inside WSL2) SHALL be named there too.

#### Scenario: Two ways, Docker first
- **WHEN** `tests/test_docker.py` reads README's Install and docs/install.md's opening
- **THEN** each names Docker as recommended before PyPI, and docs/install.md's `## Docker`
  comes before its systems' sections

#### Scenario: Windows by the PowerShell line
- **WHEN** `tests/test_docker.py` reads docs/install.md's table of the two ways
- **THEN** the Docker column's Systems names Windows through `install.ps1` and WSL2, and
  not "not checked"
