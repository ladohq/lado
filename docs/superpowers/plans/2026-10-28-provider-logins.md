# Provider logins Implementation Plan

**Goal:** Settings → Providers and environment shows each agent CLI's login, read by the
CLI's own status command, and logs Claude Code, OpenCode and Kilo in and out from the UI
(a phone too); Claude Code's token and API key are LADO's secrets; a Claude agent without
a login waits with the reason and starts by itself; a logged-in Claude agent passes Claude
Code's first run with no human.

**Architecture:** the provider interface answers four login questions (`login_status`,
`login_actions` / `logout_argv`, `login_variables`, `needs_login` / `login_note`), each
provider parsing its own CLI; a new core module `lado.logins` reads them in the agents'
environment, attributes the source's layer, finds the waiting and running agents, and runs
the login windows (tmux sessions of their own, labelled); `runtime` holds a `needs_login`
agent with `state.block` and starts its window through `lado.login_wait`, which polls and
execs; `ClaudeProvider.first_hook_blocker` records two more keys through `edit_config`;
LADO's secrets are `project_secrets`' store over another folder, a layer in
`agent_env.resolve`; the server gets `/api/providers…`, the UI a section, a login sheet and
"Log in…" in Needs you.

**Tech Stack:** Python 3.10+ (standard library, `subprocess` with a time limit), FastAPI
and pydantic, React and TypeScript, xterm.js with `@xterm/addon-web-links` (new, xterm's
own addon), pytest (unit, server, integration with the fake agent, UI with Chromium,
smoke with the real CLIs), vitest.

**Spec:** `openspec/changes/provider-logins/` (proposal AC-1..AC-10, `design.md` D1-D14,
delta specs `provider-logins`, `claude-folder-trust`, `agent-variables`, `container`) and
`docs/superpowers/specs/2026-10-28-provider-logins-design.md`; mockup
`mockup-providers.html` (the run's artifact).

## Global Constraints

- No schema migration; one new npm dependency (`@xterm/addon-web-links`), no new Python one.
- Texts, verbatim (the spec's):
  - `<title> is not logged in: log in in Settings → Providers and environment, or set
    <variable>; the agent starts by itself once you do`;
  - `LADO recorded Claude Code's first run in <config file>`;
  - `LADO recorded the approval of ANTHROPIC_API_KEY in <config file>`;
  - `[ok] <title> login: <method>`, `[warn] Claude Code login: not logged in: Claude agents
    wait for a login (Settings → Providers and environment)`, `[info] <title> login: none`,
    `[warn] <title> login: unknown: <why>`;
  - `[info] LADO secrets: <NAME>[, <NAME>…] overrides LADO_ENV_DIR`.
- Nothing above `providers/` parses a CLI's output or names a CLI's file.
- No secret's value in an API answer, the change feed, a log, lado.db, the bug report, a
  process's arguments or the tmux server's environment; the key's last 20 characters only
  in Claude Code's own config.
- `unknown` never holds an agent and is never shown as "not logged in".
- Tests never touch the user's real CLI configs: `HOME`, `LADO_HOME`, `CLAUDE_CONFIG_DIR`,
  `CODEX_HOME`, `XDG_DATA_HOME` into `tmp_path` (`tests/conftest.py`'s fixtures).

## Tests per requirement

| Requirement (delta) | Layer | Tests |
|---|---|---|
| LADO reads each CLI's login with the CLI's own command | unit, smoke | `tests/test_providers.py` (recorded outputs per CLI, exit codes, timeout, odd output); `tests/smoke/` status in fresh homes |
| Settings shows the login of each agent CLI | API, vitest, UI e2e | `tests/test_server_providers.py` (`GET /api/providers`: states, source layer, waiting, projects, doctor checks); `Providers.test.tsx`; `tests/ui/test_providers_section.py` |
| Codex's row says that its agents do not get the login | unit, vitest | `test_providers.py` (note, no actions); `Providers.test.tsx` |
| The login window runs the CLI's own login command | unit, integration, UI e2e | `tests/test_logins.py` (one per provider, label, end by label); `tests/integration/test_provider_logins.py` (the window's command has the agents' environment and ends by itself; `lado stop --all` ends it; `lado ls` ignores it); `tests/ui/test_providers_section.py` |
| The login window works from a phone | vitest, UI e2e | `Providers.test.tsx` (Send sends text + `\r` in one frame; the keys' sequences; web links addon loaded); UI e2e at 390 px: the fake login reads the line and ends |
| Logging out of Claude Code asks first | API, vitest | `test_server_providers.py` (logout runs `logout_argv`, 400 without); `Providers.test.tsx` (the confirmation names the running agents) |
| A CLI's login variables can be set as LADO's secrets | unit, API, integration | `tests/test_project_secrets_store.py` (the store over LADO's folder); `test_server_providers.py` (PUT/DELETE, 400 for other names, 422 without input); `tests/integration/test_project_secrets_canary.py` (a LADO secret's value nowhere) |
| An agent whose CLI needs a login waits for it and starts by itself | unit, integration | `tests/test_runtime.py` (block, reason, notes, unknown does not hold, other providers not held); `tests/test_login_wait.py` (polls, overlays file layers but not LADO's variables, execs); `tests/integration/test_provider_logins.py` (fake provider: wait, `lado ls` reason, `AgentInfo.login_wait`, the marker appears → first hook with no restart; a LADO secret reaches a waiting agent; a timed-out status does not hold) |
| lado doctor prints each CLI's login | unit | `tests/test_doctor.py` |
| LADO records Claude Code's first run for a logged-in agent | unit, smoke | `test_providers.py` (fresh config with a token, not logged in → nothing written, the note once); smoke: a Claude agent with a made-up token in a fresh config reaches its first hook |
| LADO approves the API key it gives Claude Code | unit | `test_providers.py` (new key added, already approved, rejected → reason, the key never in a note) |
| A missing config is created with the trust alone (modified) | unit | `test_providers.py` (no login: trust alone; with a login: trust and `hasCompletedOnboarding`, mode 600) |
| One core function lays the project's layer (modified) | unit, integration | `tests/test_agent_env.py` (order: outside < LADO's secrets < project); `tests/integration/test_provider_logins.py` (a supervisor with and without a project) |
| The headers name the UI's login first (container) | unit | `tests/test_docker.py` (both headers name `Providers and environment`) |

## Steps

1. **Providers** (tasks 1.1-1.5). Write the parsers' tests first on outputs recorded in
   this plan's design (the proposal's "Checked by hand"), then the methods. Fake provider
   (`tests/fake_provider.py`): `needs_login`, `login_status` from a marker file
   `FAKE_AGENT_LOGIN`, an action whose argv is a small script that prints a link and reads
   one line.
2. **LADO's secrets** (2.1): generalise `project_secrets`' write/remove/read over a folder
   argument; the layer in `agent_env.resolve`; doctor's override line.
3. **`lado.logins`** (2.2, 2.4): status in the agents' environment, attribution, projects,
   waiting/running agents, `wait_reason`; the windows and `lado.terminal`'s login target.
4. **The wait** (2.3): `runtime` at start, resume, spawn and a run's worker;
   `lado.login_wait`.
5. **Doctor** (2.5).
6. **Server** (3.1), then `make web-types`.
7. **UI** (4.1-4.3) to the mockup; screenshots of the section, the window (desktop and
   phone) and Needs you as run artifacts.
8. **End to end** (5.1-5.4).
9. **Docs** (6.1).

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_provider_logins.py tests/integration/test_project_secrets_canary.py
tests/integration/test_agent_liveness.py`; `uv run pytest -m ui tests/ui/test_providers_section.py`
and the Needs you and Settings UI tests; `make web`; `openspec validate provider-logins
--strict`; `openspec validate --specs --strict`. CI runs the whole `make check` and the
smoke cells (this change touches files off the skip list).
