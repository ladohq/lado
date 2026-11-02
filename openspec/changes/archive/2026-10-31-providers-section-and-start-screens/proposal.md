Task: LAD-163

## Why

The human's six remarks on Settings → Providers and environment and on the start of
Claude agents (LAD-163, with screenshots), each decided item by item in an earlier
session (`brief-lad-163`, questions #2053-#2069) and in this run (question #2078):

1. The section ends with "lado doctor about the providers" (`[ok]`/`[info]`/`[warn]`
   lines) and "Check again": a copy of `lado doctor` that mostly says everything is fine.
   Right after Save in the login sheet a row shows "Logged in" and "… waits for this
   login" together (found in LAD-160's review). Cause: the row's login is read live from
   the CLI, while the waiting agent leaves `waiting` only at the next poll of its window
   (`logins.POLL`, 3 s); the section never reads again by itself.
2. The subtitle "The agent CLIs LADO can run, whether each is logged in and how. A login
   here is the one every new agent of that CLI gets." is long and unclear.
3. Every visit waits seconds for the section. Cause: `launch.providers_page` reads
   everything anew on each GET and keeps nothing: each CLI's `--version` and status command
   (in parallel), the agents' environment from the login shell (serially, and a second
   time inside `doctor.check_agent_env`), so up to four timeouts in a row.
4. A Claude agent started in `bypassPermissions` stops on Claude Code's own screen
   "WARNING: Claude Code running in Bypass Permissions mode" (No, exit / Yes, I accept)
   before any hook, unseen by LADO. Checked on a clean config in this run (Claude Code
   2.1.295, all seven modes): the first run, the custom API key, the security notes and
   the folder trust come first in every mode (LADO answers them already: LAD-106,
   LAD-157); after those, only two screens remain: the bypass warning (bypassPermissions
   only) and "New MCP server found in this project" (any mode, when the repository has a
   `.mcp.json`). Auto mode shows an inline notice, no screen; MCP servers LADO passes by
   `--mcp-config` ask nothing. Both remaining screens go away with a key in the agent's own
   `--settings` file (checked): `skipDangerousModePermissionPrompt: true`,
   `enableAllProjectMcpServers: true`. Nothing in LADO notices an agent that stands
   before its first hook on a screen it does not know (BACKLOG, "An agent can stay
   `starting` with no hook and no reason").
5. Over the chat of a new session: "Warnings: LADO recorded Claude Code's trust in …".
   Cause: `Blocker.notes` (what LADO wrote into Claude Code's config) travel with real
   warnings into `Started.warnings`, `lado start`'s stderr and `spawn_worker`'s result.
6. Resume of a stopped session stays enabled while its CLI has no login; the supervisor
   then waits for it. LAD-161 kept the wait for every resume on purpose.

On the way: the screenshot of item 4 shows "session loop not running" for that session.
The loop starts right after the agent's window and waits for no hook, and nothing an agent
does before its first hook ends it; the status is read anew every 3 s. So it is not a
consequence of the bypass screen but a separate fault of the loop's process on the
human's Mac (its reason is in `~/.lado/loop.log`); named to the human in question #2078
and filed as LAD-165.

The human's decisions:

- (1) The doctor block and "Check again" go; no `[ok]` labels in the UI. A row shows only
  a problem the user can fix, in plain words with what to do: a CLI not installed (grey,
  with the install hint), no CLI installed at all (one line over the list), an untested
  version (small, "LADO is tested with …"), a sign-in that could not be checked
  ("Couldn't check the sign-in" and why), the agents' environment not resolved (only
  then). A small ↻ by the heading replaces "Check again". The glitch is fixed.
- (2) The subtitle: "Sign-ins your agents use. Changes apply to agents started
  afterwards." The title stays "Providers and environment".
- (3) The server keeps the last result and answers with it at once, starts a fresh check
  in the background (all CLIs in parallel); the rows change quietly when it ends, ↻ spins
  meanwhile; a login or logout from the UI starts one; at the very first open the rows
  appear as each is ready.
- (4) Every screen Claude Code shows before its first hook, in all seven modes, is
  answered by the agent's own `--settings` first, by `claude.edit_config` only where
  Claude ignores the flag; the bypass warning only in a session started in that mode. A
  repository's `.mcp.json` servers are enabled (as for a human who trusts the folder). An
  agent with no hook 30 s after its CLI's launch waits with the reason "waiting for an
  answer in its terminal".
- (5) LADO's writes into Claude Code's config go to the session's log only; real problems
  (a write failed, a file that cannot be read) stay warnings.
- (6) A manual Resume is refused while the supervisor's CLI needs a login and has none
  (UI: Resume disabled with "Log in first"; `lado start` of a stopped session refuses);
  the automatic resume (the container's start, `lado update`) still waits for the login.

Options weighed for the slow section (root cause: nothing is kept between reads):

- (a, taken) A cache in the server's process with one background check at a time, per CLI
  as each finishes; the GET answers with what is there and whether a check runs; the UI
  reads again every second while one runs. Long-term cost: one module-level state in the
  server and a short poll while the section is open and checking.
- (b) Push the rows through the change feed (`feed.DERIVED`): the feed would run the CLIs'
  commands every few seconds for every open tab, or need a second trigger path. Rejected:
  costlier, and the feed is lado.db's.
- (c) Keep the result on disk: survives a restart, but a stale login after a restart is
  worse than a short first wait. Rejected.

For the start screens: (a, taken) the agent's own settings file (no shared file touched,
AGENTS.md "Never touch the user's global agent config"); (b) `bypassPermissionsModeAccepted`
in `.claude.json` through `edit_config`: rejected, the flag works; (c) answering the screen
by typing keys: rejected, "Events, not screens".

For the agent held at its start: (a, taken) a neutral check of the session loop, by
`seen_at` (no hook yet) and the launch's time, for every provider; (b) a per-provider
list of screens: misses the next screen a CLI adds. Rejected.

Held against the design principles: neutral core (the cache, the safety net and the
resume's refusal go by `Provider` and `Capabilities`; the two Claude keys stay in
`providers/claude.py`; every provider fires a hook at its session's start or first input,
checked in design.md D9), one source of truth (the rows and the problems come from the same
`doctor`/`logins` reads, the "waits" line from the row's own login state), no silent drop
(a log line for every write LADO makes; a refused resume says why and where to log in),
only what is used (no new setting, no schema change).

## What Changes

- **Settings → Providers and environment**: the subtitle; ↻ by the heading (spinning while
  a check runs) in place of "Check again"; no doctor block; each row shows only fixable
  problems (see Why, 1); "… waits for this login" shows only while the row's login is
  missing.
- **`POST /api/providers/check`** starts a background check unless one runs (the section's
  opening and ↻); **`GET /api/providers/logins`** answers at once from the server's last
  result, starting nothing: whether a check runs (`checking`), which rows are not read yet
  (`ready: false`) and the agents' environment's problem (`environment`); the doctor's
  `checks` go. A login, logout or login window's end starts a check too.
- **Claude agents** in `bypassPermissions` get `skipDangerousModePermissionPrompt: true`,
  and every Claude agent `enableAllProjectMcpServers: true`, in their own `--settings`
  file.
- **The safety net**: the session loop puts an agent that is `starting`, has had no hook
  since its window opened, and whose CLI was launched 30 s ago or more, into `waiting`
  with the reason "Waiting for an answer in its terminal: no sign from it 30 s after its
  start. Open its terminal."; its first hook takes it out as for any start blocker.
- **Notes**: `Blocker.notes` go to loop.log only, never to `Started.warnings`, stderr,
  `spawn_worker`'s result, the UI or the waiting window's terminal.
- **Resume**: `start_session` refuses a manual resume whose supervisor's CLI needs a login
  and has none (`lado start` of a stopped session, `POST /api/sessions/{name}/resume`);
  `resume_at_start` and `lado update` (with the hidden `lado start --wait-for-login`) keep
  the wait. The Resume window greys the CLI out as New session does.
- docs/design/ui.md, docs/cli.md, docs/design/agents.md, docs/design/modules.md,
  docs/install.md (the repository's MCP servers), BACKLOG.md (the two entries this closes),
  CHANGELOG.md under `## 0.44.0 (unreleased)`.
- A behaviour change of the CLI and the API: the minor (0.44.0, already the unreleased one).

## Scope

- The section's look and data (items 1-3) with the glitch's fix.
- The two Claude screens (item 4) and the neutral safety net for any provider.
- Notes to the log only (item 5).
- The manual resume's refusal in the core, CLI, API and Resume window (item 6).
- Tests: unit, API, web unit (vitest), UI e2e, integration with the fake agent, a smoke
  test of the bypass screen with real Claude Code.

## Out of scope

- Answering the CLIs' permission requests and questions during work from the UI: the
  human decided not to take it and not to file a task.
- "session loop not running" on the human's Mac: a separate fault (see Why), filed as
  LAD-165 on the human's yes (question #2078).
- `lado doctor` and the System panel: they keep their full text, which the section no
  longer copies.
- The New session window's `GET /api/providers`, which reads the CLIs anew too: not named
  by the human; it can take the cache later.
- A Claude session with no permission mode starting in auto (Claude Code 2.1.295's new
  default): told the human, not asked to change.
- Codex, OpenCode and Kilo screens: no screen before their first hook is known; the safety
  net covers one that appears.
- Refusing a worker's resume: workers come back only by `spawn_worker`, refused already
  (LAD-161).

## Acceptance criteria

- AC-1: The section shows the subtitle "Sign-ins your agents use. Changes apply to agents
  started afterwards.", a ↻ button named "Check the CLIs again" by the heading, no
  "lado doctor about the providers" block, no "Check again" and no `[ok]`/`[info]`/`[warn]`
  text.
- AC-2: A CLI not installed shows "not installed" in grey with its install hint; with no CLI
  installed one line over the list says so; a version off the tested one shows "LADO is
  tested with <version>" next to it; a status that cannot be read shows "Couldn't check
  the sign-in" with why; the agents' environment's line shows only when it could not be
  resolved; nothing else of `lado doctor` shows.
- AC-3: With a result from before, the section's rows show at once (no "Reading the CLIs…")
  while ↻ spins, and change in place when the check ends; the very first open shows each
  row as its CLI answers.
- AC-4: ↻ starts a check; Save, Log out and a login window's end start one too; a second
  ↻ while one runs starts none.
- AC-5: After Save of a token while an agent waits for the login, the row never shows
  "Logged in" together with "… waits for this login".
- AC-6: A Claude agent started in `bypassPermissions` on a clean config reaches its first
  hook with no screen and no write to `.claude.json` or the user's settings for it; its
  `--settings` file holds `skipDangerousModePermissionPrompt: true`, an agent of another
  mode's does not.
- AC-7: A Claude agent in a repository with a `.mcp.json` reaches its first hook with no
  screen, the repository's servers enabled.
- AC-8: An agent of any provider with no hook 30 s after its CLI's launch is `waiting`
  with the reason "Waiting for an answer in its terminal: …", in Needs you and `lado ls`;
  its first hook makes it ready; an agent that waits for its login is measured from the
  login's arrival.
- AC-9: A new session's start, a resume and `spawn_worker` with LADO's writes into Claude
  Code's config show no "LADO recorded …" line (UI, stderr, the tool's result) and loop.log
  holds each once; a config that cannot be read or written still warns as before.
- AC-10: Resume of a stopped Claude session without a login: the Resume window shows
  "claude · not logged in" disabled, the red note with "Log in first", and Resume
  disabled; another CLI with a login can be chosen; `lado start` of that session exits
  non-zero with "Claude Code is not logged in, so the session was not resumed: …" and the
  session stays stopped; `POST /api/sessions/{name}/resume` answers 400 with it.
- AC-11: The resume at the container's start and after `lado update` still resumes such a
  session, its supervisor waiting for the login.
