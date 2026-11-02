## Context

Settings → Providers and environment (`web/src/Providers.tsx`) reads `GET
/api/providers/logins` (`server.launch.providers_page`) when it opens, when a login sheet
closes and on "Check again". `providers_page` runs every CLI's `--version` at once, then
the login shell (`_environment`, serially), then every CLI's status command at once
(`logins.read`), then `doctor.provider_checks`, whose `check_agent_env` runs the login
shell a second time; it keeps nothing. Each step has a 10 s timeout. The page then shows
`ProvidersPage.checks` as the doctor block.

A row's "… waits for this login" comes from `ProviderLogins.waiting`
(`logins.agents()`: live agents `waiting` with `logins.wait_reason`), while its login is
the CLI's status read now. The waiting window (`lado.login_wait`) polls every
`logins.POLL` (3 s) and only then sets the agent `starting`.

Claude agents start with `claude --mcp-config <dir>/mcp.json --settings <dir>/settings.json
… [--permission-mode <mode>]` (`providers/claude.py`, the settings file holds the hooks and
the deny list). `first_hook_blocker` answers the trust, the first run and the API key in
`.claude.json` through `edit_config`; its `Blocker.notes` (one line per write) reach
`Started.warnings` and loop.log through `runtime._first_hook_blocker` and `_before_window`,
and the waiting window's terminal through `login_wait.main`.

The probe of this run (Claude Code 2.1.295, a clean `CLAUDE_CONFIG_DIR`, a fake key and a
dead base URL, every mode of `--permission-mode`):

| Screen | Modes | LADO today | Taken here |
|---|---|---|---|
| Theme / first run | all | `hasCompletedOnboarding` | — |
| "Detected a custom API key" | all, with `ANTHROPIC_API_KEY` | `customApiKeyResponses` | — |
| "Security notes" | all | gone with the first run | — |
| "Accessing workspace … trust" | all | `hasTrustDialogAccepted` | — |
| "WARNING: … Bypass Permissions mode" | `bypassPermissions` (and `--dangerously-skip-permissions`) | nothing | `skipDangerousModePermissionPrompt` in `--settings` (works) |
| "New MCP server found in this project" | all, with a repository `.mcp.json` | nothing | `enableAllProjectMcpServers` in `--settings` (works) |
| Auto mode's notice | `auto` | — | inline, holds nothing |

`--mcp-config` servers ask nothing. `default` starts in manual mode; no flag starts in auto.

A resume: `runtime.start_session(resume=…)` checks the login only for a new session (`if
not old`, LAD-161). `resume_at_start` calls it with `reason=AT_START`; `lado update`
(`self_update._resume`) runs the installed `lado start <repo> --name <n> --no-attach`; the
UI's Resume is `POST /api/sessions/{name}/resume`. On a resume only the supervisor starts:
a stopped session's agent rows are deleted, and workers come back by `spawn_worker`, which
refuses without a login already.

## Goals / Non-Goals

Goals: the section answers at once and shows only what the user can fix; no Claude screen
before the first hook holds an agent unseen; LADO's own config writes are no warning; a
resume by hand cannot start an agent that only waits.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. The check of the CLIs is one object in the server's process

A new module `lado/server/provider_check.py` keeps, under one lock, the last row of each
provider, the agents' environment's problem and whether a check runs:

- `start() -> bool`: starts a daemon thread unless one runs; False when one runs already,
  and then one more pass runs once after it (built: a login window that ended during a
  check was read before its login, and no later check came).
- `snapshot() -> models.ProvidersPage`: the rows kept (a provider never read: a row with
  `ready: false`, its name and title only), `checking`, `environment`.
- `put(row)`: replaces one provider's row (an action's fresh row).

The thread runs the providers in a `ThreadPoolExecutor(len(registry))`: each one reads its
`doctor.provider_status`, waits for the environment (one future of `launch._environment`,
started with them, so the login shell runs once), reads `logins.read` and puts its row at
once. An exception in one provider's read becomes its row with the login `unknown` and the
error as its problem (no silent drop), and the check goes on; the thread always clears
`checking`. The result lives as long as the server; nothing is written to disk (a stale
login after a restart would be worse than a short first wait). Why a module and not
`app.state`: the actions in `launch.py` and the tests reach it without the app.

`launch.providers_page` goes; `launch.provider_login(name)` stays for the actions and puts
its row into the cache.

### D2. The API

- `GET /api/providers/logins` → `ProvidersPage` from `snapshot()`, starting nothing.
- `POST /api/providers/check` → starts a check (`start()`), answers the snapshot.
- `ProvidersPage`: `providers`, `checking: bool`, `environment: str` ("" when fine);
  `checks` goes (`CheckInfo` goes when nothing else uses it).
- `ProviderLogins.ready: bool` (false: not read yet; the rest of the row is empty).
- `PUT …/variables/{variable}`, `DELETE …/login-secrets` and the end of a login window
  (`DELETE …/login`, and the window's own end) put their fresh row and start a check.
- `make web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.

### D3. The section's UI

- On mount: `POST /api/providers/check`, then show its answer; while `checking`, `GET` every
  second (a timer, stopped on unmount); the latest answer wins (a counter, as in
  `Projects.tsx`).
- The heading in a row with a small button "↻", `aria-label="Check the CLIs again"`, a
  `title` "Checking the CLIs…" while it turns; it turns (`term-spin`, none under reduced
  motion) while `checking`, and a press while it turns does nothing.
- A row with `ready: false`: the name and "checking…" (muted). "Reading the CLIs…" goes.
- Subtitle: "Sign-ins your agents use. Changes apply to agents started afterwards."
- `DoctorChecks`, `.pv-doctor`, `.pv-mark`, `.pv-level-*`, `.pv-again` and "Check again" go.
- A sheet's `onChanged` puts the row; its close starts a check (instead of `read()`).

### D4. Which problems a row shows

- Not installed: the name in `--muted`, "not installed" as the version, the install hint
  (as today, `pv-src`); no state, no button.
- Untested version: `ProviderInfo.tested_version` set and the version outside it → a small
  muted "LADO is tested with <tested_version>" after the version (from `doctor
  .provider_status`, no second rule).
- No CLI installed: every row ready and none installed → one `pv-warn`-styled line over the
  list: "No agent CLI is installed: install one of them to start a session."
- A login that cannot be read: "Couldn't check the sign-in" with the problem under it
  (`pv-src`), the dot `dot-waiting`; replaces "Unknown: …".
- The agents' environment: `environment` non-empty → one line under the rows: "⚠ Agents'
  environment could not be read from your login shell: <why>. `lado doctor` shows more."
  Only `_environment`'s failure counts: the slow-shell warning and the WSL info stay in
  `lado doctor`.
- The macOS graphical-session check stays in `lado doctor` and the System panel: it is not
  about a provider row.

### D5. "… waits for this login" only while the login is missing

`launch.provider_logins` gives `waiting` only when the status is not `yes`. The agent
leaves `waiting` by its window's next poll (≤ 3 s), so a logged-in row never names it: one
rule, no timing. The UI keeps rendering the list as it comes.

### D6. Claude's two keys in the agent's own settings

In `providers/claude.py`, where the settings file is written: `"enableAllProjectMcpServers":
true` always, `"skipDangerousModePermissionPrompt": true` when the agent's permission mode
is `bypassPermissions`. Nothing goes through `edit_config`: the flag works (probe), so the
fallback the human allowed is not needed. A comment names the Claude Code version checked
(2.1.295). docs/install.md's line on a repository's `.mcp.json` says LADO enables them.

### D7. The safety net in the session loop

`runtime.check_starts(session, now)`, called by the loop's pass next to `check_windows`:
for each agent `starting`, with `seen_at == 0` and `window_at` set, `now - window_at >=
START_SILENCE` (30 s) → `state.block(session, name, START_SILENCE_REASON)` with
`Waiting for an answer in its terminal: no sign from it 30 s after its start. Open its
terminal.` The launch's time is `window_at`; `login_wait.main` sets it anew
(`state.window_opened`) right before it execs the CLI, so an agent that waited for its
login is measured from then. The hook path (`hooks.handle`) already makes an agent ready
on its session start when it waits by a start blocker (`held`); the developer makes any
first hook of an agent blocked by this reason clear it (`state.seen` sees `seen_at == 0`
and the reason), so a provider whose first hook is not a session start is not left
waiting. No provider name, no schema change.

Every provider gives a hook soon after its launch: Claude Code's SessionStart; Codex's
SessionStart on its first input, which LADO types at once (`FIRST_INPUT` or the queue);
OpenCode's and Kilo's plugin's session start. A model turn is not needed for any of them.

### D8. Notes to the log only

`runtime._first_hook_blocker` and `_before_window`'s early blocker log each note
themselves (`loop.log(session, f"{agent}: {note}")`) and return only the reason and the
warning; `login_wait.main` logs the notes without printing them. `Started.warnings`,
`lado start`'s stderr, `spawn_worker`'s and `start_session`'s results then carry no note.
`Blocker.notes`' docstring says so.

### D9. The resume by hand is refused, LADO's own resume waits

- `start_session(…, wait_for_login: bool = False)`: for a stored session (`old`), unless
  `wait_for_login` or `reason == AT_START`, `check_login(agent_cli, base_env,
  logins.RESUME)` at the place of the new session's check, before `state.resume_session`.
- `logins.refusal(…, RESUME)`: `<title> is not logged in, so the session was not resumed:
  log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set <first
  login variable> as LADO's secret or a project secret`.
- `lado start --wait-for-login` (hidden: `argparse.SUPPRESS`) passes it;
  `self_update._resume` adds it. An update from a LADO without the flag (0.43.0 → 0.44.0)
  runs the old `self_update`, whose `lado start` is now refused for a session whose login
  is missing: it lands in the update's `failed` list with its "resume it with lado start"
  line. Accepted: it happens once, only to a session that already waited for a login.
- `POST /api/sessions/{name}/resume`: refused as any `LadoError` (400).
- `Launch.tsx`: the `resuming` exceptions go (the option, `canStart`, `ProviderNote`'s amber
  branch); the Resume window reads `getProviders(resuming.project)` as now.
- Only the supervisor's provider is checked: it is the only agent a resume starts (Context).

### D10. Test layers

| Requirement | Layer |
|---|---|
| Section shows only fixable problems; ↻; subtitle | web unit (`Providers.test.tsx`), UI e2e |
| Answers at once from the last check | unit (`provider_check`), API (`test_server_providers.py`), web unit, UI e2e |
| "waits" only while missing | unit (`launch.provider_logins`), UI e2e (the Save test asserts it) |
| Claude's two keys | unit (`test_providers_claude.py`), smoke (real Claude: bypass on a clean config, a `.mcp.json`) |
| The safety net | unit (`check_starts`, hooks), integration with the fake agent (an agent that never hooks; one that hooks late) |
| Notes to the log only | unit (runtime, login_wait, cli), integration (`lado start` stderr), UI e2e (no "Warnings:" box) |
| Resume refused by hand, waits by LADO | unit (runtime, cli, self_update), API, web unit, UI e2e, integration (`lado start` of a stopped session) |

The live tests stay as they are (they run in bypassPermissions; the smoke covers the
screen).

### D11. Version and docs

The minor (CLI and API behaviour), already 0.44.0 (unreleased): CHANGELOG lines under
Changed (the section, the resume) and Fixed (the bypass and MCP screens, the warnings box,
the glitch). docs/design/ui.md (Providers and environment, the Resume window),
docs/cli.md (`lado start` resume, `--wait-for-login` not listed as it is internal, but
said in the update's section), docs/design/agents.md (start screens, the safety net, notes),
docs/design/modules.md (`server/provider_check.py`), AGENTS.md's layout line for `server/`,
BACKLOG.md (remove "An agent can stay `starting` with no hook and no reason" and the bypass
item of "Claude Code's first-run screens …").

## Risks / Trade-offs

- A CLI that takes longer than 30 s to its first hook on a slow machine is `waiting` for a
  moment: it clears by itself at the hook; the reason says to look at its terminal.
- `enableAllProjectMcpServers` runs the commands a repository's `.mcp.json` names, as the
  repository's `.claude/settings.json` hooks already run once LADO records the trust.
- The cache shows a result up to one check old for a second or two after a change outside
  LADO; ↻ turns meanwhile.
