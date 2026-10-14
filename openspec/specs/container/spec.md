# container Specification

## Purpose
How LADO behaves when it runs in a container: the image says so with `LADO_CONTAINER`,
`lado update` and the UI's update refuse there and name `docker compose pull && docker
compose up -d`, and `lado doctor`, the System panel and the issue report say LADO runs in a
container.

## Requirements

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

### Requirement: The UI server in a container names the port's publication, not other machines

In a container, a UI server listening on a non-loopback address SHALL NOT print the
warning that it is open to other machines; `lado server` and `lado ui` SHALL instead print
on stderr the one line `lado: note: the LADO server runs in a container and listens on
<host>:<port> inside it; who reaches it depends on how the container publishes the port
(127.0.0.1:<port>:<port>: this computer only). Published to other machines, the token
travels unencrypted (plain HTTP).` A server on a loopback address SHALL print neither, as
outside a container. Outside a container the warning SHALL stay as it is.

#### Scenario: The image's server starts
- **WHEN** `lado server --host 0.0.0.0 --port 8765` starts with `LADO_CONTAINER=1`
- **THEN** its output has the note naming `0.0.0.0:8765` and no `open to other machines`

#### Scenario: The same server outside a container
- **WHEN** `lado server --host 0.0.0.0` starts without `LADO_CONTAINER`
- **THEN** it prints the warning that it is open to other machines, as before

### Requirement: lado ui in a container prints the link for the host's browser

In a container `lado ui` SHALL print the server's local link
(`http://127.0.0.1:<port>/?token=<token>` for a server on `0.0.0.0`) and SHALL NOT print a
`From another machine` line nor try to open a browser. With `--no-open` its standard
output SHALL be that one line; without it, the link followed by the line `Open it in your
browser on the host.`

#### Scenario: The launcher asks for the link
- **WHEN** `docker exec lado lado ui --no-open` runs against a server on `0.0.0.0:8765` in
  a container
- **THEN** standard output is exactly `http://127.0.0.1:8765/?token=<token>`, and stderr
  has the note

#### Scenario: lado ui without --no-open in a container
- **WHEN** the human runs `lado ui` in a container
- **THEN** no browser is opened, and it prints the link and `Open it in your browser on
  the host.`

#### Scenario: Outside a container
- **WHEN** `lado ui --no-open` runs without `LADO_CONTAINER` against a server on
  `0.0.0.0`
- **THEN** it prints the local link, then `From another machine: http://<hostname>:<port>/?token=<token> (or this host's address)`,
  and the warning, as before
