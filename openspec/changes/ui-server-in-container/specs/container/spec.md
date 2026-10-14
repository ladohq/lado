## ADDED Requirements

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
