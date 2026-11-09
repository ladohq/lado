## ADDED Requirements

### Requirement: The image's layers come from a cache that only main writes

A CI cell `container (<arch>)` SHALL build LADO's image with BuildKit's GitHub Actions cache
in the scope `container-<arch>`: on a pull request it SHALL read the cache and MUST NOT
write it; on a push to `main` it SHALL read and write it; on the daily schedule and a manual
dispatch it SHALL build without reading the cache and write it anew.

#### Scenario: A pull request after a run of main

- **WHEN** a pull request changes `src/lado/cli.py` and `main`'s last push run wrote the cache
- **THEN** the cell takes the layers before the wheel from the cache, builds the wheel's
  layer from the pull request's wheel, and writes no cache

#### Scenario: A push to main

- **WHEN** a pull request is merged and CI runs on `main`
- **THEN** each architecture's cell reads the cache and writes its scope

#### Scenario: The daily run

- **WHEN** the schedule starts CI on `main`
- **THEN** each cell builds every layer anew, reading no cache, and writes its scope

#### Scenario: A pull request's build writes the cache

- **WHEN** the step `Image` passes `--cache-to` on a `pull_request` event
- **THEN** the unit tests fail

### Requirement: The run's code changes only the image's last layers

A CI cell `container (<arch>)` SHALL test an image built from the run's own wheel, and
`docker/Dockerfile` SHALL copy and install that wheel after every agent CLI and openspec,
so a cached build rebuilds only the layers from the wheel on.

#### Scenario: A pull request's wheel in the image

- **WHEN** a pull request changes LADO's version and the earlier layers come from the cache
- **THEN** `lado --version` in the tested image is the pull request's version

#### Scenario: The wheel's layer moves up

- **WHEN** someone puts the wheel's `COPY` before an agent CLI's install in the Dockerfile
- **THEN** the unit tests fail

### Requirement: The release image is built without a cache

`.github/workflows/release.yml` MUST build the published image from nothing, reading no
cache that CI writes: no `cache-from`, `cache-to` or `type=gha` in it.

#### Scenario: A cache in the release

- **WHEN** someone adds `--cache-from type=gha` to the release's build
- **THEN** the unit tests fail
