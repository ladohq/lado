Task: LAD-161

## Why

Symptom: a new session or a new worker whose agent CLI needs a login (Claude Code) and has
none starts all the same and waits in Needs you with "Claude Code is not logged in: …"
until the human logs in (LAD-157). On the main path this is a detour: the human first
starts something that cannot work, then finds the reason, logs in, and comes back.

Cause: LADO reads the login only at the launch of the agent's window
(`runtime._held_for_login`, inside `_before_window`), after `start_session` has taken the
session in lado.db and `spawn_worker` has made the worker's worktree, branch and record.
At that point the only safe answer is to wait (`lado.login_wait`). Nothing before the
launch, in the core or in the New session window, asks the CLI about its login.

The human's decision (session lad-157, `decision-provider-login-ux`, section 4, "2a"), and
the answers to questions #1961 and #1969 of this run (all recommendations taken):

- A new session and a new worker of a CLI that needs a login are **refused** without one:
  the New session window greys the CLI out with "Log in first"; `lado start`, the
  supervisor's `spawn_worker` and the approved `start_session` refuse with the reason.
- The check reads the login in the environment the agent would get: with the session's
  project's variables and secrets (a project with its own `CLAUDE_CODE_OAUTH_TOKEN` starts
  Claude agents without LADO's own login).
- Sessions mix CLIs (a Claude supervisor, a Kilo worker; `spawn_worker(provider=...)`): a
  session's start checks its supervisor's CLI, a worker's start the worker's own CLI.
- LAD-157's wait stays the fallback for a login lost after the start: a resume (by hand,
  at LADO's start, after an update), a logout, a removed token. A resume is never refused;
  the Resume window warns that the supervisor will wait.
- A login LADO cannot read (`unknown`) refuses nothing: the agent starts with the warning
  it has now.
- Codex, OpenCode and Kilo start without a login, as now.

Options weighed (root cause: the check comes after the state is taken):

- (a, taken) One check in the core before anything is stored (`start_session` for a new
  session, `spawn_worker`), the same for the CLI, the UI, the MCP tools; the New session
  window shows the same state, read by the server. Long-term cost: one more status command
  per new session or worker (about 0.1 s for Claude Code), and the providers list of the
  window runs it too.
- (b) A check in the UI only: `lado start`, `spawn_worker` and `start_session` would still
  wait; two behaviours for one rule. Rejected: it contradicts the decision.
- (c) Refuse inside the agent's window instead of waiting: the session is taken by then,
  and undoing it from the window is a second undo path. Rejected.

Held against the design principles: neutral core (the rule rests on
`Capabilities.needs_login` and `Provider.login_status`; no CLI is named above
`providers/`; any provider that sets `needs_login` gets the refusal), one source of truth
(the CLI's own status command, in the environment `_base_env` builds for the launch; the
window shows what the server reads, never a second rule), no silent drop (every refusal
says why and where to log in; an unreadable login warns), only what is used (one boolean
on the providers list, one query parameter).

## What Changes

- **The core refuses** a new session (`start_session` with no stored session of that name)
  whose provider needs a login and is not logged in in `agents_env(project)` (`_base_env` before), before the
  session is stored: `lado start`, `POST /api/sessions`, the approved `start_session` MCP
  tool. `lado start <git-url>` and `lado start --new` (and the UI's From scratch) check
  before they clone or make the folder.
- **The core refuses** a new worker (`spawn_worker`, also for a run) of such a provider
  before its worktree, branch or record exists; the supervisor gets the reason.
- **`GET /api/providers`** gains `login_missing` per provider (needs a login, and the status
  says "no") and a query `project=<id>` that reads it with that project's layer.
- **The New session window**: a CLI with `login_missing` is a greyed option
  "`<name>` · not logged in"; it is never the suggested choice; with it suggested or
  chosen, a red note "`<CLI>` is not logged in: its agents cannot start. Log in first"
  whose link closes the window and opens Settings → Providers and environment; Start stays
  disabled. The Project way reads the list with the chosen project. The Resume window
  shows an amber note instead and lets the resume go on.
- `lado doctor`'s warning line says that new sessions and workers of the CLI are refused.
- The living spec `claude-folder-trust`'s "A fresh home" scenario starts its agent by a
  resume, the only start that still waits for a login (a delta of that capability).
- docs/design/ui.md (New session window, Providers and environment), docs/cli.md (`lado
  start`, `lado doctor`), docs/design/agents.md (the login at launch), CHANGELOG.md
  (`## 0.44.0 (unreleased)`, Changed).
- A behaviour change of the CLI and of an MCP tool: the minor version (0.44.0, already the
  unreleased one).

## Scope

- The refusal of a new session and a new worker in the core, with the session's project.
- The pre-check of `lado start <git-url>`, `lado start --new` and the UI's From scratch.
- The providers list's login state and the New session window (folder, project, clone and
  scratch ways; the Resume window's warning).
- Tests: unit, API, web unit (vitest), UI e2e, an integration test with the fake agent.

## Out of scope

- Settings → Providers and environment's page and login window: LAD-160 (session lad-160).
  If LAD-160 merges first, its rule "the method chosen on the page wins" reaches this check
  through the same environment (`_base_env`), with no second rule here.
- A login for Codex agents (GitHub #113): Codex needs no login to start.
- Checking a token with the server: `claude auth status` calls a made-up token logged in;
  such an agent starts and fails at its first turn, as now.
- Refusing a resume: the decision keeps the wait for it (a resume at LADO's start must not
  fail the whole session for a login lost meanwhile).
- A change of the waiting agent's window, Needs you or `lado ls`: they stay as LAD-157 made
  them, for the fallback.

## Acceptance criteria

- AC-1: Claude Code not logged in: `lado start <repo> --provider claude` exits non-zero with
  "Claude Code is not logged in, so the session was not started: …"; lado.db holds no such
  session, no tmux session and no config folder is left.
- AC-2: the same for `POST /api/sessions` (400 with the reason) and the approved
  `start_session` MCP tool (an error to the supervisor; the question stays answered).
- AC-3: `lado start <git-url> --provider claude` and `lado start --new` refuse before
  cloning or making the folder; so does the UI's From scratch.
- AC-4: `spawn_worker(provider="claude")` (with or without `run`) returns the error "Claude
  Code is not logged in, so the worker was not started: …"; no worktree, branch, agent
  record or window is left, and a run's step still waits for a worker.
- AC-5: a project whose secrets or variables hold `CLAUDE_CODE_OAUTH_TOKEN` starts a Claude
  session and Claude workers with LADO's own login missing; the New session window's
  Project way offers Claude for it.
- AC-6: sessions mix CLIs: a Kilo session without any login starts; its Claude worker is
  refused while Claude Code has no login; a Claude session's Kilo worker starts.
- AC-7: Codex, OpenCode and Kilo agents start without a login, as before.
- AC-8: a resume is never refused: `lado start` of a stopped session, the UI's Resume and
  the resume at LADO's start; the supervisor waits for the login as in LAD-157, and the
  Resume window shows the amber note.
- AC-9: a login LADO cannot read (the status command fails or times out) refuses nothing;
  the agent starts with the warning it has now.
- AC-10: the New session window: Claude greyed "claude · not logged in", not preselected
  from the folder's last session, the red note with "Log in first" leading to Settings →
  Providers and environment, Start disabled; with Claude Code logged in, all as before.
