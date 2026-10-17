Task: LAD-94

## Why

Opening LADO on a phone, or giving it to a colleague, takes a terminal today. The human
runs `lado ui`, finds the line `From another machine`, or builds the link by hand from
the address and `~/.lado/server-token`. The UI's own Copy link copies an address without
the token, which another browser answers with 401.

Docker is the main way users install LADO, and there it does not work at all:
- compose publishes the port on the host's loopback only (`127.0.0.1:<port>:<port>`), so
  no other device reaches the server;
- the container cannot learn the host's address in its network. Its network is Docker's
  bridge (on a Mac also Docker Desktop's VM), its hostname is `lado`, and it cannot see
  how its port is published. That is why `lado ui` in a container prints no
  `From another machine` line.

There is also no way to take access back without restarting the server: only
`lado server --new-token` at a start makes a new token.

Root cause: who reaches the server, and by which address, is decided outside LADO (the
port's publication, the host's network). LADO is told neither, so it cannot build a link
for another device. The token lives in an HttpOnly cookie, which the UI cannot read to
build the link itself.

## What Changes

- **Two environment settings, no new file.**
  - `LADO_LISTEN` (compose's `.env`, default `127.0.0.1`) is the host address compose
    publishes the port on: `"${LADO_LISTEN:-127.0.0.1}:${LADO_PORT}:${LADO_PORT}"`.
    Compose also gives it to the container, so LADO in Docker knows for the first time
    whether other devices reach it.
  - `LADO_PUBLIC_HOST` (compose's `.env`, or the environment of `lado server` /
    `lado ui` without Docker) is the name or address other devices reach this computer
    by, e.g. `kaos-mbp.local`. It is used only to build the link.
- **One rule for the link to another device** (`run.Listening`), shared by the UI and by
  `lado ui`'s `From another machine` line:
  1. `LADO_PUBLIC_HOST` when set and the server is open to the network;
  2. otherwise the one non-loopback IPv4 address the server is published on (Docker:
     `LADO_LISTEN=192.168.1.23`; without Docker: `--host 192.168.1.23`);
  3. otherwise, for `0.0.0.0` outside a container, this machine's IPv4 address in its
     network, found by LADO (the route's source address);
  4. otherwise no link, with the reason: loopback only, or in a container open to the
     network with no `LADO_PUBLIC_HOST` (the host's address is unknown), or in a container
     whose publication is unknown (`docker run` without `LADO_LISTEN`).
- **The UI:** a QR-code icon left of the Server address in the system panel (under
  `live`, tooltip "Open on another device") opens the dialog "Open LADO on another
  device":
  - with a link: the warning (full access, plain HTTP, a trusted network only), a QR code
    of the link, the link with the token cut in the middle, and Copy link, which copies the
    full link;
  - without one: the reason and what to set (`.env` lines, or `--host 0.0.0.0` without
    Docker), text only, no field;
  - New link…, with a confirmation, in every state.
- **New link without a restart:** `POST /api/access/new-token` writes a new token, swaps
  it in the running server, ends every open event stream and terminal, and gives this
  browser the new cookie. Every other browser and phone is logged out at once.
- **`lado ui`** prints `From another machine: <link>` by the same rule, asking the
  running server (`GET /api/access`), in a container too (there on stderr with
  `--no-open`, so its standard output stays the one local link for launchers).
- **The server's start lines in a container** follow `LADO_LISTEN`: open to the network,
  the same warning as outside; loopback, no line; unknown, the note as today.
- **Docs:** docs/install.md gets "Open LADO on your phone", the compose header names both
  settings, docs/design/ui.md gets the dialog's section, docs/cli.md and
  docs/design/modules.md follow.
- **Version:** a minor (new API endpoints and settings); CHANGELOG under
  `0.41.0 (unreleased)`.

## Scope

- `src/lado/server/run.py`: `Listening` takes the settings and gives the link's base or
  the reason; the start lines in a container.
- `src/lado/server/auth.py`: an atomic new token and `Guard.renew`.
- `src/lado/server/app.py`, `models.py`: `GET /api/access`, `POST /api/access/new-token`.
- `src/lado/server/feed.py`, `terminals.py`: end the open streams and terminals on a new
  token.
- `src/lado/cli.py`: `lado ui`'s `From another machine` from the server.
- `web/`: the icon, the dialog (`Share.tsx`), the QR code (a small npm library), the API
  types.
- `docker/compose.yaml`: `LADO_LISTEN`, `LADO_PUBLIC_HOST`.
- Tests at each layer named in `design.md`; docs named above; CHANGELOG.md.

## Out of scope

- **A link per person, with revoking one person.** The human decided: no multi-user mode.
  There is one token; New link logs everyone out.
- **Typing the address in the UI, or keeping it on disk.** The human decided: settings
  come only from the environment (`.env`). The UI shows, it does not ask.
- **Restarting the server on another address from the UI.** The tab would lose its own
  server, and in Docker the publication is compose's. The dialog says what to run.
- **Checking that the link works** (that the port is really published, that the name
  resolves on the phone). LADO cannot see it from inside; the phone's scan shows it.
- **TLS and a real login.** They replace the token later (`auth.py`'s docstring).
- **IPv6.** The server refuses IPv6 addresses today.
- **The 401 page's text.** It keeps naming `lado ui`'s link.

## Impact

- With neither setting and the server on loopback (the default in and out of Docker),
  nothing changes but the new icon and dialog, which then show how to open LADO up.
- The token travels to the page in `GET /api/access` when there is a link. Only a page of
  the server's own origin with the cookie can read it (no CORS; a rebinding page has no
  cookie). It was in the page's address already when the human logged in.
- No schema change, no MCP tool change.
