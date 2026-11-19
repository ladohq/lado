## ADDED Requirements

### Requirement: The image gives github.com no credential helper of its own

The image's system git config SHALL set no credential helper for `https://github.com`:
git reaches github.com with the github.com entry of Settings → Git servers (capability
`git-servers`), and without one as any host not in the list.

#### Scenario: gh logged in on the home volume, no entry
- **WHEN** `~/.config/gh/hosts.yml` on the home volume holds a login, github.com has no
  entry, and an agent's shell runs `git credential fill` for `protocol=https`,
  `host=github.com` with no prompt
- **THEN** git prints no password

## MODIFIED Requirements

### Requirement: compose binds the secrets folder read-only, no folder by default

`docker/compose.yaml` SHALL bind the path `LADO_SECRETS` names read-only at
`/run/secrets`, by default `/dev/null`: no secrets, as for the ssh agent. It SHALL refuse
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

### Requirement: The headers say how to fill the secrets folder

The headers SHALL say to make the secrets folder with mode 700 and to put one file per
variable in it (`CLAUDE_CODE_OAUTH_TOKEN`, a kit's key such as `YOUGILE_API_KEY`, a model
provider's key). A new file reaches the agents started after it, with no restart. Each
LADO container has its own folder or none, and every agent of one container can read every
variable given to it.

#### Scenario: The headers on the folder's files
- **WHEN** the human reads the headers of `docker/compose.yaml` and `docker/Dockerfile`
- **THEN** they say to make the folder with mode 700 and to put one file per variable in
  it, such as `YOUGILE_API_KEY`

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the optional secrets folder, enabled by
  `LADO_SECRETS=./secrets` in `.env` or `-v <folder>:/run/secrets:ro`, one file per
  variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub and other git servers over https (Settings → Git servers, or `lado git-server
  add`), never `GH_TOKEN` or `gh auth login`;
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux).

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `Git servers`,
  `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login`, `kilo auth login`,
  `CODEX_ACCESS_TOKEN`, `OPENAI_API_KEY` and `codex login --device-auth`, neither names
  `GH_TOKEN` nor `gh auth login`; compose's names `LADO_SECRETS=./secrets`

## REMOVED Requirements

### Requirement: git over https to GitHub uses gh's token

**Reason**: github.com is a saved git server whose token LADO gives git; the outside login
is no longer used (capability `git-servers`).
**Migration**: the GitHub login of `GH_TOKEN` or `gh auth login` is taken over once into
the github.com entry.
