# Trusting a git server's certificate: Implementation Plan

**Goal:** a saved git server can carry a trusted certificate, offered by Check and Add in the UI from the server's own chain or given as a file on the command line; git
(LADO's and agents') and LADO's API requests trust it for that server alone; changed and
unfixable certificates are told apart; the clone, doctor and the launch name it.

**Architecture:** a new module `git_certificates` reads the chain, finds the offer and checks
files (D4–D6, D10, `cryptography` D11); `git_servers` keeps `ca.pem` (D1), adds
`sslCAInfo` (D2), builds the TLS context (D3) and the outcomes (D7); the CLI's offer lines
(D9); the API's PUT/DELETE and offers (D8); the page's `TrustCard` and row (D14); clone,
doctor and the launch notes (D13).

**Tech Stack:** Python 3.10+ with `cryptography` (already installed), FastAPI/pydantic,
React + TypeScript, pytest (`-n auto`, `-m integration`, `-m ui`), vitest, Playwright's
Chromium, openssl for the tests' certificates (or `cryptography` in the test), git ≥ 2.31.

**Spec:** `openspec/changes/git-server-certificate/` and
`docs/superpowers/specs/2026-11-19-git-server-certificate-design.md` (texts, tests per
requirement, docs, manual check). Mockup: the run's `mockup-certificate.html`.

## Global Constraints

- No TLS check is ever turned off, anywhere; no `SSL_CERT_FILE`, `GIT_SSL_CAINFO` or
  `NODE_EXTRA_CA_CERTS` set by LADO; the computer's and the image's trust stores and the
  user's git configs unchanged.
- No token reaches the chain fetch or an AIA address.
- No schema change (D1, D12).
- The texts are the deltas' and the design doc's, word for word; another wording needs a
  reason in the build report.
- Tests use no network: local TLS servers under test CAs, no CA in the test processes'
  default trust (no `SSL_CERT_FILE`/`GIT_SSL_CAINFO` in the new tests).
- Nothing in code, docs, specs or the UI names the epic's stages or `docs/epics/`.
- CHANGELOG: extend 0.48.0 (unreleased).
- The pull request carries the design doc's manual check from the start.

## Review Focus

Risky: `git_certificates.py` (the private chain method on 3.10–3.12, the AIA walk's limits,
the signature checks), `git_servers._entries`/`variables` (every agent's launch), the TLS
context in `model_servers.ask_all`, `GitServers.tsx`'s new states and focus.

## Tasks

### Task 1: `git_certificates` and the dependency (D4, D5, D6, D10, D11)

Files: `src/lado/git_certificates.py` (new), `pyproject.toml`, `uv.lock`,
`tests/test_git_certificates.py` (new), `tests/certificates.py` (new helper: root,
intermediate, leaf, self-signed, CN-only, expired, built with `cryptography`).

- [ ] Test: a chain from an in-process TLS server (root sent, root not sent with AIA, no
  AIA, self-signed leaf); the offer and its fields; AIA asked once without token headers;
  limits (3 links, 64 KB, 5 s); no bytes written after the handshake.
- [ ] Test: a file's checks (none, expired, > 1 MB, chain kept, rewritten PEM only).
- [ ] Test: `get_unverified_chain` present on the running Python.
- [ ] Implement; `uv add cryptography` (the version the lock has).
- [ ] `make lint`, `uv run pytest -n0 tests/test_git_certificates.py`; commit.

### Task 2: the file of a server, git's entry, LADO's context (D1, D2, D3, D12)

Files: `src/lado/git_servers.py`, `src/lado/model_servers.py` (`context` of `ask_all`),
`tests/test_git_servers.py`, `tests/test_model_servers.py`.

- [ ] Test: `ca.pem` written 600 by rename, link refused, lado.db untouched, token
  replacement keeps it, remove takes it; `variables` with/without file; the probe trusts the
  file alone (fake API under CA A with file of CA B fails); the previous removal leaves the
  folder (D12).
- [ ] Implement; commit.

### Task 3: the check's outcomes and trusting (D6, D7, D8 server side)

Files: `src/lado/git_servers.py`, `src/lado/server/models.py`, `src/lado/server/app.py`,
`web/openapi.json`, `web/src/api.gen.ts`, `tests/test_git_servers.py`,
`tests/test_server_git_servers.py`.

- [ ] Test: `cert_untrusted` with an offer, `cert_changed` with `before`, `cert_name` (host,
  CN only), `cert_expired`; PUT saves and checks, DELETE answers the PEM, a second check
  offers again; the address check's offer; add with `certificate`.
- [ ] Implement; `make web-types`; commit.

### Task 4: the command line (D9, D10)

Files: `src/lado/cli.py`, `tests/test_cli_git_server.py`.

- [ ] Test: `add --certificate`, `certificate` set/show/clear/`-`, refusals and exit codes,
  `list`'s column, the offer's lines and hint on `check` and `add` (exit 1, nothing saved).
- [ ] Implement; commit.

### Task 5: clone, doctor, launch (D13)

Files: `src/lado/clone.py`, `src/lado/doctor.py`, `src/lado/runtime.py`, `web/src/Launch.tsx`
(only if the note needs a text), `tests/test_clone.py`, `tests/test_doctor.py`,
`tests/test_runtime_git_servers.py`.

- [ ] Test and implement `cert_untrusted` (saved, unsaved, server way), doctor's warn and
  `gh` info lines, the launch's `gh` note; commit.

### Task 6: the integration test (end to end, real git)

Files: `tests/integration/test_git_server_certificate.py` (new), `tests/fake_git_server.py`
if it needs a CA option.

- [ ] Without the certificate: LADO's clone fails with `cert_untrusted` and the check
  offers; with it (trusted through the API): LADO's clone and the fake agent's clone, commit,
  push (an ssh address too) pass; another host under the same CA refused; `~/.gitconfig`,
  the system config and `/etc/ssl` hashed before and after equal; a launch without `ca.pem`
  has no `sslCAInfo`.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_git_server_certificate.py
  tests/integration/test_git_server_access.py`; commit.

### Task 7: the page (D14)

Files: `web/src/GitServers.tsx`, `web/src/styles.css`, `web/src/GitServers.test.tsx`,
`tests/ui/test_git_servers_certificate.py` (new).

- [ ] vitest: each mockup state (§1–§12), focus after Trust, Don't trust, Remove, Undo.
- [ ] UI e2e: a real `lado server`, the fake API under a test CA nobody trusts: Check → card
  → Don't trust → mark → Check → Trust → Works and the row; Remove → Undo; Add with trust;
  screenshots at 1440 and 390 as run artifacts.
- [ ] `make web`, `uv run pytest -m ui tests/ui/test_git_servers_certificate.py
  tests/ui/test_git_servers_section.py`; commit.

### Task 8: docs and the regression run

- [ ] `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `docs/install.md`,
  AGENTS.md (Layout line), CHANGELOG.md (0.48.0, New).
- [ ] `make lint`, `make test`, the integration and UI files above, `make web`,
  `openspec validate git-server-certificate --strict`, the trial archive; commit.
- [ ] The pull request's manual check, each command checked against this branch.
