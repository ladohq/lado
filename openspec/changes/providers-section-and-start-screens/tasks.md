The plan with each task's tests: `docs/superpowers/plans/2026-10-31-providers-section-and-start-screens.md`.

## 1. Core

- [ ] 1.1 `Blocker.notes` logged in loop.log by `runtime` and `login_wait`, returned to no
  one; real warnings unchanged (D8). Check: `tests/test_runtime.py`,
  `tests/test_login_wait.py`, `tests/test_cli.py`, `uv run pytest -m integration
  tests/integration/test_session_start.py`.
- [ ] 1.2 Claude's settings file: `enableAllProjectMcpServers` always,
  `skipDangerousModePermissionPrompt` in `bypassPermissions` only; the smoke fixtures
  without `bypassPermissionsModeAccepted`, a smoke test with a repository `.mcp.json`;
  docs/install.md (D6). Check: `tests/test_providers.py`; smoke in CI.
- [ ] 1.3 `runtime.check_starts` in the loop's pass, `login_wait` marks the launch anew
  (D7). Check: `tests/test_liveness.py`, `tests/test_login_wait.py`, `uv run pytest -m
  integration tests/integration/test_session_loop.py`.
- [ ] 1.4 The resume by hand refused (`logins.RESUME`, `start_session(wait_for_login)`,
  hidden `lado start --wait-for-login`, `self_update`) (D9). Check: `tests/test_logins.py`,
  `tests/test_runtime.py`, `tests/test_cli.py`, `tests/test_self_update.py`,
  `tests/test_server_launch.py`, `uv run pytest -m integration
  tests/integration/test_provider_logins.py`.

## 2. Server

- [ ] 2.1 `server/provider_check.py`; `GET /api/providers/logins` from it,
  `POST /api/providers/check`, the actions start a check; `waiting` only while the login
  is missing; `make web-types` (D1, D2, D5). Check: `tests/test_provider_check.py`,
  `tests/test_server_providers.py`, `make web`.

## 3. Web UI

- [ ] 3.1 The section to the mockup (subtitle, ↻, problems only, polling, not-ready rows)
  and the Resume window without the resume exceptions (D3, D4, D9). Check:
  `web/src/Providers.test.tsx`, `web/src/Launch.test.tsx`, `make web`.
- [ ] 3.2 UI e2e: the section at once from the last check, Save with no "waits" line, the
  Resume window disabled with "Log in first", no "Warnings:" box after a start;
  screenshots. Check: `uv run pytest -m ui tests/ui/test_providers_section.py
  tests/ui/test_launch.py tests/ui/test_session_head.py`.

## 4. Docs and regression

- [ ] 4.1 docs/design/ui.md, docs/cli.md, docs/design/agents.md, docs/design/modules.md,
  AGENTS.md's `server/` line, BACKLOG.md (the two closed entries), CHANGELOG.md
  `## 0.44.0 (unreleased)` (D11). Check: `tests/test_agents_md.py`.
- [ ] 4.2 Regression run: `make lint`, `make test`, the integration and UI files above with
  their markers, `make web`, `openspec validate providers-section-and-start-screens
  --strict`, `openspec validate --specs --strict`.
