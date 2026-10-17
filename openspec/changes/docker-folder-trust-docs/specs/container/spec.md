## MODIFIED Requirements

### Requirement: The install guide leads with compose and runs the headers' commands

docs/install.md SHALL have a section `Docker` that leads with compose: get `compose.yaml`,
write `.env`, start, open the UI, the agents' variables (the optional `secrets/`, enabled
by `LADO_SECRETS=./secrets` in `.env` and `mkdir -m 700 secrets`), log in to the agent
CLIs, ssh, update and go back, a second LADO, the sessions, removal and the pitfalls;
README's Install SHALL link to it. Its start, update and way-back commands SHALL be
exactly those of `docker/compose.yaml`'s header, which the container tests run (the
update's download is checked by its address, not run). Its `.env` SHALL name every
variable compose reads but `LADO_IMAGE` and `LADO_SECRETS`. It SHALL remove only its own
container and volume, by name, and nothing in the guide or the headers SHALL run a
`docker ... prune`. The guide SHALL say to check `env | grep -E '^(LADO|COMPOSE)_'` and
`unset` what the shell sets, since a shell's variable beats `.env`. Its "Your first
session" SHALL say that Claude Code asks whether to trust a repository it has not seen
before its first answer, that the agent waits in Needs you meanwhile, that the answer is
"Yes, I trust this folder" in the agent's terminal while Enter alone answers "No, exit" and
closes the agent, that it is asked once per repository and remembered on the home volume,
and that a trusted repository's own Claude Code settings and MCP servers run; the two
answers SHALL be quoted as LADO's own reason for that wait words them.

README's Install and docs/install.md's opening SHALL present the two ways to install,
Docker first and recommended, then PyPI, each with what it is for and what it needs; PyPI's
differences by system (macOS, Linux, Windows inside WSL2) SHALL be named there too.
README's Docker install SHALL start without `mkdir`, and SHALL first check the shell
with `env | grep -E '^(LADO|COMPOSE)_'` and `unset`, as the guide does.

#### Scenario: Two ways, Docker first
- **WHEN** `tests/test_docker.py` reads README's Install and docs/install.md's opening
- **THEN** each names Docker as recommended before PyPI, and docs/install.md's `## Docker`
  comes before its systems' sections

#### Scenario: The commands agree
- **WHEN** `tests/test_docker.py` reads the guide's code blocks and the header
- **THEN** the guide's start commands, its update (the version's `compose.yaml`, then
  `docker compose up -d`) and its way back (`way_back()`) are the header's

#### Scenario: Removal by name
- **WHEN** the test reads the guide's removal
- **THEN** it runs `docker compose down` and `docker volume rm` of the project's own
  `home` volume, and README.md, docs/*.md and docker/ hold no `prune` (docs/research/ and
  docs/superpowers/ are records, not read as instructions)

#### Scenario: Secrets as a step of their own
- **WHEN** `tests/test_docker.py` reads the guide's Docker section and README's Docker
  install
- **THEN** neither start has `mkdir`, and the guide's "The agents' variables" has
  `LADO_SECRETS=./secrets` and `mkdir -m 700 secrets`

#### Scenario: README checks the shell first
- **WHEN** `tests/test_docker.py` reads README's Docker install
- **THEN** its commands have `env | grep -E '^(LADO|COMPOSE)_'` and an `unset` naming
  `LADO_VERSION` and `COMPOSE_PROJECT_NAME`, both before `docker compose up -d`

#### Scenario: The first session names Claude Code's trust question
- **WHEN** `tests/test_docker.py` reads the guide's Docker "Your first session"
- **THEN** it names Needs you and quotes "Yes, I trust this folder" and "No, exit", and
  each quoted answer is in the reason `ClaudeProvider.first_hook_blocker` gives for a folder
  Claude Code does not trust
