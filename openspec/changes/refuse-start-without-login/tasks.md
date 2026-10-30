The plan with each task's tests: `docs/superpowers/plans/2026-10-30-refuse-start-without-login.md`.

## 1. Core

- [ ] 1.1 `logins.refusal` (SESSION, WORKER texts; NO only; `needs_login` only) and
  `runtime.NotLoggedIn`, `check_login`, `check_start_login` (D1, D4). Check:
  `tests/test_logins.py`.
- [ ] 1.2 `start_session` refuses a new session (never a resume), `spawn_worker` a worker by
  its own provider, before anything is stored or made; the existing tests of a new start
  without a login reworked to a resume (D2, D3). Check: `tests/test_runtime.py`,
  `tests/test_runtime_projects.py` (project secret), `tests/test_runtime_start_approved.py`,
  a run worker's step still waits.

## 2. CLI and server

- [ ] 2.1 `lado start <git-url>`, `lado start --new` and `POST /api/sessions` From scratch
  check before the clone or the folder (D2). Check: `tests/test_cli.py`,
  `tests/test_server_launch.py` (400, no folder).
- [ ] 2.2 `ProviderInfo.login_missing`, `GET /api/providers?project=` (404 unknown),
  `make web-types` (D5). Check: `tests/test_server_launch.py`, `make web`.

## 3. Web UI

- [ ] 3.1 New session window: the greyed option, no preselection, the red note with "Log in
  first", Start disabled, the Project way's project, the Resume window's amber note (D6).
  Check: `web/src/Launch.test.tsx`, `make web`.
- [ ] 3.2 UI e2e with `fake-login`: greyed option and note, the link to Settings, enabled
  once logged in, the Resume note; screenshots. Check: `uv run pytest -m ui
  tests/ui/test_launch.py`.

## 4. Integration

- [ ] 4.1 `lado start` refused with nothing left; `spawn_worker` through `lado mcp` refused
  with no worktree or branch; the LAD-157 wait tests reworked to a resume. Check: `uv run
  pytest -m integration tests/integration/test_provider_logins.py`.

## 5. Docs

- [ ] 5.1 `lado doctor`'s line (D7) with its test; docs/design/ui.md, docs/cli.md,
  docs/design/agents.md, docs/design/modules.md; CHANGELOG.md `## 0.44.0 (unreleased)`,
  Changed. Check: `make lint`, `make test`, `openspec validate refuse-start-without-login
  --strict`, `openspec validate --specs --strict`.
