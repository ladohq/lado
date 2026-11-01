## ADDED Requirements

### Requirement: The image's build runs each agent CLI it installs

The image's build SHALL run each agent CLI's `--version` right after its `npm install`,
in the same `RUN` line, so that an install that left a CLI unable to run fails the build;
a unit test SHALL keep each of the four install lines so, the command being its
`PINS` command.

#### Scenario: npm dropped a CLI's binary
- **WHEN** `npm install` of Codex CLI exits 0 without its platform package
- **THEN** `codex --version` fails and the image is not built

#### Scenario: Every CLI runs
- **WHEN** `tests/test_docker.py` reads `docker/Dockerfile`
- **THEN** each CLI's install line is `npm install -g --prefix /opt/agents` of its pin,
  then `/opt/agents/bin/<command> --version`, then `npm cache clean --force`
