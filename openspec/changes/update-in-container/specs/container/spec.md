## ADDED Requirements

### Requirement: LADO knows it runs in a container by LADO_CONTAINER

LADO SHALL take itself as running in a container when the environment variable
`LADO_CONTAINER` is set to a value other than the empty string and `0`, and SHALL NOT
guess it any other way (no look at `/.dockerenv` or cgroups). One function
(`update.in_container`) SHALL answer it for the CLI, `lado doctor`, the system report and
the UI server alike.

#### Scenario: The image sets it
- **WHEN** LADO runs with `LADO_CONTAINER=1`
- **THEN** it runs in a container

#### Scenario: Unset, empty or 0
- **WHEN** `LADO_CONTAINER` is unset, empty or `0`
- **THEN** LADO does not run in a container, also inside a Docker container

### Requirement: lado update refuses in a container at once

In a container `lado update` SHALL refuse before it stops, writes or looks up anything
(no PyPI request, no `update.lock`, no `update.json`, no result, no stopped session or
server), with exit 1 and the one line `lado: LADO runs in a container: a new image updates
it, not lado update; on the host: docker compose pull && docker compose up -d`, whatever
its version argument and `--yes`. Inside an agent the agent's refusal SHALL come first;
the container's refusal SHALL come before the refusal of a running update and the
missing installer.

#### Scenario: The human updates in a container
- **WHEN** the human runs `lado update --yes` in a container where LADO is a uv tool
  install and the UI server runs
- **THEN** it prints the container line on stderr and exits 1, the UI server and every
  session still run, and `update-result.json`, `update.json` and `update.log` are as they
  were

#### Scenario: A named version
- **WHEN** the human runs `lado update 0.36.0` in a container
- **THEN** the same refusal, and PyPI is not asked

#### Scenario: An agent in a container
- **WHEN** an agent runs `lado update` in a container
- **THEN** it gets the agent's refusal

### Requirement: The UI's update refuses in a container

In a container `GET /api/update` SHALL answer `can_update` false, `why_not` `LADO runs in
a container: a new image updates it, not lado update`, `by_hand` the one command `docker
compose pull && docker compose up -d`, and `container` true (false outside one);
`POST /api/update` SHALL answer 409 with that reason and start nothing. The System panel
SHALL show a grey `container` pill beside `LADO <version>` in its head (its tooltip: LADO
runs in a container and a new image updates it), and, when a newer LADO is out, an Update
block with no **Update…** button, the reason, and the command under `On the host:` with
its Copy button.

#### Scenario: A newer LADO is out in a container
- **WHEN** the System panel opens in a container and 0.39.0 is available
- **THEN** the head reads `LADO 0.38.0` with a `container` pill, and the Update block reads
  `0.39.0 is out`, the reason, `On the host:` and `docker compose pull && docker compose up
  -d`, and has no Update… button

#### Scenario: The latest version in a container
- **WHEN** the System panel opens in a container and nothing newer is out
- **THEN** the head has the `container` pill and there is no Update block

#### Scenario: A start of the update is refused
- **WHEN** a client posts `/api/update` in a container
- **THEN** it gets 409 with the reason, and no `lado update` process is started

#### Scenario: Outside a container
- **WHEN** the System panel opens without `LADO_CONTAINER`
- **THEN** it shows no `container` pill and `UpdateInfo.container` is false

### Requirement: lado doctor and the report say LADO runs in a container

In a container `lado doctor`'s LADO line SHALL end with `, in a container`, and the line
that a newer LADO is out (`update.available_line`, shown by `lado ls` and as
`lado doctor`'s hint) SHALL name `docker compose pull && docker compose up -d` instead of
`lado update`. The system report (`doctor.report`: the System panel's copy and
`lado bug-report`) SHALL name the installer as `(<installer>, in a container)`.

#### Scenario: The doctor on the latest version
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and nothing newer is out
- **THEN** it prints `[ok  ] LADO: 0.38.0, the latest version, in a container`

#### Scenario: The doctor with a newer LADO out
- **WHEN** LADO 0.38.0 runs `lado doctor` in a container and 0.39.0 is available
- **THEN** it prints `[warn] LADO: 0.38.0, in a container` with the hint `LADO 0.39.0 is
  available: docker compose pull && docker compose up -d`, and `lado ls` ends with that
  same line

#### Scenario: The report for an issue
- **WHEN** the human copies the system info in a container where LADO is a uv tool install
- **THEN** its LADO line reads `- LADO 0.38.0 (uv tool, in a container), Python ...`
