## MODIFIED Requirements

### Requirement: The headers name the UI's login first

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL name, before the
terminal's ways to log the agent CLIs in, the UI's Settings → Agent CLIs and environment,
which logs Claude Code, Codex, OpenCode and Kilo in from the page, a phone too, and keeps
Claude Code's token and Codex's token or key.

#### Scenario: The headers name the UI's login
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `Agent CLIs and environment`

### Requirement: The headers say how Codex logs in

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL say that Codex logs in
by `CODEX_ACCESS_TOKEN` (a ChatGPT Business or Enterprise access token) or
`OPENAI_API_KEY` in the secrets folder, or by one login inside (`codex login
--device-auth`, or Settings → Agent CLIs), kept on the home volume and shared by every
Codex agent.

#### Scenario: Codex's ways are named
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `CODEX_ACCESS_TOKEN`, `OPENAI_API_KEY` and `codex login --device-auth`
