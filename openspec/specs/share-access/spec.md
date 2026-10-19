# share-access Specification

## Purpose
How the human opens LADO on another device (a phone, a colleague's computer): one rule
builds the link with the token from where the server is published and `LADO_PUBLIC_HOST`
(or says why there is none), the system panel shows it with a QR code to the token's
holder only, `lado ui` prints it by the same rule, and New link makes a new token that
logs every other browser out without a restart.

## Requirements

### Requirement: The link to another device follows one rule

LADO SHALL build the link another device opens LADO with, `http://<address>:<port>/?token=<token>`,
by one rule (`run.Listening`), the same for the UI and for `lado ui`. `<port>` SHALL be the
port the server listens on. The settings (`LADO_LISTEN`, `LADO_PUBLIC_HOST`) SHALL be read from the server's environment only; LADO SHALL keep neither of
them on disk. This machine's address SHALL be found anew for each answer, so a changed
address shows without a restart.

#### Scenario: A changed address
- **WHEN** a server on `0.0.0.0` outside a container without `LADO_PUBLIC_HOST` runs, and
  the machine's address in its network changes from 192.168.1.23 to 192.168.1.40
- **THEN** the next answer's link names 192.168.1.40, without a restart

### Requirement: Outside a container the link's address follows where the server is published

Outside a container, `<address>` SHALL be, or the link SHALL be none with its reason:

| Published on | `LADO_PUBLIC_HOST` set | not set |
|---|---|---|
| a loopback address (`--host`) | none: `loopback` | none: `loopback` |
| `0.0.0.0` | it | this machine's IPv4 address in its network; when LADO cannot find one, its hostname |
| another address | it | that address |

#### Scenario: Without Docker on every address
- **WHEN** `lado server --host 0.0.0.0` runs outside a container without `LADO_PUBLIC_HOST`
  on a machine whose address in its network is 192.168.1.23
- **THEN** the link is `http://192.168.1.23:<port>/?token=<token>`

#### Scenario: Without Docker on loopback
- **WHEN** the server listens on 127.0.0.1 outside a container
- **THEN** there is no link, and the reason is `loopback`

### Requirement: In a container the link's address follows LADO_LISTEN

In a container, `<address>` SHALL be, or the link SHALL be none with its reason:

| Published on | `LADO_PUBLIC_HOST` set | not set |
|---|---|---|
| `LADO_LISTEN` a loopback address | none: `loopback` | none: `loopback` |
| `LADO_LISTEN=0.0.0.0` | it | none: `no-address` |
| `LADO_LISTEN` another IPv4 address | it | that address |
| `LADO_LISTEN` unset or not an IPv4 address | it | none: `unknown` |

#### Scenario: Docker with a host name
- **WHEN** the container has `LADO_LISTEN=0.0.0.0`, `LADO_PUBLIC_HOST=kaos-mbp.local` and
  listens on 8765
- **THEN** the link is `http://kaos-mbp.local:8765/?token=<token>`

#### Scenario: Docker published on one address
- **WHEN** the container has `LADO_LISTEN=192.168.1.23` and no `LADO_PUBLIC_HOST`
- **THEN** the link is `http://192.168.1.23:8765/?token=<token>`

#### Scenario: Docker open to the network without a name
- **WHEN** the container has `LADO_LISTEN=0.0.0.0` and no `LADO_PUBLIC_HOST`
- **THEN** there is no link, and the reason is `no-address`

#### Scenario: Docker on this computer only
- **WHEN** the container has `LADO_LISTEN=127.0.0.1` and `LADO_PUBLIC_HOST=kaos-mbp.local`
- **THEN** there is no link, and the reason is `loopback`

#### Scenario: docker run without LADO_LISTEN
- **WHEN** the container has neither `LADO_LISTEN` nor `LADO_PUBLIC_HOST`
- **THEN** there is no link, and the reason is `unknown`

### Requirement: LADO_PUBLIC_HOST is a host or it is refused loudly

`LADO_PUBLIC_HOST` SHALL be a host name or an IPv4 address: letters, digits, `.` and `-`,
at most 253 characters. Any other value (a scheme, a port, a path, a space) SHALL count as
unset, and the server SHALL print at its start, on stderr (so in `server.log` and `docker
logs` too), `lado: warning: LADO_PUBLIC_HOST is not a host name or address: <value>; the
link for other devices does not use it`.

#### Scenario: A URL instead of a name
- **WHEN** the server starts with `LADO_PUBLIC_HOST=http://kaos-mbp.local:8765`
- **THEN** it prints the warning naming the value, and the link is built as if it were
  unset

### Requirement: GET /api/access gives the link to the token's holder only

`GET /api/access` SHALL need the token (the cookie or a Bearer token) and SHALL answer
`AccessInfo`: `link` (the full link, or null), `reason` (`loopback`, `no-address`,
`unknown`, or null with a link), `port`, `container`, `listen` (`LADO_LISTEN` as the
container has it, or null) and `note` (the container note's text for `unknown`, else
null). Without a link the answer SHALL hold no token.

#### Scenario: Without the token
- **WHEN** a request without the cookie or a Bearer token asks `GET /api/access`
- **THEN** it is answered 401

#### Scenario: On loopback
- **WHEN** the server on 127.0.0.1 is asked with the token
- **THEN** `link` is null, `reason` is `loopback`, and the body does not contain the token

### Requirement: The access answer is never cached nor read by another origin

The answer of `GET /api/access` SHALL
carry `Cache-Control: no-store`, and the server SHALL send no CORS header, so a page of
another origin cannot read it.

#### Scenario: The answer's headers
- **WHEN** `GET /api/access` is answered with the token
- **THEN** the answer carries `Cache-Control: no-store` and no `Access-Control-Allow-Origin`
  header

### Requirement: A new link logs everyone else out without a restart

`POST /api/access/new-token`, under the token and the server's own Origin
(`Guard.changes`), SHALL replace the token in `LADO_HOME/server-token` (owner only, written
whole and then moved into place, so a reader never sees it missing or half written) and in
the running server at once. From then on the old token SHALL be refused (401, a terminal 4401), and
`lado ui` SHALL print links with the new one. The same SHALL hold in every state of the
link, also with no link.

#### Scenario: From another page
- **WHEN** `POST /api/access/new-token` comes with the cookie and an Origin that is not the
  server's
- **THEN** it is answered 403 and the token stays

### Requirement: A new link ends the old token's streams and terminals

`POST /api/access/new-token` SHALL end every open event stream and every open terminal
connection, and answer with the new cookie for the browser that asked and the new
`AccessInfo`.

#### Scenario: Another browser is logged out
- **WHEN** browser A and phone B are logged in, and A makes a new link
- **THEN** A's next request passes with the cookie it got in the answer, B's next request
  is answered 401, and B's open change feed has ended

#### Scenario: A terminal of the old token
- **WHEN** a terminal is open in B as A makes a new link
- **THEN** B's terminal connection is closed, and its reconnection is refused with 4401

### Requirement: The system panel opens the dialog for another device

The system panel's header SHALL hold, after `LADO X.Y.Z`, three icon buttons in this
order: a QR code (tooltip and label "Open on another device"), the clipboard that copies
the system info (as before), and the GitHub mark, a link to LADO's repository in a new tab
(tooltip and label "LADO on GitHub") in place of the text link `GitHub ↗`. The QR code
opens the dialog "Open LADO on another device", which
reads `GET /api/access` each time it opens.

#### Scenario: The panel's header
- **WHEN** the human opens the system panel
- **THEN** its header shows the QR-code, clipboard and GitHub icons in this order, and no
  text `GitHub ↗`

### Requirement: The dialog for another device shows the link with its warning

The dialog "Open LADO on another device" SHALL show:
- with a link: the warning that the link gives full access (sessions, agents' terminals,
  commands as the human) and travels unencrypted (plain HTTP), so it is for a trusted
  network only; a QR code of the full link, made in the browser; the link with the token
  cut to its first and last four characters around `…`; and Copy link, which copies the
  full link.
The dialog SHALL have no field to type an address.

#### Scenario: Scan from a phone
- **WHEN** the human opens the dialog on a server with a link
- **THEN** it shows the warning, a QR code that decodes to the full link, the link with
  its token cut, and Copy link puts the full link on the clipboard

### Requirement: The dialog says how to publish LADO on loopback

The dialog "Open LADO on another device" SHALL show:
- `loopback` outside a container: that other devices cannot reach this server, and the
  command `lado server stop && lado ui --host 0.0.0.0` with a copy button;
- `loopback` in a container: that LADO is published for this computer only, and the
  `.env` lines `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=<this computer's name>` with
  `docker compose up -d`.

#### Scenario: A server on loopback
- **WHEN** the human opens the dialog on a server on 127.0.0.1 outside a container
- **THEN** it shows no QR code and no link, and the command `lado server stop && lado ui
  --host 0.0.0.0` with a copy button

### Requirement: The dialog says why a container has no link

The dialog "Open LADO on another device" SHALL show:
- `no-address`: that LADO cannot learn this computer's address inside its container, and
  the `.env` line `LADO_PUBLIC_HOST=<this computer's name>` (or one address in
  `LADO_LISTEN`) with `docker compose up -d`;
- `unknown`: the container note, as the server prints it.

#### Scenario: Docker open to the network without a name
- **WHEN** the human opens the dialog and the reason is `no-address`
- **THEN** it shows no QR code and no link, and names `LADO_PUBLIC_HOST` in `.env`

### Requirement: The dialog makes a new link on the human's yes

The dialog "Open LADO on another device" SHALL show:
- in every state New link…, which asks first ("Make a new link?", that everyone who
  opened LADO with the current link is logged out at once and this browser stays in) and
  then shows the new link.

#### Scenario: New link keeps this tab
- **WHEN** the human confirms New link…
- **THEN** the dialog shows the new link, and the page keeps working (`live` comes back)

### Requirement: lado ui prints the link for another device by the same rule

`lado ui` SHALL take the link for another device from the running server
(`GET /api/access` with the token) and print `From another machine: <link>` when there is
one. Outside a container it SHALL be printed on standard output after the local link, as
before; in a container on standard output without `--no-open`, and on stderr with
`--no-open`, so that standard output stays the one local link. Without a link it SHALL
print no such line.

#### Scenario: Docker with a host name
- **WHEN** `docker compose exec lado lado ui --no-open` runs with `LADO_LISTEN=0.0.0.0`
  and `LADO_PUBLIC_HOST=kaos-mbp.local`
- **THEN** standard output is exactly `http://127.0.0.1:8765/?token=<token>`, and stderr
  has `From another machine: http://kaos-mbp.local:8765/?token=<token>`

#### Scenario: Without Docker on every address
- **WHEN** `lado ui --no-open` runs against a server on `0.0.0.0` outside a container
- **THEN** it prints the local link, then `From another machine: http://<address>:<port>/?token=<token>`
  with the address the rule gives
