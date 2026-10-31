# Codex shared login Implementation Plan

**Goal:** One login of the user's Codex (a terminal, the UI's sign-in code, an access token
or an API key) serves every Codex agent, and a Codex agent starts with no screen.

**Architecture:** Each agent keeps its own Codex home; its `auth.json` becomes a link to the
user's (or a key file from `OPENAI_API_KEY`), settled in `first_hook_blocker`; its
config.toml trusts the repository and its hooks, keeps the login in a file and switches
plugins off. The core asks `Provider.needs_login(env)`; the login sheet gets a choice that
runs a login action.

**Tech Stack:** Python 3.10+ (stdlib, FastAPI, pydantic), pytest with the fake tmux and the
fake agent, React + TypeScript (vitest), Playwright (`pytest -m ui`), the real Codex CLI
0.162.0 for smoke tests.

**Spec:** `openspec/changes/codex-shared-login/` (proposal, deltas of `provider-logins`,
`agent-start-screens`, `container`, design.md D1-D11) and
`docs/superpowers/specs/2026-10-31-codex-shared-login-design.md`. Mockup: run artifact
`mockup-codex-login.html`.

## Global Constraints

- Codex's sheet: question `How do you pay for Codex?`; choices (id, title, detail, variable / action):
  - `chatgpt`, `ChatGPT plan — Plus, Pro, Business or Enterprise`, `Sign in with your ChatGPT account by a one-time code: LADO shows a link and a code, you open the link on any device and enter the code.`, action `login`
  - `token`, `ChatGPT Business or Enterprise — access token`, `Paste an access token your workspace admin made in ChatGPT's admin console (Codex access tokens).`, `CODEX_ACCESS_TOKEN`
  - `usage`, `Pay per use — OpenAI API key`, `Paste an API key from `platform.openai.com`.`, `OPENAI_API_KEY`
- Codex's login actions: `login` label `Get a sign-in code`, argv `codex login --device-auth -c cli_auth_credentials_store="file"`, help `Open the link, sign in and enter the code there. This window closes by itself once you are signed in.`; `logout` label `Log out…`, argv `codex logout -c cli_auth_credentials_store="file"`.
- `login_variables = ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN")`; `login_note = ""`.
- Methods: `ChatGPT plan`, `ChatGPT access token`, `Pay per use (API key)`; `file_words = "Codex's login file"`.
- Keyring note: `Your Codex keeps its login in the system keyring, which Codex agents cannot read. Log in here: the login goes to Codex's login file, and your own Codex keeps using the keyring.`
- Log out confirmation for Codex's file: `Log out of Codex? <agent> of <session>, … share this login and stop working until you log in again. Your own Codex in a terminal is logged out too.`; with no agent: `Log out of Codex? No agent of it runs now. Your own Codex in a terminal is logged out too.`
- Agent config.toml adds: `cli_auth_credentials_store = "file"`, `features.plugins = false`, the trust entry, the repository hooks' `trusted_hash`.
- Key file: `{"auth_mode": "apikey", "OPENAI_API_KEY": "<key>"}`, mode 600, never a link.
- The user's Codex home file in the agent's folder: `<agent home>/user-codex-home`, one line.
- Nothing is written into the user's Codex home by LADO itself; no provider name above `providers/`; no schema change.
- CHANGELOG.md under `## 0.44.0 (unreleased)`: Added and Fixed lines.
- Unit suites `-n auto`; integration and UI files with their markers; single node ids `-n0`.

## Review Focus

- The user's `auth.json` does not exist when the agent starts, and `~/.codex` does not
  exist either: the link is made dangling, no folder is created in the user's home, and the
  agent waits for its login (Task 4 test `test_a_link_to_a_missing_file_is_made_without_its_folder`).
- `<agent home>/auth.json` is a regular file left by an earlier key launch and the key is
  gone now: it is replaced by the link (Task 4 test `test_a_key_file_turns_back_into_the_link`).
- `CODEX_ACCESS_TOKEN` and `OPENAI_API_KEY` both set (one layer): the token wins, no key file
  is written (Task 4 test `test_the_access_token_wins_over_the_key`).
- A profile without `model_provider` while the top level names `ollama`: no login needed
  (Task 2 test `test_a_profile_without_a_provider_falls_back_to_the_top_level`).
- The repository's hooks file is invalid JSON: no hash is recorded, the agent is named as
  waiting for the review as today (Task 3 test `test_an_unreadable_repo_hooks_file_is_left_to_the_question`).

---

### Task 1: `Provider.needs_login(env)` in the core (D4)

**Files:**
- Modify: `src/lado/providers/base.py` (method on `Provider`)
- Modify: `src/lado/logins.py` (`refusal`, `Login.needs_login`, `read`)
- Modify: `src/lado/runtime.py` (`_held_for_login`)
- Modify: `src/lado/doctor.py` (`login_check`)
- Modify: `src/lado/server/launch.py` (`provider_logins`), `src/lado/server/provider_check.py` (`_row`)
- Modify: `tests/integration/fake_provider.py` (`FakeLoginProvider.needs_login`)
- Test: `tests/test_logins.py`, `tests/test_runtime.py`, `tests/test_doctor.py`, `tests/test_server_providers.py`

**Interfaces:**
- Produces: `base.Provider.needs_login(self, env: Mapping[str, str]) -> bool` (default
  `self.capabilities.needs_login`); `logins.Login.needs_login: bool` (set by `read` from the
  environment it read the status in).

- [ ] **Step 1: Failing tests.** In `tests/test_logins.py`:

```python
def test_refusal_asks_the_provider_with_the_environment(monkeypatch):
    seen = []

    class Picky(FakeLoginProvider):
        def needs_login(self, env):
            seen.append(env.get("MODEL"))
            return env.get("MODEL") == "cloud"

    provider = Picky("picky")
    monkeypatch.setattr(provider, "login_status", lambda env: base.LoginStatus(base.NO))
    assert logins.refusal(provider, {"MODEL": "local"}, logins.SESSION) is None
    assert logins.refusal(provider, {"MODEL": "cloud"}, logins.SESSION) is not None
    assert seen == ["local", "cloud"]
```

  In `tests/test_runtime.py` a launch with a provider whose `needs_login` returns False for
  the launch environment is not held although its status is `NO`; in `tests/test_doctor.py`
  `login_check` of a `Login` with `needs_login=False` and state `NO` is `info` "none"; in
  `tests/test_server_providers.py` a row's `needs_login` follows `Login.needs_login`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_logins.py tests/test_runtime.py tests/test_doctor.py tests/test_server_providers.py -k needs_login`; expect failures.
- [ ] **Step 3: Implement.**

```python
# base.py, in Provider
    def needs_login(self, env: Mapping[str, str]) -> bool:
        """Whether the CLI's agents, started with `env`, need a login (a new one is refused
        and a resumed one waits without it); by default Capabilities.needs_login."""
        return self.capabilities.needs_login
```

  `logins.refusal`: `if not provider.needs_login(env): return None`. `logins.read`: compute
  `env = environment(provider, layers)` once, `status = status or provider.login_status(env)`,
  `found.needs_login = provider.needs_login(env)`. `runtime._held_for_login`: `env =
  _launch_env(...)`, `if not agent_cli.needs_login(env): return False, []`. `doctor.login_check`:
  `if found.needs_login:`. `launch.provider_logins`: `needs_login=found.needs_login`.
  `provider_check._row` keeps `provider.capabilities.needs_login` (not read yet). Grep
  `capabilities.needs_login` afterwards: only `base.py`, `claude.py`, `provider_check._row`
  and the fake provider remain.
- [ ] **Step 4: Run** the four files with `-n auto`, then `uv run pytest -m integration -n auto tests/integration/test_provider_logins.py`; expect pass.
- [ ] **Step 5: Commit** `Whether a CLI's agents need a login is asked with the environment (LAD-166)`.

### Task 2: Codex's login state, variables and model (D3, D4, D6)

**Files:**
- Modify: `src/lado/providers/codex.py` (`login_status`, `needs_login`, `login_variables`, `login_note`, `keyring_note`, `_model_provider`)
- Modify: `src/lado/providers/base.py` (`LoginStatus.keyring: bool = False`, `Provider.keyring_note: str = ""`)
- Modify: `src/lado/server/launch.py` (`provider_logins`: note), `src/lado/doctor.py` (keyring line)
- Test: `tests/test_codex.py`, `tests/test_server_providers.py`, `tests/test_doctor.py`

**Interfaces:**
- Consumes: Task 1's `needs_login(env)`.
- Produces: `CodexProvider.login_status(env)` as the Global Constraints' methods;
  `codex._model_provider(config: dict) -> str`; `LoginStatus.keyring`.

- [ ] **Step 1: Failing tests** in `tests/test_codex.py` with `cli_logins.answer("codex", …)`
  (the fixture answers by `argv[0]`; add a matcher on the `-c` override where two runs
  differ):

```python
def test_an_api_key_variable_is_a_login_without_the_command(cli_logins):
    found = CodexProvider().login_status({"OPENAI_API_KEY": "sk-x", "HOME": "/h"})
    assert (found.state, found.method, found.variable, found.choice) == (
        base.YES, "Pay per use (API key)", "OPENAI_API_KEY", "usage")
    assert cli_logins.calls == []

def test_the_status_reads_the_file_store(cli_logins, codex_home):
    cli_logins.answer("codex", 0, "", "Logged in using ChatGPT\n")
    found = CodexProvider().login_status({"CODEX_HOME": str(codex_home)})
    assert (found.method, found.choice, found.file_words) == ("ChatGPT plan", "chatgpt", "Codex's login file")
    assert ["-c", 'cli_auth_credentials_store="file"'] == cli_logins.calls[0][0][3:5]

def test_an_access_token_variable(cli_logins):
    cli_logins.answer("codex", 0, "", "Logged in using personal access token\n")
    found = CodexProvider().login_status({"CODEX_ACCESS_TOKEN": "at-x", "OPENAI_API_KEY": "sk"})
    assert (found.method, found.variable, found.choice) == ("ChatGPT access token", "CODEX_ACCESS_TOKEN", "token")

def test_a_keyring_login_is_not_the_agents(cli_logins, codex_home):
    codex_home.mkdir(); (codex_home / "config.toml").write_text('cli_auth_credentials_store = "keyring"\n')
    cli_logins.answer("codex", lambda argv, env: (1, "", "Not logged in\n") if "-c" in argv else (0, "", "Logged in using ChatGPT\n"))
    found = CodexProvider().login_status({"CODEX_HOME": str(codex_home)})
    assert (found.state, found.keyring) == (base.NO, True)
```

  `needs_login` cases: no config → True; `model_provider = "ollama"` → False;
  `[model_providers.x] requires_openai_auth = true` with `model_provider = "x"` → True;
  `env_key` provider → False; `profile = "p"` with `[profiles.p] model_provider = "ollama"`
  → False; `test_a_profile_without_a_provider_falls_back_to_the_top_level`; an unreadable
  config → True. In `tests/test_server_providers.py`: a Codex row with `keyring=True` has the
  keyring note and no other note. In `tests/test_doctor.py`: its line is `warn` with the note.
  Rework the existing tests that expect `login_note` ("Codex agents do not get this login
  yet") and Codex's empty `login_actions`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_codex.py -k "login or needs"`; expect failures.
- [ ] **Step 3: Implement** in `codex.py`:

```python
FILE_STORE = ["-c", 'cli_auth_credentials_store="file"']
KEYRING_STORES = ("keyring", "auto")
METHODS = {"ChatGPT": ("ChatGPT plan", "chatgpt"), "API key": ("Pay per use (API key)", "usage"),
           "personal access token": ("ChatGPT access token", "token"), "access token": ("ChatGPT access token", "token")}

def _model_provider(config: dict) -> str:
    """The model provider Codex runs with this config: the chosen profile's, else the top
    level's, else OpenAI's."""
    profile = (config.get("profiles") or {}).get(config.get("profile") or "") or {}
    return str(profile.get("model_provider") or config.get("model_provider") or "openai")
```

  `needs_login(env)`: `_user_config(env, [])` (an error → True); `id = _model_provider(cfg)`;
  `return id == "openai" or bool(((cfg.get("model_providers") or {}).get(id) or {}).get("requires_openai_auth"))`.
  `login_status(env)`: the four steps of design.md D3 (`how` parsed as today, looked up in
  `METHODS`; an unknown `how` keeps it as the method, as today). `keyring_note` = the
  constraint's text. `launch.provider_logins`: `note = provider.keyring_note if status.keyring else provider.login_note`.
  `doctor.login_check`: `NO` with `status.keyring` → `WARN`, `f"not logged in: {provider.keyring_note}"`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_codex.py tests/test_server_providers.py tests/test_doctor.py tests/test_logins.py`; expect pass.
- [ ] **Step 5: Commit** `Codex's login is read as its agents get it: the file, a key or a token (LAD-166)`.

### Task 3: The agent's config: trust, repository hooks, plugins, file store (D2, D7, D8, D9)

**Files:**
- Modify: `src/lado/providers/codex.py` (`launch_command`)
- Test: `tests/test_codex.py`

**Interfaces:**
- Produces: config.toml keys `cli_auth_credentials_store`, `features.plugins`,
  `projects[<main root real path>].trust_level`, `hooks.state[<repo hook key>].trusted_hash`;
  the file `<home>/user-codex-home`.

- [ ] **Step 1: Failing tests** (read the written config.toml with `tomllib`):
  `test_an_untrusted_repo_is_trusted_by_the_agents_config` (no user entry → the main root's
  real path is `trusted`, for a worker in a linked worktree too);
  `test_the_users_untrusted_entry_is_kept`; `test_the_repos_hooks_are_trusted` (a
  `.codex/hooks.json` with a `Stop` command hook → its key and `hook_hash` in
  `hooks.state`; `first_hook_blocker` returns no reason);
  `test_a_hook_the_user_disabled_stays_disabled`;
  `test_an_unreadable_repo_hooks_file_is_left_to_the_question` (invalid JSON → no state
  entry for it; `first_hook_blocker` gives the review reason as today);
  `test_plugins_are_off_and_the_login_is_kept_in_a_file`;
  `test_the_users_codex_home_is_written_for_the_login` (`CODEX_HOME=/u` in `spec.environ`
  → `<home>/user-codex-home` reads `/u`; without it `$HOME/.codex`).
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_codex.py -k "trust or hook or plugins or codex_home"`; expect failures.
- [ ] **Step 3: Implement** in `launch_command`: `config["cli_auth_credentials_store"] = "file"`;
  `features["plugins"] = False`; trust:

```python
        if trust := _trust_entry(user.get("projects"), cwd):
            config["projects"] = {trust[0]: {"trust_level": trust[1]}}
        else:
            config["projects"] = {str(gitpaths.main_root(cwd).resolve()): {"trust_level": "trusted"}}
            trust = ("", "trusted")
```

  hooks, after LADO's own: for each `path` of `_repo_hook_files(cwd, home)` and each
  `(key, digest)` of `_hook_handlers(path)`, take the user's entry when it has `enabled`
  false, else `{"trusted_hash": digest}`; only when `trust[1] == "trusted"`. The user's Codex
  home: `user_home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else Path(env.get("HOME") or Path.home()) / ".codex"`
  from `spec.environ or os.environ`, written to `home / "user-codex-home"`. Update the
  module docstring and the comments of `_trust_keys` and `_repo_hook_files` (what LADO
  writes now).
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_codex.py`; expect pass.
- [ ] **Step 5: Commit** `A Codex agent trusts its repository and its hooks and fetches no plugins (LAD-166, LAD-152)`.

### Task 4: The agent's `auth.json` (D1)

**Files:**
- Modify: `src/lado/providers/codex.py` (`first_hook_blocker`, `_settle_login`, `_user_codex_home`)
- Test: `tests/test_codex.py`, `tests/test_login_wait.py`

**Interfaces:**
- Consumes: Task 3's `<home>/user-codex-home`.
- Produces: `_settle_login(home: Path, env: Mapping[str, str]) -> list[str]` (notes);
  `OSError` raised to `first_hook_blocker`, which returns it as `Blocker.warning`.

- [ ] **Step 1: Failing tests:**

```python
def test_the_agents_login_is_a_link_to_the_users(tmp_path):
    home, user = tmp_path / "agent", tmp_path / "user"
    home.mkdir(); user.mkdir(); (user / "auth.json").write_text("{}")
    (home / "user-codex-home").write_text(str(user))
    blocker = CodexProvider().first_hook_blocker(str(repo), {"CODEX_HOME": str(home)})
    assert (home / "auth.json").is_symlink()
    assert os.readlink(home / "auth.json") == str(user / "auth.json")
    assert blocker.notes == (f"LADO linked {home / 'auth.json'} to {user / 'auth.json'}",)
```

  Also: `test_a_link_to_a_missing_file_is_made_without_its_folder` (the user's folder does
  not exist → a dangling link, the folder still does not exist);
  `test_an_existing_link_is_left_with_no_note`; `test_an_api_key_becomes_the_agents_own_file`
  (mode `0o600`, JSON as the constraint, not a link);
  `test_the_access_token_wins_over_the_key` (both set → the link, no key file);
  `test_a_key_file_turns_back_into_the_link`; `test_a_read_only_home_is_a_warning`
  (`chmod 0o500` on the home → `Blocker.warning` names the path; skip as root). In
  `tests/test_login_wait.py`: a Codex agent's window that waited for `OPENAI_API_KEY` writes
  the key file before it runs the CLI (a fake `codex` on PATH that prints its home's
  `auth.json` kind).
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_codex.py -k "link or key or token"`; expect failures.
- [ ] **Step 3: Implement:**

```python
def _settle_login(home: Path, env: Mapping[str, str]) -> list[str]:
    """Make the agent's auth.json its login: a file with OPENAI_API_KEY when that is its
    login (Codex's TUI does not read the variable), else a link to the user's auth.json,
    which every agent and the user's own Codex share. The notes of what LADO wrote."""
    auth = home / "auth.json"
    key = env.get("OPENAI_API_KEY")
    if key and not env.get("CODEX_ACCESS_TOKEN"):
        if auth.is_symlink():
            auth.unlink()
        fd = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump({"auth_mode": "apikey", "OPENAI_API_KEY": key}, file)
        return [f"LADO wrote the API key of OPENAI_API_KEY into {auth}"]
    target = _user_codex_home(home) / "auth.json"
    if auth.is_symlink() and os.readlink(auth) == str(target):
        return []
    beside = home / ".auth.json.lado"
    beside.unlink(missing_ok=True)
    beside.symlink_to(target)
    os.replace(beside, auth)
    return [f"LADO linked {auth} to {target}"]
```

  `_user_codex_home(home)`: the first line of `home / "user-codex-home"`, else
  `Path(os.environ.get("HOME") or Path.home()) / ".codex"`. In `first_hook_blocker`, before
  reading the config: `try: notes = _settle_login(home, env) except OSError as error:
  return base.Blocker(warning=f"cannot give Codex agent its login in {home}: {error}")`;
  carry `notes` into every returned `Blocker`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_codex.py tests/test_login_wait.py`; expect pass.
- [ ] **Step 5: Commit** `Every Codex agent shares the user's Codex login, or gets the API key of its variable (LAD-166)`.

### Task 5: The sheet's API: a choice that runs an action (D5)

**Files:**
- Modify: `src/lado/providers/base.py` (`LoginChoice.action`, `LoginAction.help`)
- Modify: `src/lado/providers/codex.py` (`login_question`, `login_choices`, `login_actions`)
- Modify: `src/lado/server/models.py` (`LoginChoiceInfo.action`, `LoginActionInfo.help`, `ProviderLogins.logout_file`)
- Modify: `src/lado/server/launch.py` (`provider_logins`), `src/lado/server/provider_check.py` (`_row`)
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)
- Modify: `tests/integration/fake_provider.py` (a choice with an action on `fake-login`, using `fake-window`'s login script)
- Test: `tests/test_providers.py`, `tests/test_server_providers.py`

**Interfaces:**
- Produces: `LoginChoice(id, title, detail, variable="", action="")`;
  `LoginAction(id, label, argv, help="")`; API `choices[].action`, `actions[].help`,
  `logout_file: bool` (logged in from the CLI's own file and a `logout` action exists).

- [ ] **Step 1: Failing tests:** `test_each_choice_has_a_variable_or_an_action` over every
  registered provider (exactly one set; an action id among `login_actions()`; a variable
  among `login_variables`); `tests/test_server_providers.py`: Codex's row has the three
  choices and actions with their help; `logout_file` true for "Logged in using ChatGPT" and
  false for `OPENAI_API_KEY` from LADO's secrets (`from_lado` true there); `POST
  /api/providers/codex/login` with `logout` opens the window (fake tmux).
- [ ] **Step 2: Run** them with `-n0`; expect failures.
- [ ] **Step 3: Implement** the fields (dataclass defaults keep Claude's and OpenCode's
  declarations valid), Codex's declarations from the Global Constraints, the models, and
  `logout_file=status.state == YES and not status.variable and any(a.id == "logout" for a in provider.login_actions())`.
  Run `make web-types`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_providers.py tests/test_server_providers.py tests/test_provider_check.py` and `make web`; expect pass.
- [ ] **Step 5: Commit** `Codex's login sheet: a sign-in code, an access token or an API key (LAD-166)`.

### Task 6: The sheet in the UI (D5, D6)

**Files:**
- Modify: `web/src/LoginSheet.tsx` (`ChoiceSheet`: action choice, Log out of the file), `web/src/LoginWindow.tsx` (help from the action), `web/src/Providers.tsx` (comment)
- Modify: `docs/design/ui.md`
- Test: `web/src/LoginSheet.test.tsx`, `web/src/Providers.test.tsx`

**Interfaces:**
- Consumes: Task 5's API fields.

- [ ] **Step 1: Failing vitest tests:** a choice with `action` shows its detail and a primary
  button with the action's label, no field; pressing it calls `openLogin(name, action)` and
  shows the login window with the action's help line; the window's end closes the sheet;
  "Log out…" shows for `logout_file`, its confirmation has the file's text with the running
  agents, Yes opens the window with `logout`; Codex's row (`Providers.test.tsx`) has "Log
  in…", primary while `needs_login` and not logged in, and no "do not get this login" note;
  the keyring note shows as `pv-warn`.
- [ ] **Step 2: Run** `cd web && npx vitest run src/LoginSheet.test.tsx src/Providers.test.tsx`; expect failures.
- [ ] **Step 3: Implement** to the mockup (screens 2 and 3): reuse `WindowSheet`'s
  `start(action)`/`LoginWindow` inside `ChoiceSheet` (extract the shared state into a hook
  `useLoginWindow(name)` used by both); `LoginWindow` takes `help?: string`, default the
  current line. docs/design/ui.md: Codex's sheet, its window, the keyring note, Log out of
  the file.
- [ ] **Step 4: Run** `make web`; expect pass.
- [ ] **Step 5: Commit** `The login sheet runs a CLI's sign-in from a choice and logs out of its file (LAD-166)`.

### Task 7: UI e2e

**Files:**
- Modify: `tests/ui/test_providers_section.py`
- Test: the same

- [ ] **Step 1: Write** with `fake-login` (Task 5's action choice): open "Log in…", choose
  the action choice, "Get a sign-in code" shows the window with the link and the help line,
  sending the line logs in and the row reads "Logged in"; Save of a key; "Log out…" of the
  file with a running agent named; the same at 390×844. Screenshots to
  `<temp dir>/lado-ui-shots/` for desktop and phone.
- [ ] **Step 2: Run** `uv run pytest -m ui tests/ui/test_providers_section.py`; expect pass.
- [ ] **Step 3: Commit** `UI tests of the login sheet's sign-in code and log out (LAD-166)`.

### Task 8: Integration with the fake agent

**Files:**
- Modify: `tests/integration/fake_provider.py` (`FakeLoginProvider.needs_login(env)`: False when `FAKE_AGENT_LOCAL_MODEL` is set)
- Modify: `tests/integration/test_provider_logins.py`

- [ ] **Step 1: Write:** `lado start --provider fake-login` without a login is refused;
  with `FAKE_AGENT_LOCAL_MODEL=1` in the outside folder (a layer of the agents'
  environment, which `needs_login(env)` reads) it starts with no login; a resumed
  `fake-login` session waits and starts after a key is saved on the page (`PUT
  …/variables/…`); `GET /api/providers` gives `login_missing: false` with the local model.
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_provider_logins.py`; expect pass.
- [ ] **Step 3: Commit** `Integration tests of a login needed by the agents' model only (LAD-166)`.

### Task 9: Smoke with the real Codex

**Files:**
- Modify: `tests/smoke/test_smoke.py`, `tests/smoke/conftest.py` (Codex: `auth.json` by `codex login --with-api-key` in the test's Codex home; the smoke provider keeps `env_key`)

- [ ] **Step 1: Write:** `test_a_codex_agent_shares_the_users_login_file` (the agent's
  `auth.json` is a link to the test's `$CODEX_HOME/auth.json`, `codex login status` in the
  agent's home is logged in, the link stays after the session's first turn);
  `test_a_codex_session_starts_with_no_screen_in_each_mode` (a repository with
  `.codex/hooks.json` and no trust entry; `default`, `bypassPermissions`, none: the
  supervisor reaches its first hook with no human; its home has no `.tmp/plugins`); remove
  the trust answer for Codex in `real_clis.answer_dialogs` (`CODEX_TRUST`).
- [ ] **Step 2: Run** `make test-smoke PROVIDER=codex`; expect pass (Codex 0.162.0 installed).
- [ ] **Step 3: Commit** `Smoke tests of Codex's shared login and its start with no screen (LAD-166)`.

### Task 10: Docs, the image's headers, BACKLOG, CHANGELOG, live test

**Files:**
- Modify: `docs/design/agents.md`, `docs/design/modules.md`, `docs/cli.md`, `docs/install.md`
- Modify: `docker/compose.yaml`, `docker/Dockerfile` (headers), `tests/test_docker.py`
- Modify: `CHANGELOG.md` (BACKLOG.md's four entries were removed when the task was taken)
- Create: `tests/live/test_codex_login.py` (marker `live`, skipped without a ChatGPT login)

- [ ] **Step 1:** `tests/test_docker.py`: the headers name `CODEX_ACCESS_TOKEN`,
  `OPENAI_API_KEY`, `codex login --device-auth`, and no "Codex's login is not covered".
  Run; expect failure; edit the headers; run; expect pass.
- [ ] **Step 2:** Docs per the design doc's Docs list; CHANGELOG.md under `## 0.44.0
  (unreleased)`: Added "**Codex agents share your Codex login**" (log in once, in a terminal
  or Settings, by a sign-in code, an access token or an API key; `OPENAI_API_KEY` in the
  container's secrets works), Fixed "**Codex agents no longer ask to trust the repository**"
  and "**Codex agents no longer download the plugins catalogue at every start**".
- [ ] **Step 3:** The live test: with the human's Codex logged in with ChatGPT, a Codex
  session with a worker, both answer; the shared file made stale (`last_refresh` a month
  old); both answer again; the links stay; `codex login status` logged in. Written, not run
  in CI; the build report says "written, not run".
- [ ] **Step 4: Run** `make lint`, `make test`, `openspec validate codex-shared-login --strict`, `openspec validate --specs --strict`.
- [ ] **Step 5: Commit** `Docs and the image's headers for Codex's shared login (LAD-166)`.

## Regression

`make lint`; `make test`; `make web`; `uv run pytest -m integration -n auto
tests/integration/test_provider_logins.py tests/integration/test_session_start.py`; `uv run
pytest -m ui tests/ui/test_providers_section.py tests/ui/test_launch.py`; `openspec validate
codex-shared-login --strict`; `openspec validate --specs --strict`; CI's smoke (Codex cells
on Linux and macOS).
