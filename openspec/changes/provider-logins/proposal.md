Task: LAD-157

## Why

Symptom: an agent CLI works only when it is logged in (Claude Code, Codex, OpenCode,
Kilo), but nothing in LADO's UI says whether it is, or how, and nothing there can log it
in. In Docker a new user must know `docker compose exec -it lado claude` or a token file in
`secrets/` (docs/install.md). Without it the agent stands silently: Claude Code shows its
first-run screen (the theme) and no hook comes, so the agent stays `starting` with no
reason, or, before LAD-106, was shown as the folder-trust question (LAD-104). From the UI,
and from a phone in particular, there is no way out.

Cause: LADO never asks a CLI about its login. The only thing it reads before a launch is
Claude Code's folder trust (`ClaudeProvider.first_hook_blocker`); the System panel shows
each CLI's version only (`doctor.provider_status`); the UI's terminal is bound to an
agent's tmux window; and the only LADO-wide variables are the outside folder
(`LADO_ENV_DIR`, `/run/secrets`, read-only in Docker) and the login shell, neither of
which the UI can write.

Checked by hand in LADO's container (Claude Code 2.1.295, Codex 0.162.0, OpenCode
1.18.35, Kilo 7.8.8, throwaway homes, 2026-10-28):

- `claude auth status --json` (about 0.1 s) gives `loggedIn` and `authMethod`
  (`claude.ai`, `oauth_token`, `api_key`, `none`), for a key also `apiKeySource`; exit 1
  when not logged in. It does not check a token with the server: a made-up
  `CLAUDE_CODE_OAUTH_TOKEN` is `loggedIn: true`.
- `claude auth login --claudeai` (or `--console`) without a browser prints `If the
  browser didn't open, visit: <url>` and `Paste code here if prompted >`, and waits for
  the code.
- A fresh Claude Code config shows the first-run screen (theme) before any hook, also with
  a token. With `hasCompletedOnboarding: true` in its global config it starts straight
  away with a token; without a login it then starts with "Not logged in · Run /login",
  runs its hooks and looks ready. With an `ANTHROPIC_API_KEY` it asks "Detected a custom
  API key in your environment… Do you want to use this API key?" (default "No") until the
  key's last 20 characters are in `customApiKeyResponses.approved`.
- `codex login status`: `Not logged in` (exit 1) or `Logged in using …`; it reads
  `CODEX_HOME/auth.json`; an `OPENAI_API_KEY` in the environment does not count.
- `opencode auth list` and `kilo auth list`: the credentials file's path, one line per
  credential (`<Provider> <api|oauth|wellknown>`), and a section `Environment` with each
  provider whose key variable is set (`OpenAI OPENAI_API_KEY`); ANSI colours in the
  output. Both work with no login on their free models.

Options weighed with the human (question #1891, all recommendations taken):

- The login window: A (taken) the CLI's own login command in a terminal on the page, with
  a clickable link, a field that sends text with Enter and arrow, Enter and Esc keys, so
  it works from a phone; one window for every CLI. B: LADO's own form that reads the link
  out of each CLI's text: nicer on a phone, but LADO would parse text that changes between
  versions, and OpenCode's and Kilo's menus would each need a form. Long-term cost of A:
  one more terminal kind (a login window) next to the agent's; no CLI-specific parsing.
- An agent without a login: (a, taken) it waits in Needs you with the reason and starts by
  itself once the login is there; (b) refuse to start it, so the human starts again; (c)
  start the CLI on its own login screen, to log in in the agent's terminal (hard from a
  phone). Long-term cost of (a): a small wait step in the agent's window before its CLI.
- Where a token or key typed in the UI goes: a LADO-wide secrets folder in LADO_HOME, as a
  project's secrets are kept (taken), rather than the outside folder (read-only in
  Docker) or lado.db (no place for values nobody reads back).
- Claude Code's first-run screens: LADO records `hasCompletedOnboarding` (and the approval
  of the API key it gives) through the writer of LAD-106 (taken); otherwise even a logged
  in Claude agent stands on the theme screen. The exception to "Never touch the user's
  global agent config" grows by these two keys and says so.

Held against the design principles: neutral core (every provider answers the same
questions through the provider interface: its login state, its login and logout commands,
the variables that log it in, whether its agents need a login; the core and the UI know
no CLI's output), no silent drop (a CLI whose agents cannot use a login, Codex, says so on
the page; a status LADO cannot read is shown as unknown with why, never as "not logged
in"), one source of truth (the CLI's own command is the state; the list of secrets is the
folder's files), only what is used (the UI writes only the variables a provider names as
its login).

## What Changes

- **Settings → Providers and environment** replaces the placeholder: for each of the four
  CLIs its version, whether it is logged in and how (a subscription, a token, an API key,
  the credentials of OpenCode and Kilo, none), where the login comes from (the CLI's file,
  a variable and its layer), the agents that wait for it, the projects that set a login
  variable of their own, and `lado doctor`'s warnings about providers; "Check again".
- **The login window**: a terminal on the page that runs the CLI's own login (`claude
  auth login --claudeai` or `--console`, `opencode auth login`, `kilo auth login`), with a
  clickable link, a "Text to send" field and ↑ ↓ Enter Esc keys; it closes when the command
  ends and the status is read again. Log out: `claude auth logout` with a confirmation that
  names the running Claude agents; OpenCode's and Kilo's `auth logout` in the window.
- **Login variables as LADO's secrets**: `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY`
  typed on the page (the secret field of the project page) go to
  `<LADO_HOME>/secrets/<NAME>` (600, folder 700), never shown or returned again, removed
  with a confirmation. A new layer of every agent's environment: login shell → outside
  folder → **LADO's secrets** → project → LADO and the provider.
- **An agent whose CLI needs a login and has none waits**: before a Claude agent starts,
  LADO asks `claude auth status`; when it is not logged in, the agent waits in Needs you
  and `lado ls` with `Claude Code is not logged in: log in in Settings → Providers and
  environment, or set CLAUDE_CODE_OAUTH_TOKEN; the agent starts by itself once you do`;
  its window waits instead of starting the CLI, checks again every few seconds, and starts
  it once a login is there. Needs you has a "Log in…" button that leads to the section.
- **Claude Code's first run**: when Claude Code is logged in and its config lacks
  `hasCompletedOnboarding`, LADO sets it before the agent starts; when the agent gets
  `ANTHROPIC_API_KEY` and the key's last 20 characters are in neither list of
  `customApiKeyResponses`, LADO adds them to `approved`. Both through `edit_config`, each
  told and logged as the trust is.
- **Codex**: version and its login state as `codex login status` gives it for the user's
  Codex home, with the honest note that Codex agents do not get that login yet (GitHub
  #113): no login button.
- **`lado doctor`** prints a login line per installed CLI; the page shows the provider
  checks.
- AGENTS.md's exception grows by the two keys; docs/design/ui.md (Providers and
  environment), docs/design/agents.md, docs/design/modules.md, docs/cli.md (`lado doctor`,
  `lado ls`), docs/install.md (Docker: log in from the UI), the compose and Dockerfile
  headers, CHANGELOG.md (`## 0.44.0 (unreleased)`, Added).
- A feature: the minor version (0.44.0, already the unreleased one).

## Scope

- The four CLIs' login state on the page and in `lado doctor`.
- Logging in and out of Claude Code, OpenCode and Kilo from the page, also from a phone.
- Claude Code's token and API key as LADO's secrets, and the layer they make.
- Claude agents that wait for a login, with the reason, in Needs you and `lado ls`, and
  start by themselves.
- Claude Code's first-run screens that hold a logged-in agent (the theme, the API key's
  question).
- Tests: unit, API, an integration test with the fake agent, UI e2e, the smoke test with
  the real CLIs.

## Out of scope

- A login Codex agents can use: GitHub #113 (each Codex agent has its own `CODEX_HOME`);
  the page only says so. A login button for Codex until then: it would log in something
  no agent uses.
- Codex's folder trust (LAD-152), Claude Code's folder trust (LAD-106, done).
- A login check at the start of Codex, OpenCode and Kilo agents: they run with models that
  need no login (a local model, the free models), so a missing login is no reason to hold
  them.
- A `lado login` command: in a terminal the CLIs' own commands do it (#1891, question 8).
- A CLI to set LADO's secrets: the login shell and the outside folder already give
  variables to the whole LADO; the page is for the UI and the phone.
- Any other variable as LADO's secret: only the variables a provider names as its login
  (only what is used); a project's secrets stay per project.
- Clickable links and the phone keys in the agents' terminals: the login window only;
  typing into an agent's terminal from a phone stays its own task (docs/design/ui.md).
- Claude Code's bypassPermissions disclaimer and the approval of a repository's
  `.mcp.json` servers: other first-run screens, still in BACKLOG.md.
- Checking a token with the provider's server: the CLIs' status commands do not, and LADO
  sends nothing of its own to them.

## Decisions for the record

The technical decisions D1-D14 are in `design.md`.

## Acceptance criteria

- AC-1. Settings shows, for each installed CLI, its version and its login state as its
  own status command gives it (logged in and how, not logged in, or unknown with why),
  where the login comes from, and for Codex the note that its agents do not get it.
- AC-2. In Docker without a Claude login, a session started from the UI (a phone's width
  too) shows its supervisor in Needs you with the login reason and a "Log in…" button;
  `lado ls` prints the same reason.
- AC-3. The login window runs `claude auth login`; its link opens, the code sent with
  "Text to send" logs Claude Code in; the window closes and the page shows "Logged in".
- AC-4. The waiting agent then starts by itself, with no restart, and passes Claude Code's
  first-run screen without the human (LADO records `hasCompletedOnboarding`); the next
  Claude agent starts straight away.
- AC-5. A token saved on the page reaches every agent started after it (and a waiting
  one), wins over the login file, shows as "token · LADO's secret"; removing it brings the
  previous login back. Its value is in no answer of the API, no log, lado.db or the bug
  report.
- AC-6. An `ANTHROPIC_API_KEY` given to Claude agents does not stop them at "Detected a
  custom API key" (LADO records its approval), unless the human rejected that key before.
- AC-7. Log out of Claude Code asks first, naming the running Claude agents; after it the
  page shows "Not logged in".
- AC-8. OpenCode and Kilo: their credentials and environment keys are shown; "Add a
  login…" and "Log out of one…" open their own `auth login`/`auth logout` in the window.
- AC-9. `lado doctor` prints one login line per installed CLI; the page shows the provider
  warnings of `lado doctor`.
- AC-10. A status LADO cannot read (the command fails or times out) never holds an agent
  and shows as unknown with why.
