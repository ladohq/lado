Tests first in each section; each section is one commit. The plan with the code is
`docs/superpowers/plans/2026-10-18-share-access.md`.

## 1. The rule for the link's address

- [x] 1.1 Unit tests (layer 1), `tests/test_server.py`: each row of the rule's table, the
  address and hostname fallbacks, an invalid or empty `LADO_PUBLIC_HOST`, the start lines
  in a container by `LADO_LISTEN`. Plan, Task 1.
- [x] 1.2 `run.network_address`, `run.public_host`, `Listening.of(..., env)` with
  `reason`, `problems`, `listen`; `serve` prints the problems (D1–D4).
  `uv run pytest tests/test_server.py -n auto`.

## 2. A new token in a running server

- [x] 2.1 Unit tests, `tests/test_server.py`: the file replaced whole (never missing),
  0600, a stale tmp, `Guard.renew`. Plan, Task 2.
- [x] 2.2 `auth.token(new=True)` atomic, `Guard.renew`, `Guard.set_cookie` (D6).
  `uv run pytest tests/test_server.py -n auto`.

## 3. The API

- [x] 3.1 Unit tests, `tests/test_server_access.py`, and the feed's and terminals' tests:
  401, the link and `no-store`, no token without a link, each reason, the new token's
  cookie, old cookie and Bearer 401, two in a row, 403 from another Origin, streams and
  terminals ended. Plan, Task 3.
- [x] 3.2 `AccessInfo`, `GET /api/access`, `POST /api/access/new-token`,
  `Hub.end_streams`, `terminals.close_all` (D5, D6); `make web-types` and commit both
  files. `uv run pytest tests/test_server_access.py -n auto`, `make web`.

## 4. lado ui asks the server

- [x] 4.1 Unit tests of `lado ui`: the remote line's stream outside and in a container,
  no line when the server does not answer. Integration (layer 2,
  `tests/integration/test_server_process.py`): the line comes from the server's
  environment, not the shell's; a new token ends an open event stream and the old
  cookie. Plan, Task 4.
- [x] 4.2 `server_run.access` and `cli._ui` (D1).
  `uv run pytest -m integration -n auto tests/integration/test_server_process.py`.

## 5. Compose and the install guide

- [x] 5.1 Unit tests, `tests/test_docker.py`: ports on `LADO_LISTEN`, the environment's
  six names, the header, the guide's `.env` and its section. Container (layer 7,
  `tests/container/test_access.py`): `lado ui --no-open` with both settings. Plan, Task 5.
- [x] 5.2 `docker/compose.yaml` (D9), `docs/install.md` `### Open LADO on your phone`.
  `uv run pytest tests/test_docker.py -n auto`; the container test in CI.

## 6. The dialog

- [x] 6.1 vitest, `web/src/Share.test.tsx` and `SystemPanel.test.tsx` (the header's
  icons in order, no `GitHub ↗`): `cutToken`, each state, Copy link, New link's
  confirmation and refusal, the QR code's modules. Plan, Task 6.
- [x] 6.2 `qrcode-generator` (exact version), `Share.tsx`, `QrIcon`, `GitHubIcon`, the
  panel header's three icons, `api.ts`, styles (D7, D8), to the approved mockup (section
  1 option И3, 2a–2d).
  `cd web && npx vitest run`, `make web`.

## 7. UI end to end

- [x] 7.1 `tests/ui/test_share_access.py` (layer 4): the dialog with a link, Copy link,
  New link with a second context logged out, loopback, no-address; a screenshot of each,
  attached as run artifacts. `uv run pytest -m ui -n0 tests/ui/test_share_access.py`.
  Plan, Task 7.

## 8. Docs

- [ ] 8.1 `docs/design/ui.md` (the new section, Server's Host and Token), `docs/cli.md`,
  `docs/design/modules.md`, `auth.py`'s docstring, CHANGELOG `0.41.0 (unreleased)`.
  Plan, Task 8.

## 9. Regression run

- [ ] 9.1 `make lint`; `make test`; the integration and UI files above with their
  markers; `make web`; `openspec validate share-access-link --strict`;
  `openspec validate --specs --strict`.
