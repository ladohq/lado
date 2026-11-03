## ADDED Requirements

### Requirement: Why a server has no list is given only with no list

A probe SHALL give why a server has no list of models only when it has none: when the list
asked without `anthropic-version` fails and the one asked with it gives the models, the
probe SHALL have those models and no why. Every place that shows the why (`lado
model-server probe` and `add`, Settings → Models) SHALL show it only with no list.

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400 and
  lists `claude-x` in Anthropic's shape with it
- **THEN** the probe has the models `claude-x` and no why, and Settings → Models shows
  `claude-x` with no `no list` reason

#### Scenario: A list that fails both ways
- **WHEN** the server answers `GET /v1/models` with 500 with and without the header
- **THEN** the probe has no list and its why is `GET /v1/models: 500`
