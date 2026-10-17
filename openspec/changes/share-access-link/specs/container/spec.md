## MODIFIED Requirements

### Requirement: The UI server in a container names the port's publication, not other machines

In a container, a UI server listening on a non-loopback address SHALL decide its start
line by `LADO_LISTEN`, the host address compose publishes the port on:
- `LADO_LISTEN` a non-loopback IPv4 address (`0.0.0.0` too): the warning that the server
  is open to other machines, as outside a container, naming `LADO_LISTEN` and the port;
- `LADO_LISTEN` a loopback address: no line;
- `LADO_LISTEN` unset or not an IPv4 address: on stderr the one line `lado: note: the LADO
  server runs in a container and listens on <host>:<port> inside it; who reaches it
  depends on how the container publishes the port (127.0.0.1:<port>:<port>: this computer
  only). Published to other machines, the token travels unencrypted (plain HTTP).`
`lado server` and `lado ui` SHALL print the same line. A server on a loopback address
SHALL print neither, as outside a container. Outside a container the warning SHALL stay as
it is.

#### Scenario: The image's server starts
- **WHEN** `lado server --host 0.0.0.0 --port 8765` starts with `LADO_CONTAINER=1` and no
  `LADO_LISTEN`
- **THEN** its output has the note naming `0.0.0.0:8765` and no `open to other machines`

#### Scenario: Published to the network by compose
- **WHEN** the same server starts with `LADO_LISTEN=0.0.0.0`
- **THEN** its output has the warning that it is open to other machines, naming
  `0.0.0.0:8765`, and no note

#### Scenario: Published on this computer only by compose
- **WHEN** the same server starts with `LADO_LISTEN=127.0.0.1`
- **THEN** its output has neither the note nor the warning

#### Scenario: The same server outside a container
- **WHEN** `lado server --host 0.0.0.0` starts without `LADO_CONTAINER`
- **THEN** it prints the warning that it is open to other machines, as before

### Requirement: lado ui in a container prints the link for the host's browser

In a container `lado ui` SHALL print the server's local link
(`http://127.0.0.1:<port>/?token=<token>` for a server on `0.0.0.0`) and SHALL NOT try to
open a browser. With `--no-open` its standard output SHALL be that one line; without it,
the link followed by the line `Open it in your browser on the host.` A `From another
machine` line SHALL follow only when the link for another device exists (share-access,
"The link to another device follows one rule"): on standard output without `--no-open`,
on stderr with it.

#### Scenario: The launcher asks for the link
- **WHEN** `docker exec lado lado ui --no-open` runs against a server on `0.0.0.0:8765` in
  a container
- **THEN** standard output is exactly `http://127.0.0.1:8765/?token=<token>`, and stderr
  has the note

#### Scenario: lado ui without --no-open in a container
- **WHEN** the human runs `lado ui` in a container without `LADO_LISTEN`
- **THEN** no browser is opened, and it prints the link and `Open it in your browser on
  the host.`, and no `From another machine` line

#### Scenario: Outside a container
- **WHEN** `lado ui --no-open` runs without `LADO_CONTAINER` against a server on
  `0.0.0.0`
- **THEN** it prints the local link, then `From another machine: http://<address>:<port>/?token=<token>`
  with the address of share-access's rule, and the warning

### Requirement: The compose file publishes one port number

`docker/compose.yaml` SHALL run LADO's published image of the version `LADO_VERSION` names,
`ghcr.io/ladohq/lado:${LADO_VERSION}`, unless `LADO_IMAGE` names another image (`lado:local`,
the tests'); without either compose SHALL refuse and name `LADO_VERSION`, and it SHALL
never default to `latest`. It SHALL use one variable, `LADO_PORT` (8765 by default), as
both the server's port in the container and the published one,
`${LADO_LISTEN:-127.0.0.1}:${LADO_PORT}:${LADO_PORT}`, so the host's number and the
container's are always the same; `LADO_LISTEN` is the host address the port is published
on, the host's loopback unless `.env` names another. It SHALL give the container
`LADO_LISTEN` (`${LADO_LISTEN:-127.0.0.1}`) and `LADO_PUBLIC_HOST`
(`${LADO_PUBLIC_HOST:-}`), the name other devices reach the host by. It SHALL mount
`LADO_PROJECTS`, which is required, at that same path inside the container and set
`LADO_REPOS` to it, and mount the home volume at `/home/lado`, and SHALL name no
container. Its header SHALL say to keep these variables in `.env` next to the file, that
`LADO_LISTEN=0.0.0.0` opens LADO to every device of the network with the token
travelling unencrypted, and that a second LADO is a folder of its own with a copy of the
file and its own `.env` (`COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_VERSION`,
`LADO_PROJECTS`), so it runs beside the first with a container, a volume and a version of
its own.

#### Scenario: Two LADOs on one host
- **WHEN** the human runs `docker compose up -d` in a folder whose `.env` has
  `LADO_VERSION`, and in a second folder whose `.env` adds `COMPOSE_PROJECT_NAME=lado-2`
  and `LADO_PORT=8766`
- **THEN** both run, `/api/health` answers on 8765 and on 8766, and each has its own home
  volume

#### Scenario: No projects folder given
- **WHEN** the human runs `docker compose up -d` without `LADO_PROJECTS`
- **THEN** compose refuses and names `LADO_PROJECTS`

#### Scenario: No version given
- **WHEN** the human runs `docker compose up -d` with neither `LADO_VERSION` nor
  `LADO_IMAGE`
- **THEN** compose refuses and names `LADO_VERSION`

#### Scenario: The published image by its version
- **WHEN** `.env` has `LADO_VERSION=0.39.0` and no `LADO_IMAGE`
- **THEN** `docker compose config` names the image `ghcr.io/ladohq/lado:0.39.0`

#### Scenario: The projects at the host's path
- **WHEN** the human runs `LADO_PROJECTS=/Users/me/projects docker compose up -d`
- **THEN** the container sees the projects at `/Users/me/projects` and `lado doctor` in it
  prints `[ok  ] Repositories folder: /Users/me/projects (LADO_REPOS)`

#### Scenario: Published to the network
- **WHEN** `.env` has `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=kaos-mbp.local`
- **THEN** `docker compose config` publishes `0.0.0.0:8765:8765` and gives the container
  `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=kaos-mbp.local`

#### Scenario: Published on this computer by default
- **WHEN** `.env` has neither `LADO_LISTEN` nor `LADO_PUBLIC_HOST`
- **THEN** `docker compose config` publishes `127.0.0.1:8765:8765` and gives the container
  `LADO_LISTEN=127.0.0.1`
