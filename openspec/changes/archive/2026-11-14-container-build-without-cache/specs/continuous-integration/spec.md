## ADDED Requirements

### Requirement: The container cells build the image without a layer cache

A CI cell `container (<arch>)` SHALL build LADO's image with a plain `make docker` on the
runner's own Docker, on every event, and MUST NOT read or write a layer cache: the job
`container` in `.github/workflows/ci.yml` has no BuildKit builder of its own
(`docker/setup-buildx-action`), no `crazy-max/ghaction-github-runtime`, and no
`type=gha`, `cache-from`, `cache-to` or `--builder`.

#### Scenario: A pull request's container cell

- **WHEN** a pull request's run reaches the step `Image` of a container cell
- **THEN** it runs `make docker` and `docker history lado:local`, builds every layer from
  nothing, and writes no entry to the Actions cache

#### Scenario: A layer cache comes back into the job

- **WHEN** someone adds `--cache-from type=gha` or `docker/setup-buildx-action` to the job
  `container`
- **THEN** the unit tests fail

## MODIFIED Requirements

### Requirement: The run's code changes only the image's last layers

A CI cell `container (<arch>)` SHALL test an image built from the run's own wheel, and
`docker/Dockerfile` SHALL copy and install that wheel after every agent CLI and openspec,
so a build that reuses earlier layers (a developer's own Docker) rebuilds only the layers
from the wheel on.

#### Scenario: A pull request's wheel in the image

- **WHEN** a pull request changes LADO's version
- **THEN** `lado --version` in the tested image is the pull request's version

#### Scenario: The wheel's layer moves up

- **WHEN** someone puts the wheel's `COPY` before an agent CLI's install in the Dockerfile
- **THEN** the unit tests fail

## REMOVED Requirements

### Requirement: The image's layers come from a cache that only main writes

**Reason**: LAD-252's measurement: the cache saved 14-16 s of a cell that ends 1.5 % of
green pull request runs, and took 7.0 GB of the repository's 10 GB Actions cache.

**Migration**: the cells build from nothing (The container cells build the image without
a layer cache); the cache's entries expire by GitHub's 7-day rule.
