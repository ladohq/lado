## Context

A Codex agent is started by `CodexProvider.launch_command` (`src/lado/providers/codex.py`):
its Codex home is the agent's config folder (`base.config_dir(agent)`,
`<LADO_HOME>/agents/<session>/<agent>`), passed as `CODEX_HOME`; LADO writes its
config.toml anew at each launch with `CARRIED` keys of the user's own config (`model`,
`model_provider`, `model_providers`, `oss_provider`, `profile`, `profiles`,
`model_reasoning_effort`), the role, hooks with their trusted hashes, MCP servers, the
permission profile, `features` (`multi_agent`, `shell_snapshot`, `goals` off) and the
user's trust entry for the folder if there is one (`_trust_entry`). Nothing makes an
`auth.json` there. `first_hook_blocker` reads the agent's config.toml and names the trust
question and the repository's unreviewed hooks as the reason the agent waits.

The login: `CodexProvider.login_status` runs `codex login status` in the given
environment; `login_note` says the agents do not get it; `login_actions` is empty;
`Capabilities.needs_login` is False. The core asks `provider.capabilities.needs_login` in
`logins.refusal`, `runtime._held_for_login`, `doctor.login_check`,
`server.launch.provider_logins`, `server.provider_check` and `server.launch.provider_info`
(`login_missing`).

The login sheet (`web/src/LoginSheet.tsx`): a provider with `choices` (Claude) gets the
`ChoiceSheet`, each choice a pasted variable kept as LADO's secret (`PUT
/api/providers/{name}/variables/{variable}`), "Log out…" while the login is LADO's secret
(`DELETE /api/providers/{name}/login-secrets`); a provider with `actions` only (OpenCode,
Kilo) gets the `WindowSheet`, the login window at once (`POST /api/providers/{name}/login`
with an action id, `logins.open_window`, the agents' environment of no project).

A waiting agent's window (`lado.login_wait`) polls `login_status` with the agent's launch
environment (for Codex `CODEX_HOME` is the agent's home) and, once logged in, calls
`first_hook_blocker` again before it runs the CLI.

Facts of Codex 0.162.0 this design rests on, checked in this run (see the proposal's Why):
`auth.json` written in place; the guarded reload before a refresh; a reused refresh token
accepted seconds later; no screen with a login in either mode; `OPENAI_API_KEY` and
`CODEX_API_KEY` ignored by the TUI and by `codex login status`; `CODEX_ACCESS_TOKEN` read by
both (`load_auth`, after the in-memory store, before the file; a fake token makes the
status fail with "personal access token metadata request failed with status 403"); `codex
login --with-api-key` refuses a tty; `--device-auth` prints a link and a code and exits 0
once the code is entered; `features.plugins = false` stops the catalogue's clone;
`-c cli_auth_credentials_store="file"` is taken by `codex login`, `codex login status` and
`codex logout`; the keyring key is `cli|` and 16 hex digits of the SHA-256 of the Codex
home's real path.

## Goals / Non-Goals

Goals: one login of the user's Codex serves every Codex agent and the user's own Codex; a
variable can be that login in a container; no Codex screen holds an agent at its start;
Settings logs Codex in from the page, a phone too.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. The agent's `auth.json` is settled in `first_hook_blocker`

`CodexProvider.first_hook_blocker(cwd, env)` gets the agent's launch environment (its
`CODEX_HOME` and the login variables of the layer that won) before the window starts, and
again in the waiting window once a login is there (`lado.login_wait`). So the login is
settled there, not in `launch_command`: a key saved while the agent waits reaches it. A new
helper `_settle_login(home, env) -> list[str]` (the notes) does:

- `OPENAI_API_KEY` set and `CODEX_ACCESS_TOKEN` not: write `<home>/auth.json` as a regular
  file, mode 600 (open with `O_CREAT|O_TRUNC|O_NOFOLLOW` after unlinking a link, then
  `fchmod`), `{"auth_mode": "apikey", "OPENAI_API_KEY": <key>}`, the shape `codex login
  --with-api-key` writes. Note: "LADO wrote the API key of OPENAI_API_KEY into <path>".
- Otherwise: `<home>/auth.json` a symbolic link to the user's file: `<user home>/auth.json`,
  where the user's Codex home is `$CODEX_HOME` of the agent's environment before LADO's own
  `CODEX_HOME`, else `$HOME/.codex` (as `_user_config` finds the user's config.toml). An
  existing link to the same target is left as it is (no note); a file or another link is
  replaced (a link made beside it, then `os.replace`). Note: "LADO linked <home>/auth.json
  to <target>".

The waiting window's environment holds the agent's own `CODEX_HOME`, so the user's Codex
home is not known there. `launch_command` resolves it from `spec.environ` and writes it into
the agent's config folder as `user-codex-home` (one line, the path); `_settle_login` reads
it, and without it (an agent launched by an older LADO) falls back to `$HOME/.codex`. One
writer and one reader, both in the provider; nothing for it in config.toml, which is
Codex's.

A failure (the folder not writable, the key file not written) is `Blocker.warning`: the
agent starts and the human is told; never a silent drop.

### D2. The agents' Codex stays on the file store

`launch_command` writes `cli_auth_credentials_store = "file"` into the agent's
config.toml. Without it a user's `auto` or `keyring` is not carried today (not in
`CARRIED`), but Codex's default could change; with `keyring` an agent would read and write
a key of its own home's hash and its refreshes would never reach the shared file.

### D3. The login's state

`CodexProvider.login_status(env)`:

1. `OPENAI_API_KEY` in `env` and no `CODEX_ACCESS_TOKEN`: `YES`, method "Pay per use (API
   key)", `variable="OPENAI_API_KEY"`, `choice="usage"`; no command runs (Codex would not
   report it).
2. Else run `codex login status -c cli_auth_credentials_store="file"` (the store agents
   use). `Logged in using ChatGPT` → method "ChatGPT plan", `choice="chatgpt"`,
   `file=<CODEX_HOME>/auth.json`, `file_words="Codex's login file"`; an API key in the file
   → "Pay per use (API key)", `choice="usage"`, the same file (its line is `Logged in using
   an API key - <masked>`); `Logged in using personal access token` or `Logged in using
   access token` (read in Codex's source, `cli/src/login.rs`, `run_login_status`) →
   "ChatGPT access token", `choice="token"`, with `variable="CODEX_ACCESS_TOKEN"` when that
   variable is set (Codex reads it before the file), else the file (a token stored by
   `codex login --with-access-token`).
3. `Not logged in` with a keyring store in the user's config (`_user_config(env)`'s
   `cli_auth_credentials_store` in `keyring`, `auto`): run `codex login status` once more
   without the override; logged in there → `NO` with `keyring=True` (a new field of
   `LoginStatus`, False by default, neutral: "the CLI's own login is where agents cannot
   read it"); the row says so with the provider's `keyring_note` (D6).
4. A status that fails: `UNKNOWN` as today.

`login_variables = ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN")`: the first is named by
`logins.wait_reason` and `logins.refusal` ("or set OPENAI_API_KEY"), the one a container
user most likely has.

### D4. `Provider.needs_login(env)` replaces `Capabilities.needs_login`

A method of `base.Provider`, `needs_login(self, env: Mapping[str, str]) -> bool`, by
default `self.capabilities.needs_login`; Claude keeps the capability True and the default.
`CodexProvider.needs_login(env)`: the user's config (`_user_config(env)`; in a launch
environment, whose `CODEX_HOME` is the agent's, it reads the agent's config.toml, which
carries the same keys), the provider id `profiles[profile].model_provider` if a `profile`
names one, else `model_provider`, else `"openai"`; True when the id is `openai`, or
`model_providers[id].requires_openai_auth` is true; False otherwise (built-in `ollama`,
`lmstudio`, any provider with `env_key`). A config that cannot be read → True (the status
then decides; an unknown status never refuses).

Every reader switches to the method with the environment it reads the login in:
`logins.refusal` (its `env`), `runtime._held_for_login` (the launch environment),
`doctor.login_check` (`found` gets the environment: `logins.read` stores it as
`Login.needs_login: bool`, computed there), `server.launch.provider_logins` and
`provider_info` (`login_missing`) from that field. `Capabilities.needs_login` stays as the
default's source (one field per provider, no second list).

### D5. The sheet: a choice can run a login action

`base.LoginChoice` gets `action: str = ""` (a `login_actions` id) and `variable` may be
""; exactly one of them is set (a unit test over every provider). `models.LoginChoiceInfo`
gets `action`; `make web-types`. Codex's choices:

| id | title | detail | variable / action |
|---|---|---|---|
| `chatgpt` | ChatGPT plan — Plus, Pro, Business or Enterprise | Sign in with your ChatGPT account by a one-time code: LADO shows a link and a code, you open the link on any device and enter the code. | action `login` |
| `token` | ChatGPT Business or Enterprise — access token | Paste an access token your workspace admin made in ChatGPT's admin console (Codex access tokens). | `CODEX_ACCESS_TOKEN` |
| `usage` | Pay per use — OpenAI API key | Paste an API key from `platform.openai.com`. | `OPENAI_API_KEY` |

`login_question = "How do you pay for Codex?"`; `login_actions`:
`login` "Get a sign-in code" (`codex login --device-auth -c
cli_auth_credentials_store="file"`), `logout` "Log out…" (`codex logout -c
cli_auth_credentials_store="file"`: it removes the file the agents share and, for a ChatGPT
login, revokes its tokens on OpenAI's side; the user's keyring login, if any, stays).

`LoginSheet.tsx`: `ChoiceSheet` renders a choice with `action` as its detail and a primary
button with the action's label; the button opens the login window in the sheet (the
`WindowSheet`'s `start(action)` and `LoginWindow`, its end closes the sheet and the page
checks again, as now). The login window's help line stays "Open the link, sign in, then send
what it gives you (a code) from here." for OpenCode and Kilo; Codex's device code needs
nothing sent back, so the line comes from the action: `LoginAction.help: str = ""`, shown
when set ("Open the link, sign in and enter the code there. This window closes by itself
once you are signed in."), through `LoginActionInfo.help`.

"Log out…" in `ChoiceSheet`: shown when `from_lado` (as now) or when the login is the
CLI's file and the provider has a `logout` action (`ProviderLogins.logout_file: bool`,
computed in `provider_logins`: `status.state == YES and not status.variable and logout
action exists`). The confirmation's text for the file: "Log out of Codex? <agents> share
this login and stop working until you log in again. Your own Codex in a terminal is logged
out too." (no agents: "No agent of it runs now. Your own Codex …"); Yes opens the login
window with `logout`.

`Providers.tsx`'s comment "A CLI with no way to log in from the page (Codex) has no button"
goes; the row's rule (one button when `choices` or `actions`) is unchanged.

### D6. The keyring note

`LoginStatus.keyring` (D3) makes `server.launch.provider_logins` put the note "Your Codex
keeps its login in the system keyring, which Codex agents cannot read. Log in here: the
login goes to Codex's login file, and your own Codex keeps using the keyring." into
`ProviderLogins.note` in place of `login_note` (which is "" for Codex now). The text is
the provider's (`Provider.keyring_note: str = ""`, Codex's set), so the core names no CLI.
`lado doctor`'s line for that state: `warn`, "not logged in: <the note>".

The existing `keychain_login` (macOS graphical session) stays None for Codex: agents read
the file, never the keyring (D2). BACKLOG's "macOS: Codex with keyring is not warned
about" is closed by D6.

### D7. The trust

`launch_command`: `_trust_entry(user projects, cwd)` as now; with none, `projects =
{str(main_root.resolve()): {"trust_level": "trusted"}}` (`gitpaths.main_root(cwd)`, the
key Codex looks up third, after the folder and the project root, all by real path; a
worker's worktree is a linked worktree, whose main root is the repository). An explicit
user entry, `trusted` or `untrusted`, is carried as today. A folder that is no git
repository (no main root): its own real path. `first_hook_blocker`'s trust reason then
cannot happen for a LADO-written config; it stays for a config LADO did not write (a
hand-edited home), unchanged.

### D8. The repository's hooks

`launch_command`: for each of `_repo_hook_files(cwd, home)` and each `(key, digest)` of
`_hook_handlers(path)`, `config["hooks"]["state"][key] = {"trusted_hash": digest}` unless
the user's entry for that key has `enabled = false`, which is carried as it is (today's
loop keeps the user's entries; it now adds LADO's for the rest). Only when the folder is
trusted (an `untrusted` folder loads no repository hooks). `_unreviewed` then finds none
for a LADO-written config; `first_hook_blocker` keeps the check for a file LADO could not
read (no handlers read → no hash → Codex asks; the reason stays as today).

### D9. Plugins off

`features.plugins = false` in `launch_command`'s `features`. Checked: no `.tmp/plugins`
(curated catalogue) after a start; `features.apps` and `remote_plugin` stay as they are
(they read nothing into the home at start).

### D10. Texts of the core

`logins.wait_reason` and `logins.refusal` already name the provider's title and first
login variable: "Codex CLI is not logged in: … or set OPENAI_API_KEY …". No change.

### D11. Tests

| Requirement | Layer | Tests |
|---|---|---|
| Every Codex agent shares the user's Codex login | unit; smoke | `tests/test_providers.py` (link made, kept, replaced, dangling target, CODEX_HOME of the environment, the `user-codex-home` file, warning when the folder is read-only); `tests/smoke/test_smoke.py`: a Codex agent's `auth.json` is a link to the test's Codex home after `codex login --with-api-key` there, and the agent starts with no screen |
| A login variable gives Codex agents their login | unit; integration | `tests/test_providers.py` (key file mode 600, token wins, back to the link); `tests/test_logins.py` (layers); `tests/integration/test_provider_logins.py`: a waiting Codex-like fake agent starts once `OPENAI_API_KEY` is saved (fake provider with `needs_login(env)`) |
| Codex's model decides whether its agents need a login | unit; integration | `tests/test_providers.py` (`openai`, none, profile, `requires_openai_auth`, `ollama`, unreadable); `tests/test_logins.py`, `tests/test_runtime.py`, `tests/test_doctor.py`, `tests/test_server_launch.py` (`login_missing`); `tests/integration/test_provider_logins.py`: `lado start --provider codex` refused, a fake provider whose `needs_login(env)` follows a variable |
| LADO reads each CLI's login (Codex scenarios) | unit; smoke | `tests/test_providers.py` with `cli_logins` answers; smoke `test_each_clis_login_is_read_from_its_own_command` for Codex with a key file |
| Codex's sheet asks how the human pays; the login window (Codex) | web unit; UI e2e | `web/src/LoginSheet.test.tsx` (choice with action, help line, Log out of the file); `tests/ui/test_providers_section.py` with `fake-login` actions: the sheet, Get a sign-in code opens the window, Save a key; screenshots at desktop and phone width |
| A Codex login kept in the keyring is named | unit | `tests/test_providers.py` (two status runs), `tests/test_server_providers.py` (note), `web/src/Providers.test.tsx` |
| Logging out of Codex asks first | web unit; UI e2e | `LoginSheet.test.tsx` (texts, agents named, the window with `logout`); `tests/ui/test_providers_section.py` |
| A Codex agent trusts its repository; takes its hooks; no plugins; no screen in every mode | unit; smoke | `tests/test_providers.py` (config.toml: trust key, untrusted kept, hook hashes, disabled kept, `plugins = false`, `cli_auth_credentials_store`); smoke: a Codex session in a repository with `.codex/hooks.json` and no trust entry reaches its first hook with no human in `default`, `bypassPermissions` and no mode, and its home has no `.tmp/plugins` |
| The headers say how the agent CLIs log in | unit | `tests/test_docker.py` |
| AC-1, AC-2 with a real ChatGPT login | live | `tests/live/`: a Codex session on the human's login, a worker, the link after a refresh (forced by a stale `last_refresh`); only at release with the human (the image has no ChatGPT account in CI) |

Regression: `make lint`, `make test`, `make web`, `uv run pytest -m integration
tests/integration/test_provider_logins.py tests/integration/test_session_start.py`, `uv run
pytest -m ui tests/ui/test_providers_section.py tests/ui/test_launch.py`, `openspec validate
codex-shared-login --strict`, `openspec validate --specs --strict`; CI's smoke runs the
Codex cells.

## Risks / Trade-offs

- **A Codex that writes `auth.json` by rename** would turn an agent's link into a file on
  its first refresh; the others keep the old refresh token, which the server took seconds
  later in this run but may not take days later. Guard: the smoke test checks the link after
  Codex writes the file (`codex login --with-api-key` writes through the same `save`), and
  `TESTED_VERSION` warns on another version.
- **OpenAI advises against one `auth.json` for concurrent jobs** (docs/research,
  cloud-workers R4): written for copies across machines; on one machine Codex's guarded
  reload serves several processes, as a user's several terminals. The same-second race
  sends one refresh token twice; today's server accepts it.
- **A key on disk** (D1): mode 600 in the agent's folder under LADO_HOME, the user's only,
  as Codex's own key login keeps it; removed with the agent's folder.
- **Log out revokes the shared login** for every agent and the user's own Codex: the
  confirmation says so.
