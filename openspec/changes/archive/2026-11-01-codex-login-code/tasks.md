Each task names its checks; UI work follows the mockup `mockup-login-no-terminal.html` of
run task/lad-168.

## 1. Provider

- [x] 1.1 `base.LoginPrompt`, `Provider.login_prompt` (default None), `LoginAction.shows_code`;
  Codex's `login_prompt` on its real 0.162.0 output, its `login` action `shows_code` (D1, D2).
  Check: `tests/test_login_status.py` (the real output with and without colours and wrapped
  lines, a partial output, a non-https link, the warning and expiry lines),
  `tests/test_providers.py`.

## 2. Core and server

- [x] 2.1 Login windows with `remain-on-exit`; a dead window counts as ended in
  `open_windows`' callers; its text and status read before it is killed (D3). Check:
  `tests/test_logins.py`, `tests/test_terminal.py`.
- [x] 2.2 The login socket's `prompt` and `ended` frames (D4). Check:
  `tests/test_terminal_socket.py`, `tests/test_server_providers.py`.
- [x] 2.3 Across processes with a fake login command that prints Codex's text and exits
  non-zero at once: the `prompt` frame, then `ended` with its last line; a command that
  exits 0 closes with status 0; a command with unknown text sends no `prompt`. Check: `uv
  run pytest -m integration tests/integration/test_provider_logins.py`.
- [x] 2.4 `make web-types` for `LoginAction.shows_code`. Check: `make web`.

## 3. Web UI

- [x] 3.1 `LoginWindow.tsx` to the mockup: waiting, the two steps with Open, Copy code and
  the QR code (none at a phone's width), Codex's lines, the failure view with Get a new code
  and Back, the fallback after 10 s with the terminal, the field and the keys; the shared
  QR component (D5, D6, D7). Check: `web/src/LoginSheet.test.tsx` (or a new
  `LoginWindow.test.tsx`: each state, Copy through the legacy copy without
  `navigator.clipboard`, the fallback timer), `web/src/Share.test.tsx`, `make web`.
- [x] 3.2 UI e2e, desktop and phone, with screenshots of each state: the code shown, Copy
  code puts it on the clipboard, Open's href and target, no QR on a phone, the failure view.
  Check: `uv run pytest -m ui tests/ui/test_providers_section.py`.

## 4. Docs and release

- [x] 4.1 docs/design/ui.md (The login window: Codex's window without a terminal, its
  states and fallback), docs/design/modules.md (`logins`, the Codex provider), CHANGELOG.md:
  the 0.44.0 line "Codex agents share your Codex login" says the sign-in code is shown with
  Copy and Open. Check: `make lint`, `make test`.
- [x] 4.2 By hand: Codex's real `--device-auth` in LADO's image, the code copied and the link
  opened on a computer and on a phone over the LAN by http; the regression run of the
  settings' Checks. Check: the build report names the result. Done in LADO's container
  with Codex 0.162.0 through a real `lado server` on 0.0.0.0, opened by Chromium at the
  container's LAN address over plain http (no Clipboard API), at a phone's and a computer's
  width: the code shown in 0.8 s, Copy code pasted back exactly, Open reached OpenAI's
  sign-in page. Not done: a physical phone, and a real Codex failure (its code expires
  after 15 minutes); the fake's failure covers the latter in the UI e2e.
