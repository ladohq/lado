# Codex agents share one login: design

Task: LAD-166 (with LAD-152). Change: `openspec/changes/codex-shared-login/` (proposal,
deltas of `provider-logins`, `agent-start-screens` and `container`, design.md D1-D11).
Mockup: run artifact `mockup-codex-login.html`. The human's decisions: #2148 (session
lado), #2163, #2168.

## What the user sees

**Logging in once** (mockup, screens 1-2)

- The user logs Codex in once: in a terminal (`codex login`, `codex login --device-auth`)
  or in Settings → Providers and environment → Codex CLI → "Log in…". Every Codex agent,
  new or running, then works with that login; the user's own Codex in a terminal shares it.
- The sheet "How do you pay for Codex?":
  - "ChatGPT plan — Plus, Pro, Business or Enterprise" → "Get a sign-in code": the login
    window shows OpenAI's link and a one-time code; the user opens the link on any device
    (a phone too) and enters the code; the window closes by itself and the row reads
    "Logged in · ChatGPT plan · Codex's login file".
  - "ChatGPT Business or Enterprise — access token" → paste a token from ChatGPT's admin
    console; kept as LADO's secret `CODEX_ACCESS_TOKEN` (Codex's counterpart of `claude
    setup-token`).
  - "Pay per use — OpenAI API key" → paste a key; kept as LADO's secret `OPENAI_API_KEY`.
  - "Log out…": asks first, naming the running Codex agents; for Codex's file it says the
    user's own Codex is logged out too and runs `codex logout`.
- In the container the same two variables can come from the secrets folder
  (`secrets/OPENAI_API_KEY`, `secrets/CODEX_ACCESS_TOKEN`), as `CLAUDE_CODE_OAUTH_TOKEN`
  does for Claude; the row then names the outside folder.
- A Mac whose Codex keeps its login in the system keyring: the row says "Not logged in",
  that agents cannot read the keyring, and offers "Log in…", whose login goes to Codex's
  file while the user's own Codex keeps the keyring.
- The note "Codex agents do not get this login yet" is gone.

**Starting a session**

- Codex with OpenAI's model and no login: a new session or worker is refused with "Codex
  CLI is not logged in, so the session was not started: log in in LADO's UI (Settings →
  Providers and environment, `lado ui`), or set OPENAI_API_KEY as LADO's secret or a project
  secret"; the New session window greys "codex · not logged in" out. A session LADO resumes
  by itself waits for the login and starts once it comes.
- Codex with a local model (Ollama, LM Studio, a provider with its own key): no login
  needed, as before.
- A Codex agent starts with no screen: no sign-in screen, no "Trust this folder?", no
  review of the repository's own Codex hooks, in each permission mode; it no longer
  downloads Codex's plugins catalogue at its start.

## How it works

- Each Codex agent keeps its own Codex home (Codex's own way to give one process its own
  config); its `auth.json` is a symbolic link to the user's `auth.json`. Codex writes that
  file in place and re-reads it before refreshing, so one refresh serves all (checked on a
  real ChatGPT login in this run: three agents refreshing at once, three rounds, all
  working; a refresh token reused seconds later was accepted).
- An `OPENAI_API_KEY` variable becomes the agent's own `auth.json` with that key (Codex's
  TUI does not read the variable); `CODEX_ACCESS_TOKEN` Codex reads itself.
- The agent's config.toml trusts the repository's main root (unless the user's Codex has an
  entry for it, `untrusted` kept), trusts the repository's own hooks by their hashes (a hook
  the user disabled stays disabled), switches plugins off and keeps the login in a file.
- Whether Codex's agents need a login follows the user's Codex config: OpenAI's provider
  (the default) or one with `requires_openai_auth` needs one; others do not. The core asks
  every provider `needs_login(env)`.

## Options weighed

The proposal's Why lists them: a link (taken), a copy per agent, a watcher copying back, the
shared `~/.codex` (rejected by the human); for a key variable, the agent's own key file
(taken) or a model provider of LADO's reading the variable; for plugins, off (taken) or a
shared cache.

Held against ROADMAP.md's next stages (ACP, cloud workers): the link is per machine; a
cloud worker gets a variable (an API key or an access token) instead, which this change
makes a first-class Codex login. Held against AGENTS.md's principles: neutral core
(`Provider.needs_login(env)`, `LoginChoice.action`, `LoginAction.help`,
`LoginStatus.keyring`, `Provider.keyring_note`; Codex's details stay in
`providers/codex.py`), one source of truth (one login file), no silent drop (a link or key
file LADO cannot write is a warning; a keyring login is named), only what is used (each new
field has Codex as its user), never touch the user's global config (nothing is written into
the user's Codex home; the login window runs Codex's own command, as for OpenCode and Kilo).

## Docs

- docs/design/agents.md: Codex's home, the link, the key file, the trust and hooks, plugins.
- docs/design/modules.md: `providers/codex.py`, `logins.py`, `server/launch.py`.
- docs/design/ui.md: Codex's sheet and login window, the keyring note.
- docs/cli.md: `lado start`'s refusal for Codex; `lado doctor`'s Codex line.
- docs/install.md and the headers of `docker/compose.yaml`, `docker/Dockerfile`: Codex's
  login in the container.
- BACKLOG.md: four entries closed (the proposal names them). CHANGELOG.md, 0.44.0
  (unreleased): Added (Codex login for all agents, from the UI), Fixed (trust question,
  plugins clone).

## Version

A feature and an API field: the minor; 0.44.0 is already the unreleased version.
