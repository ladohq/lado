# Provider login layers Implementation Plan

**Goal:** Settings → Providers and environment shows per CLI one state line, which names
the layer the login comes from, and one button; Claude Code logs in only by a token or
API key pasted in a sheet and kept as LADO's secret; the layer that sets any of a
provider's login variables gives that provider's agents the whole login.

**Architecture:** `agent_env` splits `resolve` into `layers` and `merge(layers, login)`
with the whole-login rule over names only; `runtime`, `login_wait` and `logins` pass the
agent's provider's `login_variables`. The provider interface gains `login_question`,
`login_choices`, `LoginStatus.choice` and the file's words, and loses `logout_argv`;
Claude loses its login actions. The server adds fields, replaces the logout route by
`DELETE …/login-secrets`, and PUT replaces LADO's other login variable. The UI gets a
simpler row and `LoginSheet.tsx`.

**Tech Stack:** Python 3.10+ (standard library), FastAPI and pydantic, React and
TypeScript, pytest (unit, server, integration with the fake agent, UI with Chromium),
vitest.

**Spec:** `openspec/changes/provider-login-layers/` (proposal AC-1..AC-9, `design.md`
D1-D9, delta specs `provider-logins`, `agent-variables`) and
`docs/superpowers/specs/2026-10-30-provider-login-layers-design.md`; mockup
`mockup-login-ladder.html` (the run's artifact).

## Global Constraints

- No schema migration, no new dependency.
- Texts, verbatim (the spec's): "How do you pay for Claude?", "Subscription — Claude Pro
  or Max", "Pay per use — API billing", "Run `claude setup-token` on any computer where
  Claude Code is installed and paste the token it prints.", "Paste an API key from
  console.anthropic.com.", "Log in…", "Change login…", "Log out…", "Log out of one…",
  "Logged in · <method> · <where>", where "LADO's secret", "outside folder", "login
  shell", "Claude Code's login file"; methods "Subscription (<Plan>)", "Subscription
  (token)", "Pay per use (API key)", "Pay per use (Console)".
- No value of a secret in any answer, log, lado.db or the bug report.
- Nothing above `providers/` names Claude Code; `agent_env` gets names, not providers.
- LAD-161 may land first: merge, keep both (design D9).

## Task 1: The whole-login rule (D1)

Files: `src/lado/agent_env.py`, `tests/test_agent_env.py`.

- `Layers`, `layers(project)`, `merge(layers, login=())`; `resolve` on top of them.
- Tests (unit): without `login` the result equals today's for every existing case; the
  highest layer that sets any login name gives all it sets and none comes from lower
  ones; a project's single variable hides both lower ones; names outside `login` keep
  their order; `for_git` unchanged.

## Task 2: Providers (D3, D4, D5)

Files: `src/lado/providers/base.py`, `src/lado/providers/claude.py`,
`tests/integration/fake_provider.py`, `tests/test_login_status.py`,
`tests/test_providers.py`.

- `LoginChoice`, `login_question`, `login_choices`, `LoginStatus.choice`, the file's
  words; `logout_argv` removed; Claude: no actions, the choices, the words.
- `fake-login`: login variables `FAKE_AGENT_TOKEN`, `FAKE_AGENT_KEY`; two choices.
- Tests (unit): each recorded `claude auth status` output gives the method and `choice`;
  each choice's variable is a login variable; Claude has no login action.

## Task 3: Agents, waiting windows, page environment, doctor (D1, D2)

Files: `src/lado/runtime.py`, `src/lado/login_wait.py`, `src/lado/logins.py`,
`src/lado/doctor.py`, `tests/test_runtime.py`, `tests/test_login_wait.py`,
`tests/test_logins.py`, `tests/test_doctor.py`.

- `runtime`: `Layers` per launch, `merge` per agent's provider.
- `login_wait`: `shell_login` in the file; `layers` merges with the rule.
- `logins.environment(project=None, provider=None)`, `layer` by the rule; `logout`
  removed; `doctor`'s line with the layer.
- Tests (unit): a worker of another provider keeps `ANTHROPIC_API_KEY`; the waiting
  window's `layers` drops the shell's key once a token is saved; `layer` names the
  highest layer; doctor's `[ok] Claude Code login: Subscription (token) · LADO's secret`.

## Task 4: Server (D6, D7)

Files: `src/lado/server/models.py`, `src/lado/server/launch.py`,
`src/lado/server/app.py`, `web/openapi.json`, `web/src/api.gen.ts`, `web/src/api.ts`,
`tests/test_server_providers.py`.

- Fields `question`, `choices`, `from_lado`, `LoginInfo.choice`, `LoginInfo.where`;
  `can_logout` removed. PUT removes the provider's other login variables from LADO's
  secrets; `DELETE /api/providers/{name}/login-secrets`; the logout route removed.
  `make web-types`.
- Tests (API): the fields for a token of LADO's secrets, of the outside folder, of the
  file; PUT of a key after a token leaves only the key; DELETE login-secrets removes both
  and answers the row; `POST …/logout` is 404/405; no value in any answer.

## Task 5: UI (D8)

Files: `web/src/Providers.tsx`, `web/src/LoginSheet.tsx` (new), `web/src/LoginWindow.tsx`
(embeddable), `web/src/styles.css`, `web/src/Providers.test.tsx`,
`web/src/LoginSheet.test.tsx` (new), `web/src/fakes.ts`.

- The row: the state line with its layer, waiting agents, projects, note, one button.
- The sheet: question, choices, the chosen one's field and Save, Log out with
  confirmation; OpenCode/Kilo straight to their login window with "Log out of one…";
  full screen at ≤600 px.
- Tests (vitest): every row state of the mockup; one button; the sheet's calls; the
  confirmation names the running agents; no Log out unless `from_lado`.

## Task 6: End to end

Files: `tests/integration/test_provider_logins.py`, `tests/ui/test_providers_section.py`.

- Integration (marker `integration`, fake agent `fake-login`): outside `FAKE_AGENT_KEY` +
  LADO's `FAKE_AGENT_TOKEN` → the agent's environment has only the token (AC-3, AC-4); a
  project's `FAKE_AGENT_KEY` → its session's agent has only the key (AC-5); a waiting
  agent takes a token saved meanwhile and not the shell's key; an OpenCode-like fake
  (`fake`) keeps `FAKE_AGENT_KEY`.
- UI e2e (marker `ui`): the row and the sheet at 1280 and 390 px with the fake providers;
  paste and Log out; screenshots in `<temp>/lado-ui-shots/` for the build report (AC-1,
  AC-2, AC-7, AC-8).

## Task 7: Docs and changelog (D9)

Files: `docs/design/ui.md` (Providers and environment), `docs/design/agents.md` (the
environment's whole-login rule), `docs/design/modules.md` (`agent_env`, `lado.logins`),
`docs/cli.md` (`lado doctor`'s login line), `docs/install.md` (Docker: a token from
`claude setup-token`, pasted or in `secrets/`; `claude auth logout` for a file login),
`CHANGELOG.md` (0.44.0 Added).

## Requirement → tests

| Requirement (delta) | Tests |
|---|---|
| agent-variables: one core function (whole login) | `test_agent_env.py`, `test_runtime.py`, integration |
| reads each CLI's login (words) | `test_login_status.py`, `test_doctor.py` |
| Settings shows the login | `Providers.test.tsx`, `test_server_providers.py`, UI e2e |
| login window (OpenCode, Kilo; none for Claude) | `LoginSheet.test.tsx`, `test_providers.py`, UI e2e |
| Logging out asks first | `test_server_providers.py`, `LoginSheet.test.tsx`, UI e2e |
| login variables as LADO's secrets | `test_server_providers.py`, UI e2e |
| agent waits and starts by itself | `test_login_wait.py`, integration |
| lado doctor's line | `test_doctor.py` |

## Regression run

`make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_provider_logins.py`, `uv run pytest -m ui
tests/ui/test_providers_section.py`, `make web`, `openspec validate provider-login-layers
--strict`, `openspec validate --specs --strict`.
