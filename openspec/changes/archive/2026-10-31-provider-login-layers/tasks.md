The plan with each task's tests: `docs/superpowers/plans/2026-10-30-provider-login-layers.md`.

## 1. Core

- [x] 1.1 `agent_env.layers`/`merge` with the whole-login rule, `resolve` on top (D1).
  Check: `tests/test_agent_env.py`.

## 2. Providers

- [x] 2.1 `base.py`: `LoginChoice`, `login_question`, `login_choices`,
  `LoginStatus.choice`, the file's words; `logout_argv` removed (D4, D5). Check:
  `tests/test_login_status.py`.
- [x] 2.2 Claude: no login actions, the choices, the method words; `fake-login` with two
  variables and two choices (D3, D4, D5). Check: `tests/test_login_status.py`.

## 3. Agents and the page's environment

- [x] 3.1 `runtime` merges per agent's provider; `login_wait` keeps `shell_login` and
  merges with the rule (D1). Check: `tests/test_runtime.py`, `tests/test_login_wait.py`.
- [x] 3.2 `logins.environment(provider=…)`, `layer` by the rule, `logout` removed;
  `lado doctor`'s line (D1, D2, D3). Check: `tests/test_logins.py`, `tests/test_doctor.py`.

## 4. Server

- [x] 4.1 Fields, PUT replaces, `DELETE …/login-secrets`, logout route removed;
  `make web-types` (D6, D7). Check: `tests/test_server_providers.py`, `make web`.

## 5. UI

- [x] 5.1 The row: one state line with its layer, one button (D8). Check:
  `web/src/Providers.test.tsx`.
- [x] 5.2 `LoginSheet.tsx`: Claude's choices and paste, Log out; OpenCode and Kilo
  straight to their login window (D8). Check: `web/src/LoginSheet.test.tsx`.

## 6. End to end

- [x] 6.1 Integration with `fake-login`: whole login from the highest layer, the project
  wins, a waiting agent takes a saved token. Check: `uv run pytest -m integration
  tests/integration/test_provider_logins.py`.
- [x] 6.2 UI e2e at desktop and phone width, screenshots for the build report. Check:
  `uv run pytest -m ui tests/ui/test_providers_section.py`.

## 7. Docs

- [x] 7.1 docs/design/ui.md, agents.md, modules.md, docs/cli.md, docs/install.md,
  CHANGELOG.md (D9). Check: `tests/test_agents_md.py`, read against the code.
