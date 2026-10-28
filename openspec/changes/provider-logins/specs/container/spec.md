## MODIFIED Requirements

### Requirement: The headers say how the agent CLIs log in, and the first start makes no folder

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL also say:
- the logins of the agent CLIs: first the UI's Settings → Providers and environment, which
  logs Claude Code, OpenCode and Kilo in and keeps Claude Code's token; else Claude Code
  by `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) in the folder or one login
  inside; OpenCode and Kilo by `opencode auth login` and `kilo auth login` inside (kept on
  the home volume) or a model provider's key in the folder. Codex's login is not covered.
The first start's commands of both headers SHALL make no folder: the minimal start needs
no secrets.

#### Scenario: The minimal start makes no folder
- **WHEN** `tests/test_docker.py` reads the first start's commands of both headers
- **THEN** none of them is a `mkdir`

#### Scenario: The headers name the UI's login
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `Providers and environment`
