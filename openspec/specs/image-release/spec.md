# image-release Specification

## Purpose
How a release publishes LADO's image: the Release workflow builds it for amd64 and arm64,
runs the container tests on each before anything is published, pushes it to GHCR as
`ghcr.io/ladohq/lado:<version>` (`latest` only for the newest final release), and the
GitHub release names its `docker pull`.

## Requirements

### Requirement: A release publishes LADO's image to GHCR for amd64 and arm64

For every release tag, a release candidate's too, the Release workflow SHALL publish LADO's
image as `ghcr.io/ladohq/lado:<version>` (the tag without its `v`, PEP 440's spelling, e.g.
`0.39.0rc1`), one multi-architecture image for linux/amd64 and linux/arm64, each
architecture built on its own native runner from `docker/Dockerfile` with the wheel the
same run uploads to PyPI (the workflow artifact `dist`).

#### Scenario: A release candidate is tagged
- **WHEN** `v0.39.0rc1` is pushed and the workflow succeeds
- **THEN** `docker pull ghcr.io/ladohq/lado:0.39.0rc1` works on linux/amd64 and on
  linux/arm64, and `lado --version` in it prints `0.39.0rc1`

#### Scenario: The same wheel as PyPI
- **WHEN** the workflow publishes `0.39.0`
- **THEN** the LADO in the image is installed from the wheel attached to the GitHub
  release and uploaded to PyPI, never from an index

### Requirement: The image is pushed with the job's token and carries its labels

The Release workflow SHALL push the image with the job's
`GITHUB_TOKEN` (`packages: write`) and no other secret. The image SHALL carry the labels
`org.opencontainers.image.source` (the repository's URL) and
`org.opencontainers.image.version` (the version).

#### Scenario: No new secret
- **WHEN** the workflow file is read
- **THEN** it names no `secrets.` but the job token, and the jobs that push have
  `packages: write`

### Requirement: The image is tested before anything is published

Each architecture's image SHALL pass the container tests (`tests/container/`, run as CI's
container cell runs them, a skip a failure) before the workflow publishes anything: PyPI's
upload, the image's tags and the GitHub release SHALL wait for both architectures. When
either architecture fails, nothing SHALL be published under the
version: no PyPI release, no tag on GHCR, no GitHub release.

#### Scenario: A red container test on arm64
- **WHEN** a container test fails on arm64 for `v0.39.0rc2`
- **THEN** PyPI has no `0.39.0rc2`, `ghcr.io/ladohq/lado:0.39.0rc2` does not exist, and
  there is no GitHub release `v0.39.0rc2`

### Requirement: The tagged image is the image the tests ran

The image that gets the tags SHALL be the very image the tests ran (the same image digest per
architecture).

#### Scenario: The tested image is the tagged one
- **WHEN** the workflow tags `0.39.0`
- **THEN** each architecture's image under the tag has the digest the container tests ran

### Requirement: latest names only the newest final release

`ghcr.io/ladohq/lado:latest` SHALL be moved only by a final release, by the same rule that
makes its GitHub release the latest (`scripts/release_notes.py --flag`); a release
candidate SHALL get its own version tag and no other. No floating tag other than `latest`
SHALL be published. The plain version tag SHALL be the image with every agent CLI, so that
images with fewer agents can later be published as `<version>-<agent>`.

#### Scenario: A release candidate
- **WHEN** `v0.39.0rc1` is published
- **THEN** `latest` still names the image of the final before it

#### Scenario: A final
- **WHEN** `v0.39.0` is published
- **THEN** `:0.39.0` and `:latest` name the same image

### Requirement: The GitHub release names the image

The GitHub release's notes SHALL say, beside the PyPI install line, `docker pull
ghcr.io/ladohq/lado:<version>`, for a release candidate and a final alike; the GitHub
release SHALL be created only after the image's tags exist.

#### Scenario: A final's notes
- **WHEN** `python3 scripts/release_notes.py v0.39.0` prints the notes
- **THEN** they hold `docker pull ghcr.io/ladohq/lado:0.39.0`

#### Scenario: A release candidate's notes
- **WHEN** it prints the notes of `v0.39.0rc1`
- **THEN** they hold `docker pull ghcr.io/ladohq/lado:0.39.0rc1`

### Requirement: The GitHub release carries compose.yaml

The GitHub release of every release, a release candidate and a final alike, SHALL carry
the tag's `docker/compose.yaml` as an asset named `compose.yaml`, so that
`https://github.com/ladohq/lado/releases/latest/download/compose.yaml` gives the newest
final's file and `https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml`
the file of one version. The install guide SHALL download the first from the latest
address, and each update's from the version's address.

#### Scenario: The workflow attaches the file
- **WHEN** `tests/test_release_workflow.py` reads the job `github-release`
- **THEN** its `gh release create` uploads `docker/compose.yaml` as `compose.yaml`
  beside the files of `dist/`

#### Scenario: The guide's address
- **WHEN** `tests/test_docker.py` reads docs/install.md's Docker section
- **THEN** it downloads `releases/latest/download/compose.yaml`, the asset's name

#### Scenario: The update's address
- **WHEN** `tests/test_docker.py` reads docs/install.md's "Update the container"
- **THEN** it downloads `releases/download/v<version>/compose.yaml`
