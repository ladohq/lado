## Context

- The token is one file, `LADO_HOME/server-token` (`auth.token`). `lado server --new-token`
  replaces it only at a start. `auth.token(new=True)` deletes the file, then creates it
  with `O_EXCL`; a `lado ui` that reads between the two makes a token of its own.
- `auth.Guard` keeps the token it was made with for the server's life. A browser holds it
  in the HttpOnly cookie `lado_token_<port>`; the UI's script cannot read it.
- `run.Listening.of(host, port, container)` decides `url` (from this machine), `remote`
  (from others: the hostname for `0.0.0.0`) and the start line (warning or container
  note). `lado ui` builds `From another machine` from it in its own process, not in the
  server's.
- In a container the image starts `lado server --host 0.0.0.0 --port $LADO_PORT`.
  Compose publishes `127.0.0.1:${LADO_PORT}:${LADO_PORT}`. The container's hostname is
  `lado`, and its network is Docker's bridge (on a Mac, inside Docker Desktop's VM): it
  can learn neither the host's address nor the publication.
- The change feed is one SSE stream per tab (`feed.Hub`). A stream that ends is reopened
  by the browser; one refused with 401 is shown as the server's message
  (`live.ts`, `diagnose`). A terminal is a WebSocket checked once, at its connect
  (`terminals.serve`).
- The system panel (`SystemPanel.tsx`) has a header with `LADO X.Y.Z`, the clipboard
  icon (copy system info) and the text link `GitHub ↗`; it shows `Server` as
  `window.location.origin`.

Root cause: who reaches the server, and by which address, is decided outside LADO (the
port's publication, the host's network), and LADO is told neither. So it cannot build the
link, and the UI cannot either, as it never sees the token.

## Options

**Where the link's address comes from** (asked of the human in three rounds):
1. **Two environment settings, `LADO_LISTEN` and `LADO_PUBLIC_HOST`** (chosen by the
   human). The first publishes the port in compose and tells the container what it did;
   the second names the host for the link. They are the one source, they keep in `.env`
   across updates, and the same rule serves the UI and `lado ui`. Long-term cost: two
   documented variables; a changed name means editing `.env` and `up -d`.
2. **`LADO_URL` alone**, the whole base URL. One variable, but the publication stays
   127.0.0.1, so the link would not work, and the port is written twice.
3. **The address typed in the UI, kept in `LADO_HOME`.** No restart to change it, but it
   is a second source beside the environment, and the human does not want settings kept on
   disk or a field to type in.
4. **The page's own origin.** Free, but useless on the host itself (127.0.0.1), which is
   where the human opens the dialog.

**How access is taken back:**
1. **One token, renewed in the running server** (chosen). No new state; everyone is
   logged out together. Long-term cost: none beyond this change; a real login replaces it.
2. **A token per person**, revoked one by one. The human decided against a multi-user
   mode; it would need a store, a list and rules for `lado ui`, all replaced by a later
   login.

**The QR code:**
1. **Made in the browser by a small npm library** (chosen). The wheel's users get it in
   the bundle; no Python dependency; the link never leaves the page.
2. **An SVG from the server (a Python library such as segno).** A runtime dependency of
   the wheel for one picture, against "standard library first".
3. **An encoder of our own.** Several hundred lines of Reed-Solomon and masks to keep, for
   no gain.

## Decisions

- **D1. The rule lives in `run.Listening`, and the server is its one judge.**
  - `Listening.of(host, port, container, env)` takes `LADO_LISTEN` and `LADO_PUBLIC_HOST`
    from `env` (the server's `os.environ`; tests pass a dict). It adds `reason` (`loopback`,
    `no-address`, `unknown`, or None) and keeps `url`, `remote` (now the base
    `http://<address>:<port>`, None with a reason), `warning` and `note`.
  - The rule is the spec's table (share-access, "The link to another device follows one
    rule").
  - `lado ui` no longer builds `remote` itself. It asks `GET /api/access` with
    `Authorization: Bearer <token>`. The server's environment then decides, not that of
    whatever shell runs `lado ui`.
  - An older server (no `/api/access`, 404) gets no `From another machine` line; `lado ui`
    restarts a server of another version anyway, so this is only the moment of an upgrade.
  - Why: one source of truth.
- **D2. This machine's address: the source address of a route, found per call.**
  - `run.network_address()` opens a UDP socket, `connect`s it to a TEST-NET address
    (`192.0.2.1:9`; UDP's connect sends nothing), and reads `getsockname()`.
  - A loopback, unspecified or failing result falls back to `socket.gethostname()`, today's
    behaviour.
  - It runs at every `/api/access`, so a new DHCP address shows without a restart.
  - Why: the standard library; the address a phone on the same network reaches. A
    hostname often does not resolve on a phone.
- **D3. `LADO_PUBLIC_HOST` is checked once, at the server's start.**
  - Valid: `^[A-Za-z0-9.-]{1,253}$`, not starting or ending with `.` or `-`.
  - Invalid: the start's warning line (spec), and it counts as unset. `Listening.of`
    returns the warning in a list `problems` that `serve` prints, so nothing is dropped
    silently.
- **D4. `LADO_LISTEN` is read only in a container.**
  - Outside a container, `--host` is the publication itself, so the variable is ignored
    there. `lado doctor` says nothing about it.
  - In a container a value that is not an IPv4 address (a name, IPv6) counts as unknown:
    compose itself refuses a name at `up`.
- **D5. `GET /api/access` answers `AccessInfo`, and the link holds the token only when
  there is one.**
  - Fields: `link: str | None`, `reason: Literal["loopback", "no-address", "unknown"] |
    None`, `port: int`, `container: bool`, `listen: str | None`, `note: str | None` (the
    container note's text for `unknown`, so the UI shows the CLI's words).
  - Under `Depends(guard)`, not `guard.changes`: a same-origin `GET` from `fetch` carries
    no Origin in every browser. A page of another origin cannot read the answer (no CORS),
    and a DNS-rebinding page has no cookie.
  - The answer has `Cache-Control: no-store`.
- **D6. A new token in a running server.**
  - `auth.token(new=True)` writes the value to `server-token.tmp` (`O_CREAT|O_EXCL`,
    0600, a stale tmp removed first), then `os.replace`s it. A reader sees the old file or
    the new one, never none.
  - `Guard.renew()` makes it and swaps `self.token`. FastAPI handlers run in one process;
    a request in flight checked before the swap finishes with the old token, which is
    harmless.
  - `POST /api/access/new-token` (`guard.changes`) then:
    1. ends the open change-feed streams with `Hub.end_streams()`, which sends the end to
       every queue but leaves the hub open (unlike `close`);
    2. closes the open terminal sockets through a registry in `terminals` (a set of open
       WebSockets, added after `accept`, removed in `finally`), with code `ENDED` (4500);
       the browser reopens, and its connect is checked against the new token, so another
       browser gets 4401;
    3. answers `AccessInfo` with `Set-Cookie` of the new token (the same attributes as
       `Guard.login`).
  - This tab's EventSource reopens with the new cookie. Others reopen, get 401, and show
    the server's message.
  - `lado server --new-token` stays as it is.
- **D7. The UI.**
  - `web/src/Share.tsx` holds `ShareButton` (the icon, first of the panel header's
    `system-links`, chosen by the human: mockup option И3) and `ShareDialog` (a `<dialog>`
    with `question-dialog`, like `UpdateDialog`).
  - The header's `GitHub ↗` becomes an icon link (the human's ask): `GitHubIcon`, the
    GitHub mark as GitHub publishes it for linking to GitHub, in `currentColor`; an
    `icon-button` styled `<a>`, `target="_blank" rel="noreferrer"`, label and tooltip
    `LADO on GitHub`. Order: QR, clipboard, GitHub.
  - `QrIcon` and `GitHubIcon` go in `icons.tsx`.
  - API: `getAccess()` and `newAccessToken()` in `api.ts`; types from `make web-types`.
  - The QR code is drawn as an SVG in the page from the full link (D8).
  - The token is cut by `cutToken(link)`: `token=` followed by its first 4 characters,
    `…`, its last 4.
  - Texts are the mockup's (`mockup-share-access.html`, section 1 and 2a–2d),
    listed in the design doc.
  - The system panel stays open behind the dialog, as with Update….
- **D8. The QR library: `qrcode-generator` (MIT, no dependencies), at an exact version.**
  - Error correction M; `createSvgTag` is not used. The component draws `<rect>`s from
    `getModuleCount`/`isDark`, so colours come from the page: black on white in both
    themes, as phones need.
  - Why: small, long-lived, no transitive dependencies. Another library of the same kind
    is acceptable if it has no dependencies; the developer names it in the build report.
- **D9. Compose and the image.**
  - compose: `ports: ["${LADO_LISTEN:-127.0.0.1}:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]`;
    `environment` adds `LADO_LISTEN: ${LADO_LISTEN:-127.0.0.1}` and
    `LADO_PUBLIC_HOST: ${LADO_PUBLIC_HOST:-}`.
  - The header documents both.
  - The Dockerfile sets neither: `docker run` without them stays `unknown`, today's note.
  - An empty `LADO_PUBLIC_HOST` counts as unset.
- **D10. Tests by layer** (AGENTS.md, Testing).
  - Unit:
    - the rule's table and the address fallback (`tests/test_server.py`, `Listening`);
    - the atomic token and `Guard.renew`;
    - `/api/access` in each state, 401, `no-store`, no token without a link;
    - `/api/access/new-token`: the cookie, old cookie and Bearer 401, 403 from another
      Origin, streams ended, the terminal registry closed;
    - `lado ui`'s lines with a faked server answer (`tests/test_cli*.py`);
    - compose (`tests/test_docker.py`);
    - the start lines in a container.
  - vitest: `Share.tsx` in each state, `cutToken`, the confirmation, a QR code that is
    there for a link and absent without.
  - Integration (`tests/integration/test_server_process.py`, crosses processes): a real
    `lado server --host 0.0.0.0` with `LADO_PUBLIC_HOST`; `lado ui --no-open` prints
    `From another machine` from the server's environment, not its own; a new token over
    HTTP makes the old cookie 401 and ends an open event stream.
  - UI e2e (`tests/ui/test_share_access.py`): the icon opens the dialog; the QR code is
    there; Copy link copies the full link; New link… keeps this page live while a second
    browser context gets the 401 message; a screenshot of each state.
  - Container (`tests/container/test_access.py`): with `LADO_LISTEN=0.0.0.0` and
    `LADO_PUBLIC_HOST=lado-test.local`, `lado ui --no-open` keeps one stdout line and has
    the remote line on stderr.
- **D11. Version: minor.** New API endpoints, new settings, a changed `lado ui` output.
  CHANGELOG under `## 0.41.0 (unreleased)`.

## Held against the roadmap and the principles

- Neutral core: nothing here touches providers or agents.
- One source of truth: the server's environment decides the link; `lado ui` asks the
  server; nothing is kept beside `server-token`.
- No silent drops: an invalid `LADO_PUBLIC_HOST` warns; no link always says why.
- Only what is used: no per-person tokens, no address field, no restart from the UI.
- Roadmap: stage 7's local web UI and the desktop app. A real login with TLS replaces the
  token later; this change adds no state that would need migrating then.

## Risks

- The token now reaches the page's script when there is a link. An XSS in the UI could
  read it and keep access after the tab closes. It could already act with the cookie
  while the tab was open; New link takes the token back.
- `LADO_LISTEN=0.0.0.0` on a laptop opens LADO on every network it joins. The header,
  the guide and the dialog say so.
