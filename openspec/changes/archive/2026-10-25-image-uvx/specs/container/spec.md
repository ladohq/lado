## ADDED Requirements

### Requirement: The image carries uvx beside uv

The image SHALL carry `uvx` in `/usr/local/bin` beside `uv`, both copied from the one
pinned `uv` stage of `docker/Dockerfile` (the image `ghcr.io/astral-sh/uv`), so that an
agent's `uvx` is uv's own at uv's version, needs no mise, and answers before any mise
shim on `PATH`.

#### Scenario: uvx answers at uv's version in an agent's shell

- **WHEN** a login shell as `lado`, started from a clean environment as LADO starts an
  agent's, runs `command -v uvx`, `uvx --version` and `uv --version` in a new container on
  a new home volume
- **THEN** `uvx` is `/usr/local/bin/uvx`, and `uvx --version` answers with exit 0 and the
  same version number as `uv --version`

#### Scenario: uvx runs a package

- **WHEN** such a shell runs `uvx` offline with a local wheel's console script and the
  image's Python
- **THEN** the script runs and prints its output, and nothing is installed under
  `/opt/uv`

#### Scenario: The copy leaves uvx out

- **WHEN** `docker/Dockerfile` copies from the `uv` stage without `/uvx` into
  `/usr/local/bin`
- **THEN** the unit tests fail and name it
