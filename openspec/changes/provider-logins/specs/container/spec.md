## ADDED Requirements

### Requirement: The headers name the UI's login first

The headers of `docker/compose.yaml` and `docker/Dockerfile` SHALL name, before the
terminal's ways to log the agent CLIs in, the UI's Settings → Providers and environment,
which logs Claude Code, OpenCode and Kilo in from the page, a phone too, and keeps Claude
Code's token.

#### Scenario: The headers name the UI's login
- **WHEN** `tests/test_docker.py` reads both headers
- **THEN** each names `Providers and environment`
