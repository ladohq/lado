## MODIFIED Requirements

### Requirement: A new image starts on an old home volume

A container of LADO's image whose home volume holds a `lado.db` of an older schema SHALL
migrate it at its start with the backup the capability `schema-migration` describes, and
`docker logs` SHALL show the upgrade line, or, when the migration fails, its message.
`docker/compose.yaml`'s header SHALL say that an update is that version's `compose.yaml`
downloaded next to `.env` and a new `LADO_VERSION` in `.env`, followed by `docker compose
up -d` (which pulls the image of that version; see "An update takes the version's
compose.yaml"), and that the
image before keeps its version's name, so no name is kept by hand and nothing names
`lado:previous`. It SHALL give the steps that go back after a migration that succeeded:
put the version before back in `.env`, stop the container, put the backup in place of
`lado.db` (with its `-wal` and `-shm` removed) with that image, and start it; after a
migration that failed, the first and the last step alone. The Dockerfile's header SHALL
say the same for `docker run`: the container removed and run again with the other
version's tag on the same home volume.

#### Scenario: The migration on start
- **WHEN** the image starts on a home volume whose `lado.db` has the schema before this
  LADO's and holds a stopped session
- **THEN** `/api/health` answers `ok`, `lado.db` has this LADO's schema,
  `~/.lado/backups/lado.db.schema-<the schema before>` exists, `docker logs` has the
  upgrade line, and `lado ls` in the container lists the session

#### Scenario: A migration that fails
- **WHEN** the image starts on a home volume whose `lado.db` cannot be migrated
- **THEN** `docker logs` has the message of a failed migration naming the image of the
  version run before and no traceback, and `lado.db` keeps its schema

#### Scenario: The image before keeps a name
- **WHEN** a container is updated by the compose header's steps from one version to
  another
- **THEN** the image of the version before is still named by its version tag, and no
  step tags an image

#### Scenario: Back to the backup
- **WHEN** after the migration on start the compose header's steps back run
- **THEN** `lado.db` has the schema before again, and the container runs the image of the
  version before

### Requirement: The image takes the agents' variables from a secrets folder

The image SHALL set `LADO_ENV_DIR=/run/secrets` for the UI server and `docker exec` (the
processes that launch agents), so the agents get the variables of the files mounted there
(capability agent-variables).
- `docker/compose.yaml` SHALL bind the path `LADO_SECRETS` names read-only at
  `/run/secrets`, by default `/dev/null`: no secrets, as for the ssh agent. It SHALL refuse
  to start when a folder `LADO_SECRETS` names does not exist, rather than letting Docker
  make it (`create_host_path: false`).
- With no secrets (the null device at `/run/secrets`, or nothing mounted there, as with
  `docker run` without the folder), the container SHALL say nothing about the folder in
  `docker logs`, and `lado start` no warning about it; `lado doctor` says how to give
  secrets (capability agent-variables).
- No variable for the agents SHALL be set through compose's `environment:` or the image's
  `ENV`, and `LADO_AGENT_ENV=inherit` SHALL not be set, so no value is in `docker
  inspect`.
- The headers SHALL say that the secrets folder is optional and is enabled by
  `LADO_SECRETS=./secrets` in `.env` (compose) or `-v <folder>:/run/secrets:ro` (`docker
  run`), to make the folder with mode 700 and to put one file per variable in it
  (`GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, a kit's key such as `YOUGILE_API_KEY`, a model
  provider's key). A new file reaches the agents started after it, with no restart. Each
  LADO container has its own folder or none, and every agent of one container can read
  every variable given to it.

#### Scenario: A kit that needs a variable starts
- **WHEN** a container runs with a folder holding `TEST_KIT_KEY` mounted at
  `/run/secrets`, and a session starts there with a kit whose role's MCP server has
  `env: {KEY: ${TEST_KIT_KEY}}`
- **THEN** the session and a worker of that role start, its supervisor's process has
  `TEST_KIT_KEY` with the file's value, and `docker inspect` of the container does not
  contain the value

#### Scenario: compose without the folder
- **WHEN** `docker compose up -d` runs in a folder with `compose.yaml` and `.env`, without
  `secrets/` and without `LADO_SECRETS`
- **THEN** the container starts, `lado doctor` exits 0 with `[info] Variables from
  outside: /run/secrets: none` and no warning, `docker compose logs lado` has no line
  about `/run/secrets` or `LADO_ENV_DIR`, and a session with the fake endpoint reaches
  idle

#### Scenario: Secrets enabled by one line
- **WHEN** `.env` has `LADO_SECRETS=./secrets`, the folder `secrets/` next to
  `compose.yaml` holds `GH_TOKEN` with a fake value, and `docker compose up -d` runs
- **THEN** an agent's shell has `GH_TOKEN` with that value, and `lado doctor` prints
  `[ok  ] Variables from outside: /run/secrets: GH_TOKEN`

#### Scenario: The folder named but missing
- **WHEN** `.env` has `LADO_SECRETS=./secrets` and there is no `secrets/`
- **THEN** compose refuses to start and names the missing path, and no folder is made

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the optional secrets folder, enabled by
  `LADO_SECRETS=./secrets` in `.env` or `-v <folder>:/run/secrets:ro`, one file per
  variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub over https (`GH_TOKEN` in the folder, or `gh auth login` inside);
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux);
- the logins of the agent CLIs: Claude Code by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude
  setup-token`) in the folder or one login inside; OpenCode and Kilo by `opencode auth
  login` and `kilo auth login` inside (kept on the home volume) or a model provider's key
  in the folder. Codex's login is not covered.

The first start's commands of both headers SHALL make no folder: the minimal start needs
no secrets.

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `GH_TOKEN`, `gh auth
  login`, `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login` and `kilo auth
  login`; compose's names `LADO_SECRETS=./secrets`

#### Scenario: The minimal start makes no folder
- **WHEN** `tests/test_docker.py` reads the first start's commands of both headers
- **THEN** none of them is a `mkdir`

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
`unset` what the shell sets, since a shell's variable beats `.env`.

README's Install and docs/install.md's opening SHALL present the two ways to install,
Docker first and recommended, then PyPI, each with what it is for and what it needs; PyPI's
differences by system (macOS, Linux, Windows inside WSL2) SHALL be named there too.
README's Docker install SHALL start without `mkdir`.

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

## ADDED Requirements

### Requirement: An update takes the version's compose.yaml

`docker/compose.yaml`'s header, docs/install.md's "Update the container" and README's
Docker update SHALL update in this order, in the folder of `compose.yaml`: download that
version's `compose.yaml` next to `.env` (`curl -fLO
https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml`), set the new
`LADO_VERSION` in `.env`, then `docker compose up -d`. They SHALL say that `.env`,
`secrets/` and the home volume stay, and the guide that a change made to `compose.yaml`
by hand must be carried over to the new file. Going back to the version before SHALL keep
the current `compose.yaml`. No step SHALL touch another LADO's folder, container or
volume.

#### Scenario: The header's update
- **WHEN** `tests/test_docker.py` reads the header's update
- **THEN** its commands are the `curl -fLO` of
  `releases/download/v<version>/compose.yaml`, then `docker compose up -d`, and its text
  names `LADO_VERSION` in `.env`

#### Scenario: The address is the release's asset
- **WHEN** `tests/test_docker.py` reads the update's address and the release workflow's
  `gh release create`
- **THEN** the address's tag is `v` and the version, as `$GITHUB_REF_NAME` is, and its
  file is the asset `compose.yaml`

#### Scenario: README's update
- **WHEN** `tests/test_docker.py` reads README's `## Update`, `### Docker`
- **THEN** it downloads `releases/download/v<version>/compose.yaml` before `docker compose
  up -d`
