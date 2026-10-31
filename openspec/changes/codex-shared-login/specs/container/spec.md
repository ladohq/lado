## MODIFIED Requirements

### Requirement: The headers say how the agents log in and get access

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say:
- how to give the agents variables (the optional secrets folder, enabled by
  `LADO_SECRETS=./secrets` in `.env` or `-v <folder>:/run/secrets:ro`, one file per
  variable);
- the git identity (`LADO_GIT_NAME`, `LADO_GIT_EMAIL`);
- GitHub over https (`GH_TOKEN` in the folder, or `gh auth login` inside);
- the ssh agent (`LADO_SSH_AGENT` for a Mac and for Linux).

#### Scenario: The steps are in the headers
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** each names `secrets`, `LADO_GIT_NAME`, `LADO_GIT_EMAIL`, `GH_TOKEN`, `gh auth
  login`, `LADO_SSH_AGENT`, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode auth login`, `kilo auth
  login`, `CODEX_ACCESS_TOKEN`, `OPENAI_API_KEY` and `codex login --device-auth`; compose's
  names `LADO_SECRETS=./secrets`

### Requirement: The headers say how the agent CLIs log in, and the first start makes no folder

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL also say:
- the logins of the agent CLIs: Claude Code by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude
  setup-token`) in the folder or one login inside; OpenCode and Kilo by `opencode auth
  login` and `kilo auth login` inside (kept on the home volume) or a model provider's key
  in the folder; Codex by `CODEX_ACCESS_TOKEN` (a ChatGPT Business or Enterprise access
  token) or `OPENAI_API_KEY` in the folder, or one login inside (`codex login
  --device-auth`, or Settings → Providers), kept on the home volume and shared by every
  Codex agent.
The first start's commands of both headers SHALL make no folder: the minimal start needs
no secrets.

#### Scenario: Codex's login is named
- **WHEN** `tests/test_docker.py` reads the headers
- **THEN** neither says that Codex's login is not covered

#### Scenario: The minimal start makes no folder
- **WHEN** `tests/test_docker.py` reads the first start's commands of both headers
- **THEN** none of them is a `mkdir`
