The plan with each task's tests: `docs/superpowers/plans/2026-11-19-git-server-certificate.md`.

## 1. The certificates module

- [x] 1.1 `git_certificates`: the chain from a bare handshake, the offer (root, AIA,
  intermediate, own), the check that it works, a file's checks; `cryptography` declared (D4,
  D5, D6, D10, D11). Check: `tests/test_git_certificates.py` (no token sent, AIA limits, the
  private chain method on this Python).

## 2. A server's certificate

- [x] 2.1 `ca.pem` in the server's folder, kept on a token replacement, removed with the
  server; `http.<address>/.sslCAInfo`; LADO's requests trust it alone (D1, D2, D3, D12).
  Check: `tests/test_git_servers.py` (the context goes into `git_servers`' own opener, so
  `model_servers` and its tests are unchanged).
- [x] 2.2 The check's outcomes `cert_untrusted` with an offer, `cert_changed`, `cert_name`,
  `cert_expired`; PUT and DELETE of a server's certificate; the address check's offer; add
  with a certificate; `make web-types` (D6, D7, D8). Check: `tests/test_git_servers.py`,
  `tests/test_server_git_servers.py`; `make web`.

## 3. The command line

- [x] 3.1 `add --certificate`, `lado git-server certificate`, `list`'s column, the offer's
  lines on `check` and `add` (D9). Check: `tests/test_cli_git_server.py`.

## 4. Clone, doctor, launch

- [x] 4.1 The clone's `cert_untrusted` and its way out; doctor's lines; the launch's `gh` note
  (D13). Check: `tests/test_clone.py`, `tests/test_doctor.py`, `tests/test_runtime_git_servers.py`.

## 5. End to end

- [x] 5.1 Integration with a local https git server under a test CA nobody trusts: LADO's and
  the fake agent's clone and push with the certificate, refused without it, another host
  refused, configs and trust stores unchanged, no `sslCAInfo` without `ca.pem`. Check:
  `uv run pytest -m integration tests/integration/test_git_server_certificate.py`.

## 6. The page

- [x] 6.1 The trust card, the changed card, Add's question, the Certificate row with Remove
  and Undo, the Remove server text (D14). Check: vitest `GitServers.test.tsx`; UI e2e
  `tests/ui/test_git_servers_certificate.py` with screenshots at 1440 and 390.

## 7. Docs and the regression run

- [x] 7.1 `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `docs/install.md`,
  AGENTS.md's Layout, CHANGELOG.md's 0.48.0. Check: `make lint`, `make test`, the
  integration and UI files, `make web`, `openspec validate git-server-certificate --strict`,
  the trial archive.
- [x] 7.2 The pull request's manual check, each command checked against this branch.
