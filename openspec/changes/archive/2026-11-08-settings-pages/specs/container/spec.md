## MODIFIED Requirements

### Requirement: The headers name the UI's login first

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL name, before the
terminal's ways to log the agent CLIs in, the UI's Settings → Agent CLIs,
which logs Claude Code, Codex, OpenCode and Kilo in from the page, a phone too, and keeps
Claude Code's token and Codex's token or key.

#### Scenario: The headers name the UI's login
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `Settings → Agent CLIs`
