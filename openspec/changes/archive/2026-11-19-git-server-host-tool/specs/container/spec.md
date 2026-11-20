## ADDED Requirements

### Requirement: The image carries glab at its pin

The image SHALL carry `glab` at the exact version of the build argument `GLAB_VERSION`, from
its release archive checked against a SHA-256 per architecture, in a layer of its own under
`/opt/tools`, with `GLAB_CHECK_UPDATE=false` and `GLAB_SEND_TELEMETRY=false` in the image's
`ENV` and profile; the image SHALL grow by at most 60 MB with it.

#### Scenario: A clean home volume
- **WHEN** a login shell as `lado` in a new container runs `glab --version`
- **THEN** it answers with `GLAB_VERSION`'s default, on amd64 and on arm64

#### Scenario: A loose pin
- **WHEN** `GLAB_VERSION` is not an exact version, or an architecture has no SHA-256
- **THEN** the unit tests fail and name the line

#### Scenario: An agent's glab in the image
- **WHEN** a GitLab server under a test authority is saved with its certificate and an agent
  of the container runs `glab auth status`
- **THEN** it is logged in, and `~/.config/glab-cli` and `~/.gitconfig` are unchanged
