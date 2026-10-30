# Refuse a start without a login Implementation Plan

**Goal:** A new session or worker whose agent CLI needs a login (Claude Code) and has none
is refused before anything is stored, in the CLI, the UI and the MCP tools; the New
session window shows it before Start; a resume still waits for the login (LAD-157).

**Architecture:** `lado.logins.refusal` decides and words the refusal; `runtime.check_login`
raises it as a `LadoError` from `start_session` (new sessions only) and `spawn_worker`, and
from the CLI's and server's clone/scratch paths before a folder is made. The providers list
(`GET /api/providers`) gains `login_missing` (and `?project=`), from which `Launch.tsx`
greys a CLI out.

**Tech Stack:** Python 3.10+ (stdlib, FastAPI, pydantic), pytest with the fake tmux and the
fake agent, React + TypeScript (vitest), Playwright (pytest -m ui).

**Spec:** `openspec/changes/refuse-start-without-login/` (proposal, delta of
`provider-logins`, design.md D1-D8) and
`docs/superpowers/specs/2026-10-30-refuse-start-without-login-design.md`. Mockup: run
artifact `mockup-start-without-login.html`.

## Global Constraints

- Session refusal text: `<title> is not logged in, so the session was not started: log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set <first login variable> as LADO's secret or a project secret`
- Worker refusal text: `<title> is not logged in, so the worker was not started: ask the human to log in in Settings → Providers and environment, or start the worker with another provider`
- Window option: `<name> · not logged in` (disabled); red note: `<CLI title> is not logged in: its agents cannot start.` + link `Log in first`; Resume note (amber, `field-note warn`): `⚠ <CLI title> is not logged in: the supervisor waits until you log in.` + link `Log in…`.
- Only `NO` refuses; `UNKNOWN` and providers without `needs_login` never do.
- A resume (a stored session of that name) is never refused.
- No provider name above `providers/`: the rule goes by `capabilities.needs_login`.
- CHANGELOG.md: one line under `## 0.44.0 (unreleased)` → `### Changed`.
- Tests run with `-n auto` for suites; integration and UI files with their markers.

## Review Focus

- A refusal after a partial write: the check must come before `state.add_session`,
  `exclude_worktrees`/`git worktree add`, `clone.clone`, `scratch.make`. Each refusal test
  asserts nothing is left (lado.db, tmux calls, worktree, branch, config dir, folder).
- `lado start` of a stopped session without a login: must resume and wait, not refuse
  (`resume=None` path with `old` set).
- A project's secret that logs in: the check must read `_base_env(project)` with the
  project's layer, not `logins.environment()` without it.
- Mixed sessions: `spawn_worker(provider="kilo")` in a Claude session without a login must
  start; `spawn_worker(provider="claude")` in a Kilo session must refuse.
- The window when the providers list fails or is still loading: no note, no crash; Start
  stays as today's rules say.

---

### Task 1: `logins.refusal` and `runtime.check_login`

**Files:**
- Modify: `src/lado/logins.py` (after `wait_reason`)
- Modify: `src/lado/runtime.py` (next to `LadoError` and `_held_for_login`)
- Test: `tests/test_logins.py`, `tests/test_runtime.py`

**Interfaces:**
- Produces: `logins.SESSION = "session"`, `logins.WORKER = "worker"`;
  `logins.refusal(provider: base.Provider, env: Mapping[str, str], what: str) -> str | None`;
  `runtime.NotLoggedIn(LadoError)`;
  `runtime.check_login(agent_cli: providers.Provider, base_env: dict[str, str], what: str) -> None`;
  `runtime.check_start_login(provider: str | None, project: str | None) -> None`.

- [ ] **Step 1: Write the failing tests** (`tests/test_logins.py`, with the `cli_logins` fixture used by `tests/test_runtime.py`)

```python
def test_a_cli_that_needs_a_login_and_has_none_is_refused(cli_logins):
    cli_logins.logged_out()
    claude = providers.get("claude")
    assert logins.refusal(claude, {}, logins.SESSION) == (
        "Claude Code is not logged in, so the session was not started: log in in LADO's UI "
        "(Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN "
        "as LADO's secret or a project secret"
    )
    assert logins.refusal(claude, {}, logins.WORKER) == (
        "Claude Code is not logged in, so the worker was not started: ask the human to log "
        "in in Settings → Providers and environment, or start the worker with another provider"
    )


def test_a_login_or_an_unknown_one_or_no_need_refuses_nothing(cli_logins):
    claude = providers.get("claude")
    cli_logins.logged_in()
    assert logins.refusal(claude, {}, logins.SESSION) is None
    cli_logins.answer("claude", "timed out")
    assert logins.refusal(claude, {}, logins.SESSION) is None
    cli_logins.logged_out()
    assert logins.refusal(providers.get("kilo"), {}, logins.SESSION) is None
```

(`cli_logins` is `tests/conftest.py`'s `CliLogins`: `logged_in()`, `logged_out()`,
`answer("claude", "<problem>")` for an unreadable status. Task 4 adds
`logged_in_with(variable)`: logged in only when the env asked holds `variable`, else
logged out — `run` gets the env, so the answer is chosen there.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_logins.py -n0 -k "refused or refuses_nothing"`
Expected: FAIL, `module 'lado.logins' has no attribute 'refusal'`

- [ ] **Step 3: Implement**

```python
# lado/logins.py, after wait_reason
SESSION, WORKER = "session", "worker"  # what a refusal (refusal) does not start


def refusal(provider: base.Provider, env: Mapping[str, str], what: str) -> str | None:
    """Why a new `what` (SESSION or WORKER) of `provider` is not started: its agents need a
    login (Capabilities.needs_login) and its status in `env` says none. None otherwise, also
    when the status cannot be read: that never refuses (the launch warns)."""
    if not provider.capabilities.needs_login:
        return None
    if provider.login_status(dict(env)).state != base.NO:
        return None
    head = f"{provider.title} is not logged in, so the {what} was not started"
    if what == WORKER:
        return (
            f"{head}: ask the human to log in in {SETTINGS}, or start the worker with "
            "another provider"
        )
    names = provider.login_variables
    how = f"log in in LADO's UI ({SETTINGS}, `lado ui`)"
    if names:
        how += f", or set {names[0]} as LADO's secret or a project secret"
    return f"{head}: {how}"
```

```python
# lado/runtime.py, after class LadoError
class NotLoggedIn(LadoError):
    """A new session or worker refused: its CLI needs a login and has none
    (lado.logins.refusal)."""


# next to _held_for_login
def check_login(agent_cli: providers.Provider, base_env: dict[str, str], what: str) -> None:
    """Refuse a new session or worker (`what`, logins.SESSION or WORKER) of `agent_cli`
    whose CLI needs a login and has none in `base_env`, the environment it would start
    from; called before anything of it is stored or made."""
    if reason := logins.refusal(agent_cli, base_env, what):
        raise NotLoggedIn(reason)


def check_start_login(provider: str | None, project: str | None) -> None:
    """Before a clone or a new folder for a new session (lado start <git-url>, --new, the
    UI's From scratch): refuse as start_session would, when the provider is known now:
    given, or the only one installed on the agents' PATH. Otherwise start_session decides."""
    base_env = _base_env(project)
    if provider is None:
        path = base_env.get("PATH", os.defpath)
        found = suggested_provider(None, lambda p: shutil.which(p.command, path=path) is not None)
        if found is None:
            return
        provider = found.provider
    check_login(_provider(provider), base_env, logins.SESSION)
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_logins.py -n0`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lado/logins.py src/lado/runtime.py tests/test_logins.py
git commit -m "A new session or worker of a CLI without its login has a refusal (LAD-161)"
```

### Task 2: `start_session` and `spawn_worker` refuse

**Files:**
- Modify: `src/lado/runtime.py` (`start_session` after `_check_commands(env, base_env)`; `spawn_worker` after `_check_commands(env, base_env)`)
- Test: `tests/test_runtime.py`, `tests/test_runtime_projects.py`, `tests/test_runtime_start_approved.py`

**Interfaces:**
- Consumes: `runtime.check_login`, `logins.SESSION`, `logins.WORKER` (Task 1).

- [ ] **Step 1: Write the failing tests** (`tests/test_runtime.py`)

```python
SESSION_REFUSED = (
    "Claude Code is not logged in, so the session was not started: log in in LADO's UI "
    "(Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN as "
    "LADO's secret or a project secret"
)


def test_a_new_claude_session_without_a_login_is_refused_and_leaves_nothing(
    repo, fake_tmux, claude_config, cli_logins
):
    cli_logins.logged_out()
    with pytest.raises(runtime.NotLoggedIn, match="so the session was not started"):
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert state.get_session("s") is None
    assert not [c for c in fake_tmux if c[0] == "new_session"]
    assert not list(providers.base.session_config_dirs("s"))  # or the helper the module has


def test_a_stopped_claude_session_resumes_without_a_login_and_waits(
    repo, fake_tmux, claude_config, cli_logins
):
    cli_logins.logged_in()
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    cli_logins.logged_out()
    started = runtime.start_session(str(repo), "s", None)  # lado start: resume=None
    assert started.resumed
    assert runtime.status_reasons("s") == {"supervisor": LOGIN_REASON}


def test_an_unreadable_login_refuses_no_new_session(repo, fake_tmux, claude_config, cli_logins):
    cli_logins.answer("claude", "timed out")
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert any("cannot tell whether Claude Code is logged in" in w for w in started.warnings)


def test_a_claude_worker_without_a_login_is_refused_and_leaves_nothing(
    repo, fake_tmux, claude_config, cli_logins
):
    runtime.start_session(str(repo), "s", None, provider="kilo")  # a mixed session
    cli_logins.logged_out()
    with pytest.raises(runtime.NotLoggedIn, match="so the worker was not started"):
        runtime.spawn_worker("s", "a task", name="w1", provider="claude")
    assert state.get_agent("s", "w1") is None
    assert runtime.git(str(repo), "branch", "--list", "lado/s/w1") == ""
    assert not (repo / ".lado" / "worktrees" / "s" / "w1").exists()
    runtime.spawn_worker("s", "a task", name="w2", provider="kilo")  # Kilo needs none
```

Also: `tests/test_runtime_projects.py` — a project whose secret `CLAUDE_CODE_OAUTH_TOKEN`
is set starts a Claude session and a Claude worker with `cli_logins` answering "logged in"
only when the env holds that variable (assert the env the status saw has it);
`tests/test_runtime_start_approved.py` — `start_approved_session` with the caller's
provider `claude` logged out raises `NotLoggedIn` and stores no session; a run worker
(`runs.spawn_worker`) refused leaves the run's step waiting (`_acting_agent` None).

Rework the existing tests that start a **new** session or worker without a login and
expect the wait (`test_a_claude_agent_without_a_login_waits_for_it`,
`…_in_a_fresh_home_gets_the_trust_alone`, and any `grep -n "logged_out()" tests/test_runtime*.py`
hit that starts something new): start logged in, stop, log out, resume — the wait they
check is unchanged.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_runtime.py -n0 -k "refused or resumes_without or unreadable"`
Expected: FAIL (the session starts and waits)

- [ ] **Step 3: Implement**

```python
# start_session, right after `_check_commands(env, base_env)`:
    if not old:  # a resume waits for the login instead (lado.login_wait)
        check_login(agent_cli, base_env, logins.SESSION)

# spawn_worker, right after `_check_commands(env, base_env)`:
    check_login(agent_cli, base_env, logins.WORKER)
```

Update `start_session`'s and `spawn_worker`'s docstrings with one line each; update
`logins.py`'s module docstring: a new agent of such a CLI is refused (`refusal`), a resumed
one waits.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_runtime.py tests/test_runtime_projects.py tests/test_runtime_start_approved.py tests/test_runs.py -n auto`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lado/runtime.py src/lado/logins.py tests/test_runtime*.py
git commit -m "A new session or worker of a CLI without its login is refused (LAD-161)"
```

### Task 3: `lado start <git-url>`, `--new` and the server's From scratch check first

**Files:**
- Modify: `src/lado/cli.py` (`_start_clone` before `_cloned`, `_start_new` before `scratch.make`)
- Modify: `src/lado/server/app.py` (`start`, before `scratch.make`)
- Test: `tests/test_cli.py`, `tests/test_server_launch.py`

**Interfaces:**
- Consumes: `runtime.check_start_login(provider, project)` (Task 1).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
def test_start_from_a_git_url_without_the_login_refuses_before_cloning(
    tmp_path, cli_logins, capsys, monkeypatch
):
    cli_logins.logged_out()
    cloned = []
    monkeypatch.setattr(clone, "clone", lambda *a, **k: cloned.append(a))
    target = tmp_path / "shop"
    code = cli.main(["start", "https://example.invalid/shop.git", str(target), "--provider", "claude"])
    assert code == 1 and cloned == [] and not target.exists()
    assert "so the session was not started" in capsys.readouterr().err


def test_start_new_without_the_login_makes_no_folder(tmp_path, cli_logins, capsys):
    cli_logins.logged_out()
    target = tmp_path / "fresh"
    assert cli.main(["start", "--new", str(target), "--provider", "claude"]) == 1
    assert not target.exists()
```

```python
# tests/test_server_launch.py
def test_from_scratch_without_the_login_is_400_and_makes_no_folder(client, tmp_path, cli_logins):
    cli_logins.logged_out()
    target = tmp_path / "fresh"
    answer = client.post("/api/sessions", json={
        "where": {"kind": "scratch", "path": str(target)}, "kits": ["default"], "provider": "claude"})
    assert answer.status_code == 400
    assert "so the session was not started" in answer.json()["detail"]
    assert not target.exists()


def test_a_new_session_without_the_login_is_400(client, repo, cli_logins, fake_tmux):
    cli_logins.logged_out()
    answer = client.post("/api/sessions", json={
        "where": {"kind": "folder", "path": str(repo)}, "kits": ["default"], "provider": "claude"})
    assert answer.status_code == 400 and state.get_session(repo.name) is None
```

(Match the `Launch` body and the error shape (`detail` or `Refused.message`) to the
neighbouring tests of each file; use the CLI's own entry the other `tests/test_cli.py`
tests use.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_cli.py tests/test_server_launch.py -n0 -k "login"`
Expected: FAIL (the clone runs, the folder is made)

- [ ] **Step 3: Implement**

```python
# cli._start_clone, after runtime.check_name(...):
    runtime.check_start_login(args.provider, args.project)
# cli._start_new, before scratch.make(...):
    runtime.check_start_login(args.provider, args.project)
# server/app.py start(), inside the try, before `scratch.make(...)`:
                if where.kind == "scratch":
                    runtime.check_start_login(given.provider, where.project)
                    scratch.make(path, ...)
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_cli.py tests/test_server_launch.py -n auto`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lado/cli.py src/lado/server/app.py tests/test_cli.py tests/test_server_launch.py
git commit -m "lado start refuses a clone or a new folder for a CLI without its login (LAD-161)"
```

### Task 4: `GET /api/providers` gives `login_missing`, with `?project=`

**Files:**
- Modify: `src/lado/server/models.py` (`ProviderInfo`), `src/lado/server/launch.py` (`provider_infos`, `provider_info`), `src/lado/server/app.py` (`list_providers`)
- Regenerate: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)
- Test: `tests/test_server_launch.py`

**Interfaces:**
- Produces: `ProviderInfo.login_missing: bool` (default False);
  `launch.provider_infos(project: str | None = None) -> list[ProviderInfo]`;
  `GET /api/providers?project=<id>` (404 for an unknown project).

- [ ] **Step 1: Write the failing tests**

```python
def test_providers_say_which_cli_lacks_the_login_it_needs(client, installed, cli_logins):
    cli_logins.logged_out()
    by_name = {p["name"]: p for p in client.get("/api/providers").json()}
    assert by_name["claude"]["login_missing"] is True
    assert by_name["kilo"]["login_missing"] is False


def test_providers_for_a_project_with_its_own_login(client, installed, cli_logins, lado_home):
    projects.create("shop")
    projects.set_secret("shop", "CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-test")
    cli_logins.logged_in_with("CLAUDE_CODE_OAUTH_TOKEN")  # logged in only when env has it
    assert {p["name"]: p for p in client.get("/api/providers").json()}["claude"]["login_missing"]
    shop = {p["name"]: p for p in client.get("/api/providers?project=shop").json()}
    assert shop["claude"]["login_missing"] is False
    assert client.get("/api/providers?project=nope").status_code == 404


def test_an_unreadable_login_is_not_missing(client, installed, cli_logins):
    cli_logins.answer("claude", "timed out")
    assert {p["name"]: p for p in client.get("/api/providers").json()}["claude"]["login_missing"] is False
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_server_launch.py -n0 -k "login"`
Expected: FAIL, `KeyError: 'login_missing'`

- [ ] **Step 3: Implement**

```python
# models.ProviderInfo
    login_missing: bool = False  # its agents need a login and it has none (lado.logins.refusal)

# launch.py
def provider_infos(project: str | None = None) -> list[models.ProviderInfo]:
    """Each provider of the registry, its CLI checked anew (`<cli> --version`), all at once,
    and whether it lacks the login its agents need, read in the environment of the agents
    of `project` (or of none)."""
    registry = [providers.get(name) for name in providers.names()]
    try:
        env = runtime._base_env(project) if project is None or projects.exists(project) else None
    except runtime.LadoError:
        env = None  # the login shell failed: the start says so itself
    ...
    def one(provider):
        info = provider_info(provider)
        if env is not None and info.installed and provider.capabilities.needs_login:
            info.login_missing = logins.refusal(provider, env, logins.SESSION) is not None
        return info
    with ThreadPoolExecutor(len(registry)) as pool:
        return list(pool.map(one, registry))
```

Raise `projects.NoSuchProject` for an unknown `project` and turn it into 404 in
`list_providers(project: str | None = None)`; give `runtime._base_env` a public name
(`runtime.base_env`) if the server needs it, rather than reaching for a private one. Then
`make web-types` and commit both generated files.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_server_launch.py -n auto && make web`
Expected: PASS, no stale types

- [ ] **Step 5: Commit**

```bash
git add src/lado/server tests/test_server_launch.py web/openapi.json web/src/api.gen.ts
git commit -m "The providers list says which CLI lacks the login it needs (LAD-161)"
```

### Task 5: The New session window

**Files:**
- Modify: `web/src/api.ts` (`getProviders(project?: string)`), `web/src/Launch.tsx` (the providers' ask, the options, the suggestion, `ProviderNote`, `ready`/`cloneReady`/`scratchReady`/`projectReady`, the Resume note)
- Test: `web/src/Launch.test.tsx`

**Interfaces:**
- Consumes: `ProviderInfo.login_missing`, `GET /api/providers?project=` (Task 4); `PROVIDERS_PATH` (`web/src/paths.ts`).

- [ ] **Step 1: Write the failing vitest tests**

```tsx
test("a CLI without the login it needs is greyed out, not preselected, and Start stays off", async () => {
  // providers: claude login_missing true, kilo false; folder suggests claude (last session)
  // expect option "claude · not logged in" disabled, select value "", the note
  // "Claude Code is not logged in: its agents cannot start." with link "Log in first",
  // and Start disabled
});

test("Log in first closes the window and opens Settings' providers", async () => {
  // click "Log in first" → onClose called, location is PROVIDERS_PATH
});

test("the Project way asks the providers for the chosen project", async () => {
  // getProviders called with "shop"; claude enabled there; Start on
});

test("Resume of a CLI without its login warns and goes on", async () => {
  // resuming a claude session: "⚠ Claude Code is not logged in: the supervisor waits until you log in." + "Log in…", Resume enabled
});
```

Write them in the file's own style (its fake `api` and `render` helpers); each asserts the
exact texts of Global Constraints.

- [ ] **Step 2: Run them to see them fail**

Run: `cd web && npx vitest run src/Launch.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement**

- `api.ts`: `getProviders = (project?: string) => get<ProviderInfo[]>(project ? `/api/providers?project=${encodeURIComponent(project)}` : "/api/providers")`.
- `Launch.tsx`: ask the providers with the Project way's chosen project (re-ask on its
  change; the folder, clone and scratch ways without one). Option label
  `${one.name} · not logged in` and `disabled` when `one.login_missing`. Apply the folder's
  suggestion only when its provider's `login_missing` is false, but keep a `blocked`
  provider name for the note. `const missing = !resuming && providerInfo?.login_missing`;
  every `…Ready` gains `&& !missing`. `ProviderNote` gets `missing`/`resuming` and an
  `onLogIn` that calls `onClose()` then `navigate(PROVIDERS_PATH)`: new session → `field-note
  bad` with the text and a link button "Log in first"; resume → `field-note warn` "⚠ … the
  supervisor waits until you log in." with "Log in…".

- [ ] **Step 4: Run them to see them pass**

Run: `make web`
Expected: PASS (tsc, vitest, build)

- [ ] **Step 5: Commit**

```bash
git add web/src/api.ts web/src/Launch.tsx web/src/Launch.test.tsx src/lado/server/static
git commit -m "The New session window greys out a CLI without its login (LAD-161)"
```

(Commit the static bundle only if the repository tracks it; follow what earlier UI commits did.)

### Task 6: UI e2e

**Files:**
- Test: `tests/ui/test_launch.py`

- [ ] **Step 1: Write the tests** with the fake provider `fake-login` (as `tests/ui/test_providers_section.py` uses it): no login → the option `fake-login · not logged in` disabled, the red note, its "Log in first" opens Settings → Providers and environment; with the marker file written → the option enabled and a session starts; a stopped `fake-login` session's Resume shows the amber note and resumes. Screenshot each state with the `shot` fixture.

- [ ] **Step 2: Run**

Run: `uv run pytest -m ui tests/ui/test_launch.py -k login`
Expected: PASS; screenshots in `<temp dir>/lado-ui-shots/`

- [ ] **Step 3: Commit**

```bash
git add tests/ui/test_launch.py
git commit -m "UI tests of the New session window without a login (LAD-161)"
```

### Task 7: Integration with the fake agent

**Files:**
- Modify: `tests/integration/test_provider_logins.py`

- [ ] **Step 1: Write the tests**

```python
def test_a_new_session_without_a_login_is_refused_by_lado_start(repo, marker):
    marker.unlink(missing_ok=True)
    found = subprocess.run(
        fake_provider.lado_command("start", str(repo), "--name", SESSION, "--provider", PROVIDER),
        capture_output=True, text=True, timeout=60,
    )
    assert found.returncode == 1
    assert "Fake agent is not logged in, so the session was not started" in found.stderr
    assert state.get_session(SESSION) is None and not tmux.has_session(SESSION)


def test_a_supervisor_spawning_a_worker_without_a_login_gets_the_refusal(repo, marker):
    # a session of the plain fake provider; its supervisor's `lado mcp` calls spawn_worker
    # with provider "fake-login" while the marker is gone: the tool's error names the
    # refusal, and no worktree or branch lado/<session>/<name> is left
    ...
```

Rework `test_an_agent_without_a_login_waits_then_starts_by_itself`,
`test_a_lado_secret_saved_meanwhile_reaches_the_waiting_agent` and
`test_a_login_it_cannot_read_never_holds_the_agent` to the path the wait still serves:
start logged in, `runtime.stop_session`, remove the marker, resume
(`runtime.start_session(..., resume=True)`); the rest of each test is unchanged. Use the
helper the integration suite has for calling a tool through `lado mcp` (`grep -rn "mcp" tests/integration/*.py | head`).

- [ ] **Step 2: Run**

Run: `uv run pytest -m integration tests/integration/test_provider_logins.py -n auto`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_provider_logins.py
git commit -m "Integration tests of the refused start without a login (LAD-161)"
```

### Task 8: doctor, docs, changelog

**Files:**
- Modify: `src/lado/doctor.py` (the login warning's words, D7), `tests/test_doctor.py`
- Modify: `docs/design/ui.md` (New session window: the greyed option, the note, the Resume note, `login_missing`; Providers and environment: the providers list's new field), `docs/cli.md` (`lado start` refuses; `lado doctor`'s line; a resume waits), `docs/design/agents.md` (the login at launch: refused when new, waits on resume), `docs/design/modules.md` (logins: `refusal`), `CHANGELOG.md`

- [ ] **Step 1:** doctor's line becomes `not logged in: new sessions and workers of it are refused, a resumed agent waits (Settings → Providers and environment)`; update its test.
- [ ] **Step 2:** CHANGELOG under `## 0.44.0 (unreleased)` → `### Changed`:
  `- **No Claude session or worker starts without a login.** The New session window greys Claude Code out with "Log in first"; \`lado start\` and a supervisor's new worker are refused with the reason. A resumed session still waits for the login.`
- [ ] **Step 3:** the docs as listed, true to the code.
- [ ] **Step 4: Run** `make lint && make test`, `openspec validate refuse-start-without-login --strict`, `openspec validate --specs --strict`.
- [ ] **Step 5: Commit**

```bash
git add src/lado/doctor.py tests/test_doctor.py docs CHANGELOG.md
git commit -m "The docs and the changelog say a start without a login is refused (LAD-161)"
```

## Regression run

`make lint`; `make test` (`-n auto`); `uv run pytest -m integration tests/integration/test_provider_logins.py tests/integration/test_session_start.py tests/integration/test_clone_start.py tests/integration/test_scratch_start.py -n auto`; `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_launch_project.py tests/ui/test_providers_section.py`; `make web`; `openspec validate refuse-start-without-login --strict`; `openspec validate --specs --strict`. CI runs the rest (the smoke tests: this change touches `runtime.py`, not `providers/`).

## Tests per requirement

| Requirement | Tests |
|---|---|
| A new session or worker … is refused | unit `test_logins.py`, `test_runtime.py`, `test_runtime_projects.py`, `test_runtime_start_approved.py`, `test_cli.py`; API `test_server_launch.py`; integration `test_provider_logins.py` (lado start, spawn_worker through `lado mcp`) |
| The providers list says which CLI lacks the login | API `test_server_launch.py` |
| The New session window offers only CLIs that can start | vitest `Launch.test.tsx`; UI e2e `tests/ui/test_launch.py` |
| An agent … waits for it (modified: resume) | unit `test_runtime.py` (resume waits); integration `test_provider_logins.py` (reworked to resume) |
