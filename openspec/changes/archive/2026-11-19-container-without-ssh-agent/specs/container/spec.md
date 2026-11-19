## ADDED Requirements

### Requirement: The container has no ssh

`docker/compose.yaml` SHALL bind no ssh agent's socket, and the image SHALL hold no ssh
host key, no sudo rule or program for a socket and no profile file that sets
`SSH_AUTH_SOCK`. A `LADO_SSH_AGENT` in `.env` SHALL change nothing, and the container SHALL
say nothing about it. A saved git server's ssh addresses SHALL go over https with its token.

#### Scenario: An old .env with LADO_SSH_AGENT
- **WHEN** `.env` has `LADO_SSH_AGENT=<a socket on the host>` and `docker compose up -d` runs
- **THEN** the container starts, `/run/lado/ssh-agent.sock` does not exist, neither an
  agent's login shell nor the UI server has `SSH_AUTH_SOCK`, and neither `docker compose
  logs lado` nor `lado doctor` has a line about ssh

#### Scenario: An ssh address of a saved server
- **WHEN** `https://github.com` is saved and the UI clones `git@github.com:acme/app.git`
- **THEN** git asks the saved server's token over https, and no ssh runs

## MODIFIED Requirements

### Requirement: The root step removes its own way to root first

The change of `lado`'s uid SHALL be made by a step that runs as root once per container
and, first of all, removes its way to it (a sudo rule for the entrypoint alone), so
that no process started after it, an agent included, can become root through it. The
image SHALL have no other sudo rule.

#### Scenario: No way to root is left

- **WHEN** the container has started
- **THEN** `sudo -n true` run as `lado` in it fails, and `sudo -n -l` run as `lado` grants no command

### Requirement: compose binds the secrets folder read-only, no folder by default

`docker/compose.yaml` SHALL bind the path `LADO_SECRETS` names read-only at
`/run/secrets`, by default `/dev/null`: no secrets. It SHALL refuse
to start when a folder `LADO_SECRETS` names does not exist, rather than letting Docker
make it (`create_host_path: false`).

#### Scenario: Secrets enabled by one line
- **WHEN** `.env` has `LADO_SECRETS=./secrets`, the folder `secrets/` next to
  `compose.yaml` holds `YOUGILE_API_KEY` with a fake value, and `docker compose up -d` runs
- **THEN** an agent's shell has `YOUGILE_API_KEY` with that value, and `lado doctor` prints
  `[ok  ] Variables from outside: /run/secrets: YOUGILE_API_KEY`

#### Scenario: The folder named but missing
- **WHEN** `.env` has `LADO_SECRETS=./secrets` and there is no `secrets/`
- **THEN** compose refuses to start and names the missing path, and no folder is made

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the optional secrets folder, enabled by
  `LADO_SECRETS=./secrets` in `.env` or `-v <folder>:/run/secrets:ro`, one file per
  variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub and other git servers (Settings → Git servers, or `lado git-server add`), their
  ssh addresses going over https, never `GH_TOKEN` or `gh auth login`;
- that the container has no ssh.

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `Git servers`,
  `no ssh`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login`, `kilo auth login`,
  `CODEX_ACCESS_TOKEN`, `OPENAI_API_KEY` and `codex login --device-auth`, neither names
  `GH_TOKEN`, `gh auth login`, `LADO_SSH_AGENT` nor `SSH_AUTH_SOCK`; compose's names
  `LADO_SECRETS=./secrets`

### Requirement: The image holds no private data

The image SHALL hold no key, login, password or token of any person: the human gives
their own at run time (the secrets folder, logins on the home volume, Settings → Git
servers). The build context SHALL stay the allowlist of
`docker/Dockerfile.dockerignore`, which names each file the build takes.

#### Scenario: The build context
- **WHEN** `tests/test_docker.py` reads `docker/Dockerfile.dockerignore`
- **THEN** it lets in only `dist/lado-*.whl`, `docker/profile.sh`,
  `docker/entrypoint.sh` and `docker/mise.toml`

## REMOVED Requirements

### Requirement: The host's ssh agent reaches the agents without root's group

**Reason**: the container has no ssh; git servers are set up only in LADO's settings.
**Migration**: save the git server in Settings → Git servers; its ssh addresses go over https.

### Requirement: The entrypoint gives a root's socket to lado through one fixed program

**Reason**: no socket is bound, so neither the program nor its sudo rule is needed.
**Migration**: none.

### Requirement: An ssh agent's socket lado cannot use is a warning

**Reason**: no socket is bound.
**Migration**: none.

### Requirement: The image gives the agents and the server the host's ssh agent socket

**Reason**: no socket is bound; the container has no ssh.
**Migration**: save the git server in Settings → Git servers.

### Requirement: The image knows GitHub's ssh host keys

**Reason**: with no ssh key in the container, ssh to github.com runs only for an unsaved
github.com and fails anyway; the clone's hint covers both failures.
**Migration**: save github.com in Settings → Git servers.
