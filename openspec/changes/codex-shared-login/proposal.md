Task: LAD-166

## Why

GitHub #113 "Save Codex authorization": after `codex login` the login is in the user's
`~/.codex/auth.json` (or `$CODEX_HOME/auth.json`), while every Codex agent runs with a
Codex home of its own (`CODEX_HOME=<LADO_HOME>/agents/<session>/<agent>`, the agent's
config folder) and does not see that file. So Codex with a ChatGPT login or a key stored by
`codex login` does not work in LADO: each agent stands on Codex's "Sign in with ChatGPT"
screen. The same root, the fresh home, gives two more faults: each agent asks "Trust this
folder?" for a repository the user's own Codex does not trust (LAD-152; LADO writes the
agent's config.toml anew at each launch, so an answer is lost), and Codex clones OpenAI's
plugins repository (about 100 MB) into each new home at its start (BACKLOG).

Why it is built so: the own home is Codex's native way to give one process its own
config.toml (`developer_instructions`, hooks, MCP servers, the permission profile), which
Codex itself writes into (trust, TUI state). LADO carries only the model settings
(`CARRIED`) and the trust into it, and nothing of the login.

The human's decision #2148 (session lado, #2140-#2148, comparison of options in its
artifacts `codex-options-1-vs-3` and `codex-like-claude`): the own home stays (option 1;
option 3, the shared `~/.codex` with `-c` overrides, rejected), but the user gets what
Claude Code gives: one login (in the UI or in a terminal) and every agent works, no trust
question, no agent standing silently on a screen at its start, no start without a login
where the model needs one, and Settings → Providers says what to do.

Checked in this run (Codex CLI 0.162.0 in the container; its source at `rust-v0.162.0`):

- **The link holds** (the task's first step, on a real ChatGPT account the human logged
  in by a device code into a throw-away home, logged out after): Codex writes `auth.json`
  in place (`FileAuthStorage::save`: open with truncate, write; no temporary file and
  rename), so an agent's `auth.json` that is a symbolic link to the user's file stays a
  link after a token refresh, the user's file (same inode) gets the new tokens, and the
  user's own `codex login status` stays logged in.
- **Agents refreshing at once do not log each other out**: three agents' homes linked to
  one file, the file made stale (an access token Codex cannot parse and `last_refresh` a
  month old, so each refreshes before its first request), three `codex exec` at once, three
  rounds: every run answered, one refresh per round won and the others reloaded it. Codex
  re-reads the file before a refresh and skips it when the file changed (a guarded
  reload); its lock is per process only. Worst case checked too: two homes with copies of
  one stale file refreshed one after the other with the same refresh token, 3 s and 7 s
  apart: OpenAI's server accepted the reused refresh token both times, and every copy kept
  working afterwards. So the same-second race is harmless on today's server.
- **Start screens on a clean home** (`-a on-request` and
  `--dangerously-bypass-approvals-and-sandbox`, the repository trusted in the agent's
  config): with a ChatGPT login or an API key, no screen before or after the first input;
  without a login, Codex's "Welcome to Codex … Sign in with ChatGPT" screen; without the
  trust entry, "Trust this folder?". A startup warning that bubblewrap is missing shows in
  the status line only (LAD-151, out of scope).
- **Variables**: Codex's TUI does not take `OPENAI_API_KEY` or `CODEX_API_KEY` from the
  environment (the sign-in screen shows; `CODEX_API_KEY` is read by `codex exec` only),
  and `codex login status` ignores them; `codex login --with-api-key` refuses a key typed
  in a terminal (stdin must not be a tty). It does take `CODEX_ACCESS_TOKEN`, an access
  token (`at-…`) of a ChatGPT Business or Enterprise workspace, made in ChatGPT's admin
  console, which Codex checks with OpenAI's server and never refreshes: Codex's
  counterpart of `claude setup-token` (the human's question #2163, answered #2168).
- **Plugins**: `features.plugins = false` in the agent's config.toml stops the clone (no
  `.tmp/plugins` in the home); the user's installed plugins live in the user's home and
  never reached an agent.
- **Keyring**: with `cli_auth_credentials_store = "keyring"` (or `auto` with a working
  keyring) Codex keeps the login under a key made from the Codex home's path, so an agent's
  home never finds it, and the user's `auth.json` may not exist.

The human's decisions (#2163, all as recommended; #2168):

1. Settings → Providers: Codex gets "Log in…"/"Change login…" with the sheet "How do you
   pay for Codex?" (mockup `mockup-codex-login.html`): a ChatGPT plan by a one-time code
   (`codex login --device-auth` in the login window), a ChatGPT Business or Enterprise
   access token (LADO's secret `CODEX_ACCESS_TOKEN`), or an OpenAI API key (LADO's secret
   `OPENAI_API_KEY`). The note "Codex agents do not get this login yet" goes.
2. A login kept in the system keyring is named on the row with "Log in…"; LADO's login
   goes to Codex's login file, the user's own Codex keeps the keyring.
3. "Log out…" in the sheet, with a confirmation naming the running Codex agents, and that
   the user's own Codex is logged out too when the login is Codex's file.
4. LADO trusts the session's repository in each agent's config.toml; an explicit
   `untrusted` of the user's own Codex is kept.
5. The repository's own Codex hooks (`.codex/hooks.json`, `.codex/config.toml` hooks) are
   taken by the agent without the review question, as Claude agents take a repository's
   `.mcp.json` (LAD-163).
6. Plugins off for agents instead of a shared cache.
7. A new Codex session or worker is refused without a login only when its model needs one
   (OpenAI's provider, or a provider with `requires_openai_auth`); a local model starts as
   before. A resumed agent waits for the login and starts by itself.
8. The supervisor asked (#2158, from the human's question): `OPENAI_API_KEY` in the
   container's secrets folder makes Codex work and counts as a login.

Options weighed for the login (root cause: the agent's home has no login):

- (a, taken) A symbolic link `<agent home>/auth.json` → the user's `auth.json`. Every
  agent and the user's own Codex share one login file and its refreshes, which Codex
  supports between processes (the guarded reload, checked above). Long-term cost: LADO
  depends on Codex writing the file in place; a Codex that starts to write a temporary file
  and rename it would replace the link with a file, and that agent's refreshes would stop
  reaching the others. Guarded by a smoke test of the link after a login command and by
  `TESTED_VERSION`.
- (b) A copy of `auth.json` per agent: the first refresh rotates the refresh token in one
  copy only. Rejected: the copies drift and one day the server stops taking the old token.
- (c) LADO watches the file and copies refreshed tokens back (the task's fallback):
  rejected, not needed once (a) is checked.
- (d) The shared `~/.codex` with `-c` overrides (option 3): rejected by the human (#2148).

Options weighed for an API key from a variable (Codex's TUI does not read one):

- (a, taken) LADO writes the agent's own `auth.json` with the key (the format `codex login
  --with-api-key` writes, mode 600) in place of the link. Native: Codex treats it as any
  key login. Cost: the key is on disk in the agent's home, the user's only, removed with
  the agent's folder; the variable already is a file in the secrets folder.
- (b) A model provider of LADO's in the agent's config (`env_key = "OPENAI_API_KEY"`):
  nothing on disk, but the agent then runs another provider than Codex's own `openai`
  (other id in its UI and state, and what Codex ties to the built-in provider). Rejected.

Held against the design principles: neutral core (the login's place, the trust and the
plugins stay in `providers/codex.py`; the core gets one neutral question,
`Provider.needs_login(env)`, and a choice of the login sheet that runs a login action);
one source of truth (the agents' login is the user's one file, read by Codex's own
`codex login status`; no second copy); no silent drop (a keyring login, a file LADO cannot
link and a key LADO cannot write are said on the row or as a launch warning); only what is
used (two login variables Codex reads or LADO hands it, no new setting, no schema change).

## What Changes

- **The agent's login** (`providers/codex.py`): before an agent's first hook LADO makes
  `<agent home>/auth.json` a symbolic link to the user's `auth.json`
  (`$CODEX_HOME/auth.json` of the agent's environment, else `~/.codex/auth.json`), also
  when that file does not exist yet; with `OPENAI_API_KEY` in the agent's environment (and
  no `CODEX_ACCESS_TOKEN`) a file with that key instead. The agent's config.toml sets
  `cli_auth_credentials_store = "file"`.
- **The login's state**: `codex login status` runs with `-c cli_auth_credentials_store=
  "file"` (what agents can read); `OPENAI_API_KEY` in the environment is logged in as "Pay
  per use (API key)"; `CODEX_ACCESS_TOKEN` as "ChatGPT access token"; Codex's file as
  "ChatGPT plan" or "Pay per use (API key)". A login only in the keyring is "not logged
  in" with a note that says so.
- **Login from the UI**: Codex's sheet asks "How do you pay for Codex?" with three choices
  (decision 1); the ChatGPT choice opens the login window with `codex login --device-auth`
  (into the file); the others keep a pasted value as LADO's secret, as Claude's sheet does.
  "Log out…": the secrets when the login is LADO's, else `codex logout` in the login window.
- **No start without a login** where the model needs one (decision 7), by a neutral
  `Provider.needs_login(env)` that replaces the reads of `Capabilities.needs_login`.
- **No screen at the start**: `trust_level = "trusted"` for the session's repository's main
  root in the agent's config.toml unless the user's Codex has an entry for it; the
  repository's own hooks trusted in the agent's config (their hashes, as LADO's own hooks
  are); `features.plugins = false`. `first_hook_blocker` then has nothing left to name but
  a hooks file it cannot read.
- docs/design/agents.md, docs/design/modules.md, docs/design/ui.md, docs/cli.md,
  docs/install.md, `docker/compose.yaml` and `docker/Dockerfile` headers (Codex's login in
  the container), BACKLOG.md (the four entries this closes: "Codex agents cannot log in",
  "Every Codex agent asks whether to trust…", "Codex clones its plugins repository at every
  start", "macOS: Codex with `cli_auth_credentials_store = "keyring"` is not warned
  about"), CHANGELOG.md under `## 0.44.0 (unreleased)`.
- A feature and an API change (the login sheet's choice runs an action): the minor,
  0.44.0, already the unreleased one.

## Scope

- The shared login, the API key and access token variables, the keyring case.
- Codex's login sheet, its login window and log out, at a phone's width too.
- The refusal and the wait for a Codex model that needs a login.
- The trust, the repository's hooks and the plugins, so a Codex agent starts with no screen
  in both of LADO's permission modes and with none.
- Tests: unit, web unit, UI e2e, integration with the fake agent, smoke with real Codex
  (no model), a live test with a ChatGPT login (at release, with the human).

## Out of scope

- LAD-151 (Codex's bubblewrap sandbox in the container): a separate task; its warning holds
  no agent.
- Answering permission requests during work from the UI: decided against by the human in
  LAD-163.
- A shared plugins cache: plugins are off for agents (decision 6); the user's installed
  plugins never reached agents.
- A Codex login per project: `CODEX_HOME` is reserved for projects (`projects` spec), and
  a project's `OPENAI_API_KEY` or `CODEX_ACCESS_TOKEN` secret already gives its agents a
  login of their own.
- Carrying the user's skills or other config from `~/.codex`: unchanged.
- The keyring as the agents' store: an agent's key would be another one per home; LADO
  keeps agents on the file.

## Acceptance criteria

- AC-1: With the user's Codex logged in with ChatGPT (`codex login` in a terminal or the
  UI's code), a new Codex session in a new repository starts, and its supervisor and a
  worker reach their first hook with no sign-in screen and no trust question, in the
  permission modes `default`, `bypassPermissions` and none.
- AC-2: Each Codex agent's `auth.json` is a symbolic link to the user's `auth.json` (also
  before that file exists); after a token refresh in one agent it is still a link and the
  user's `codex login status` is logged in.
- AC-3: With `OPENAI_API_KEY` as LADO's secret (or in the secrets folder, or the login
  shell), Codex's row shows "Logged in · Pay per use (API key) · <layer>", a session starts
  and its agents' `auth.json` holds that key (mode 600); with `CODEX_ACCESS_TOKEN`, "Logged
  in · ChatGPT access token · <layer>" and the agents get the variable.
- AC-4: Settings → Providers: Codex's row has "Log in…" (primary while a Codex agent's
  model needs a login) or "Change login…"; the sheet asks "How do you pay for Codex?" with
  the three choices of the mockup; "Get a sign-in code" opens the login window with the
  link and the code; Save keeps a token or key as LADO's secret; the note "Codex agents do
  not get this login yet" is gone.
- AC-5: "Log out…" asks first, naming the running Codex agents; with LADO's secret it
  removes it; with Codex's file it runs `codex logout` and the row reads "Not logged in".
- AC-6: With the login only in the keyring, the row shows "Not logged in", the note that
  Codex agents cannot read a login kept in the system keyring and "Log in…"; a login from
  the UI then lands in `auth.json`.
- AC-7: Without a login and a model of OpenAI's provider, `lado start --provider codex`
  and `spawn_worker` with `codex` are refused with the reason of `provider-logins`, and the
  New session window greys Codex out; with a local model (`model_provider = "ollama"` or a
  provider with `env_key`) they start as before; a Codex session LADO resumes by itself
  waits for the login and starts once the user logs in.
- AC-8: A Codex agent in a repository the user's Codex never trusted starts with no trust
  question and its config.toml trusts the repository's main root; a repository marked
  `untrusted` in the user's config stays untrusted for the agent.
- AC-9: A Codex agent in a repository with `.codex/hooks.json` the user never reviewed
  starts with no review question, the hooks enabled.
- AC-10: A Codex agent's home has no `.tmp/plugins` after its start.
