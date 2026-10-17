# Open LADO on another device: design

Task LAD-94. Change `openspec/changes/share-access-link/` (proposal, specs `share-access`
and `container`, `design.md` with decisions D1–D11). Mockup: run artifact
`task/lad-94/mockup-share-access.html`, approved: section 1 (option И3: the icons in
the panel's header, GitHub as an icon) and sections 2a–2d.

## What the human gets

In the UI: `live` (top right) → the QR-code icon in the panel's header → the dialog
"Open LADO on another device", with a QR code to scan and Copy link. New link… logs out
everyone who opened LADO with the old link; this browser stays in.

In Docker, once, two lines in `.env` next to `compose.yaml`, then `docker compose up -d`:

```
LADO_LISTEN=0.0.0.0              # let other devices of the network in
LADO_PUBLIC_HOST=kaos-mbp.local  # this computer's name, for the link
```

Or one address instead of both: `LADO_LISTEN=192.168.1.23`. Without Docker:
`lado ui --host 0.0.0.0`; the name is optional there, as LADO finds the address itself.

## The rule for the address

The spec's table (share-access, "The link to another device follows one rule") is the
whole rule. Summary:
- outside a container: loopback → none; `0.0.0.0` → `LADO_PUBLIC_HOST`, else this
  machine's address in its network (D2), else its hostname; another address →
  `LADO_PUBLIC_HOST`, else that address;
- in a container, by `LADO_LISTEN`: loopback → none; `0.0.0.0` → `LADO_PUBLIC_HOST`, else
  none (`no-address`); another IPv4 → `LADO_PUBLIC_HOST`, else it; unset or not IPv4 →
  `LADO_PUBLIC_HOST`, else none (`unknown`).

## Server

- `run.Listening.of(host, port, container, env=os.environ)` gains:
  - `reason: str | None`;
  - `problems: list[str]` (the invalid `LADO_PUBLIC_HOST` warning);
  - `remote` keeps its meaning, the base URL for other devices, now by the rule.
- `run.network_address() -> str | None` (D2).
- `run.public_host(env) -> tuple[str | None, str | None]`: the valid host, or None with
  the warning (D3).
- `auth.token(new=True)` atomic; `Guard.renew() -> str` (D6).
- `feed.Hub.end_streams()`; `terminals.close_all(code, reason)` with an open-socket
  registry (D6).
- `models.AccessInfo`; `GET /api/access`; `POST /api/access/new-token` (D5, D6).
- `cli._ui`: after the local link, `GET /api/access` with Bearer, then
  `From another machine: <link>` where the spec says, and nothing on a 404 or a network
  error (D1).
- `serve`: prints `Listening.problems` as `lado: warning: …` lines, then the warning or
  note as now.

## UI

Files: `web/src/Share.tsx` (new), `SystemPanel.tsx` (the header's icons), `icons.tsx`
(`QrIcon`, `GitHubIcon`), `api.ts`, `api.gen.ts` and `openapi.json` (`make web-types`), `styles.css`
(the dialog's QR layout, from the mockup's `.mk-share-body`, `.mk-linkcol`, `.mk-link`,
`.mk-warn` under real names: `.share-body`, `.share-link`, `.share-warning`),
`package.json` (`qrcode-generator`, exact version).

The panel's header: `LADO X.Y.Z` (and its pills), then the icons QR, clipboard, GitHub.

Texts, exactly:
- QR icon: aria-label and tooltip `Open on another device`;
- GitHub icon: aria-label and tooltip `LADO on GitHub` (it replaces the text `GitHub ↗`);
- title: `Open LADO on another device`;
- warning: `This link gives full access: sessions, agents' terminals, commands as you. It
  travels unencrypted (plain HTTP): share it only on a network you trust.` (`full access`
  in bold);
- beside the QR code: `Scan it with the phone's camera, or send the link.`, the cut link,
  `Copy link` (copied note: `Link copied`);
- under it: `Anyone who opened LADO with this link stays in until you make a new one.`;
- `loopback` outside a container: `This LADO server listens on 127.0.0.1 only: other
  devices cannot reach it.` / `To open it from a phone or another computer on your
  network, restart the server open to the network:` / the command
  `lado server stop && lado ui --host 0.0.0.0` with `Copy command` / `The sessions keep
  running; open tabs reconnect.`;
- `loopback` in a container: `LADO is reachable from this computer only (its port is
  published on 127.0.0.1).` / `To open it from a phone or another computer on your
  network, set in .env next to compose.yaml, then run docker compose up -d:` /
  `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=<this computer's name>` with `Copy lines`;
- `no-address`: `LADO is open to your network (LADO_LISTEN=<listen>), but inside its
  container it cannot learn this computer's address for the link.` / `Set the name or
  address other devices reach this computer by in .env, then run docker compose up -d:` /
  `LADO_PUBLIC_HOST=<this computer's name>` / `Or publish on one address instead:
  LADO_LISTEN=<address>.`;
- `unknown`: `AccessInfo.note`;
- buttons: `New link…`, `Close`;
- confirmation: `Make a new link?` / `Everyone who opened LADO with the current link —
  other browsers, phones, people you sent it to — is logged out at once. This browser
  stays in.` / `The same as lado server --new-token, without a restart.` / `Cancel`,
  `Make a new link` (class `danger`);
- a failed request: the API's message in `.problem`, as `UpdateDialog` does.

The QR code: 180 px square, black modules on white with a 4-module quiet zone, in both
themes; `role="img"`, `aria-label="QR code of the link"`.

## Docs

- `docs/design/ui.md`: the System panel's P1 bullet names the three header icons in place of
  `GitHub ↗`; the section `### Open on another device (decided 2026-10-18,
  LAD-94)` after System panel. The Server section's Host and Token bullets name
  `/api/access`, the new token in a running server, and `LADO_LISTEN`/`LADO_PUBLIC_HOST`.
- `docs/install.md`: under Docker, `### Open LADO on your phone` after "Your first
  session". The `.env` example names both variables, commented out (the guide's test wants
  every variable compose reads named).
- `docker/compose.yaml`'s header: both variables, and that `0.0.0.0` opens LADO to every
  device of the network with the token unencrypted.
- `docs/cli.md`: `lado ui`'s `From another machine`; `docs/design/modules.md`: `run.py`,
  `auth.py`.
- CHANGELOG `## 0.41.0 (unreleased)`: one line.

## Tests

Listed by layer in `design.md`, D10; the plan names each test.
