The plan with each task's tests: `docs/superpowers/plans/2026-10-28-provider-logins.md`.

## 1. Providers

- [ ] 1.1 `base.py`: `LoginStatus`, `login_status`, `login_actions`, `logout_argv`,
  `login_variables`, `capabilities.needs_login`, `login_note` with their defaults (D1).
  Check: `tests/test_providers.py`.
- [ ] 1.2 Claude: `login_status` from `claude auth status --json` (each `authMethod`,
  `subscriptionType`, `apiKeySource`, exit 1, bad JSON, timeout), its actions, logout,
  variables, `needs_login` (D1). Check: unit tests on recorded outputs.
- [ ] 1.3 Codex: `login_status` from `codex login status` with the user's `CODEX_HOME`,
  nothing after ` - ` kept, the note (D1). Check: unit tests.
- [ ] 1.4 OpenCode and Kilo (`opencode_family.py`): `auth list` parsed with ANSI removed,
  credentials and Environment, actions login/logout (D1). Check: unit tests on recorded
  outputs.
- [ ] 1.5 Claude's first-run keys in `first_hook_blocker`: `hasCompletedOnboarding`, the
  API key's approval, the rejected key's reason, the notes; a missing config (D6). Check:
  `tests/test_providers.py` (configs without the keys, with a rejected key, not JSON).

## 2. Core

- [ ] 2.1 LADO's secrets: the store generalised from `project_secrets` (write, remove,
  read with the own-folder checks), the layer in `agent_env.resolve`, `lado doctor`'s
  override line (D4). Check: `tests/test_agent_env.py`, `tests/test_project_secrets_store.py`,
  `tests/test_doctor.py`.
- [ ] 2.2 `lado.logins`: the status of each installed provider in the agents' environment
  without a project, the source's layer, the projects with their own login variable, the
  waiting and running agents, `wait_reason` (D2, D9). Check: `tests/test_logins.py` (new).
- [ ] 2.3 The login wait at launch: `runtime` reads the status for a `needs_login`
  provider, blocks with the reason, tells and logs it; `lado.login_wait` polls with the
  file layers and execs the CLI after `first_hook_blocker`; unknown never holds (D3).
  Check: `tests/test_runtime.py`, `tests/test_login_wait.py` (new).
- [ ] 2.4 Login windows: open (one per provider, labelled), close, end by label at `lado
  stop --all` and the server's start and stop; `lado ls` ignores them; `lado.terminal`'s
  login target (D5). Check: `tests/test_logins.py`, `tests/test_terminal.py`.
- [ ] 2.5 `lado doctor`'s login lines (D10). Check: `tests/test_doctor.py`.

## 3. Server

- [ ] 3.1 `GET /api/providers`, login window open/close and its WebSocket, logout,
  `PUT`/`DELETE` of a login variable (refusals, 422 without input), `AgentInfo.login_wait`;
  `make web-types` (D5, D9, D11). Check: `tests/test_server_providers.py` (new), `make web`.

## 4. UI

- [ ] 4.1 `Providers.tsx` in Settings with the anchor, the rows, the shared `SecretField`,
  the doctor checks, Check again, the confirmations (D7, D11). Check: vitest
  `Providers.test.tsx`.
- [ ] 4.2 The login window: the terminal made reusable over a socket, `@xterm/addon-web-links`,
  "Text to send", the keys, the phone sheet (D8). Check: vitest.
- [ ] 4.3 Needs you's "Log in…" for an agent with `login_wait` (D9). Check: vitest
  `NeedsYou.test.tsx`.

## 5. End to end

- [ ] 5.1 `tests/integration/test_provider_logins.py` with the fake provider's login: the
  wait and its reason in `lado ls`, the start by itself, a LADO secret reaching a waiting
  agent, an unknown status that does not hold, a login window's command and its end (D12).
  Check: `uv run pytest -m integration -n auto tests/integration/test_provider_logins.py`.
- [ ] 5.2 The canary of secrets covers a LADO secret (D12). Check: `uv run pytest -m
  integration -n auto tests/integration/test_project_secrets_canary.py`.
- [ ] 5.3 UI e2e: the section, the window with a fake login command, Needs you's "Log
  in…", a phone's width; screenshots (D12). Check: `uv run pytest -m ui
  tests/ui/test_providers.py`.
- [ ] 5.4 Smoke: each real CLI's status in a fresh home, and a Claude agent with a token in
  a fresh config past the first run (D12). Check: CI's smoke cells.

## 6. Docs

- [ ] 6.1 docs/design/ui.md, docs/design/agents.md, docs/design/modules.md, docs/cli.md,
  docs/install.md, the compose and Dockerfile headers (with `tests/test_docker.py`),
  AGENTS.md's exception and map, CHANGELOG.md (D13). Check: `tests/test_agents_md.py`,
  `tests/test_docker.py`, `openspec validate provider-logins --strict`.
