## MODIFIED Requirements

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
