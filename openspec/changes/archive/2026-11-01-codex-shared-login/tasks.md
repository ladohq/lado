The plan with each task's tests: `docs/superpowers/plans/2026-10-31-codex-shared-login.md`.

## 1. Core

- [x] 1.1 `Provider.needs_login(env)`; `logins.refusal`, `logins.read` (`Login.needs_login`),
  `runtime._held_for_login`, `doctor.login_check`, `server.launch.provider_logins` ask it
  (D4). Check: `tests/test_logins.py`, `tests/test_runtime.py`, `tests/test_doctor.py`,
  `tests/test_server_providers.py`, `uv run pytest -m integration
  tests/integration/test_provider_logins.py`.

## 2. Codex provider

- [x] 2.1 Codex's login state, `needs_login`, login variables, `LoginStatus.keyring` and
  `Provider.keyring_note`; the row's and `lado doctor`'s keyring note (D3, D4, D6). Check:
  `tests/test_codex.py`, `tests/test_server_providers.py`, `tests/test_doctor.py`.
- [x] 2.2 The agent's config.toml: the trust of the main root, the repository's hooks,
  `features.plugins = false`, `cli_auth_credentials_store = "file"`, `user-codex-home` (D2,
  D7, D8, D9). Check: `tests/test_codex.py`.
- [x] 2.3 The agent's `auth.json`: the link, the key file, the token, in
  `first_hook_blocker` (D1). Check: `tests/test_codex.py`, `tests/test_login_wait.py`.

## 3. Server and web UI

- [x] 3.1 `LoginChoice.action`, `LoginAction.help`, `ProviderLogins.logout_file`; Codex's
  question, choices and actions; `make web-types` (D5). Check: `tests/test_providers.py`,
  `tests/test_server_providers.py`, `tests/test_provider_check.py`, `make web`.
- [x] 3.2 The sheet to the mockup: a choice that opens the login window, the window's help,
  Log out of the file; docs/design/ui.md (D5, D6). Check: `web/src/LoginSheet.test.tsx`,
  `web/src/Providers.test.tsx`, `make web`.
- [x] 3.3 UI e2e of the sheet, desktop and phone, with screenshots. Check: `uv run pytest
  -m ui tests/ui/test_providers_section.py`.

## 4. Integration and smoke

- [x] 4.1 A login needed by the model only: refusal, start with a local model, a resumed
  session waiting and starting after a saved key. Check: `uv run pytest -m integration
  tests/integration/test_provider_logins.py`.
- [x] 4.2 Real Codex: the shared login file and the start with no screen in each mode, no
  plugins; `real_clis.answer_dialogs` without the trust answer. Check: `make test-smoke
  PROVIDER=codex` (and CI's smoke).

## 5. Docs and regression

- [x] 5.1 docs/design/agents.md, docs/design/modules.md, docs/cli.md, docs/install.md, the
  headers of `docker/compose.yaml` and `docker/Dockerfile` with `tests/test_docker.py`;
  CHANGELOG.md `## 0.44.0 (unreleased)`; the live test `tests/live/test_codex_login.py`
  (written, not run). Check: `make lint`, `make test`, `openspec validate codex-shared-login
  --strict`, `openspec validate --specs --strict`.
- [x] 5.2 BACKLOG.md: the four entries the proposal names removed when the task was taken
  (decision #1705), in a commit of its own by the analyst. Check: `grep -n "Codex agents
  cannot log in\|Every Codex agent asks\|Codex clones its plugins\|is not warned about"
  BACKLOG.md` finds none of them.
