# Providers section and agent start screens Implementation Plan

**Goal:** Settings → Providers and environment answers at once and shows only what the
user can fix; no Claude Code screen holds an agent unseen before its first hook; LADO's
own writes into Claude Code's config go to loop.log only; a resume by hand is refused
without the login the supervisor's CLI needs.

**Architecture:** A server-side cache of the CLIs' rows refreshed by one background check
(`lado/server/provider_check.py`), read by a polling section with a ↻; two keys in Claude
agents' own `--settings` file; a neutral check in the session loop for agents that never
hook; `Blocker.notes` logged by the core and returned to no one; `start_session` refuses a
resume unless LADO itself resumes (`wait_for_login`, `AT_START`).

**Tech Stack:** Python 3.10+ (stdlib, FastAPI, pydantic), pytest with the fake tmux and
the fake agent, React + TypeScript (vitest), Playwright (pytest -m ui), the real Claude
Code for the smoke test.

**Spec:** `openspec/changes/providers-section-and-start-screens/` (proposal, deltas of
`provider-logins`, `claude-folder-trust`, `agent-start-screens`, design.md D1-D11) and
`docs/superpowers/specs/2026-10-31-providers-section-and-start-screens-design.md`. Mockup:
run artifact `mockup-providers.html`.

## Global Constraints

- Subtitle: `Sign-ins your agents use. Changes apply to agents started afterwards.`
- ↻ button: text `↻`, `aria-label="Check the CLIs again"`, `title="Checking the CLIs…"` while a check runs.
- Row texts: `not installed` + install hint; `LADO is tested with <tested_version>`; `Couldn't check the sign-in` + the problem; not-ready row `checking…`.
- Over the list: `No agent CLI is installed: install one of them to start a session.`
- Under the rows: `⚠ Agents' environment could not be read from your login shell: <why>. `lado doctor` shows more.`
- Safety net: `START_SILENCE = 30.0`; reason `Waiting for an answer in its terminal: no sign from it 30 s after its start. Open its terminal.`
- Resume refusal: `<title> is not logged in, so the session was not resumed: log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set <first login variable> as LADO's secret or a project secret`
- Claude settings keys: `enableAllProjectMcpServers: true` always; `skipDangerousModePermissionPrompt: true` only for `bypassPermissions`.
- No provider name above `providers/`; no schema change; no write to `.claude.json` for the two screens.
- CHANGELOG.md: lines under `## 0.44.0 (unreleased)` (Changed, Fixed).
- Unit suites with `-n auto`; integration and UI files with their markers; single node ids with `-n0`.

## Review Focus

- A check that raises in one provider (a broken CLI): the others' rows still arrive and `checking` ends (Task 5 test `test_a_failing_provider_does_not_stop_the_check`).
- The section unmounted while polling: no timer left, no state set after unmount (Task 6 vitest `stops polling when it leaves`).
- An agent blocked at its start by a known blocker (trust refused, rejected key) or waiting for its login is never touched by the safety net (Task 3 test `test_a_blocked_or_login_waiting_agent_is_left_alone`).
- A resume with `--provider kilo` of a Claude session without a login goes on (Task 4 test `test_a_resume_with_another_provider_goes_on`).
- Two quick ↻ presses start one check (Task 5 test `test_start_twice_runs_one_check`).

---

### Task 1: Notes to the session's log only (D8)

**Files:**
- Modify: `src/lado/runtime.py` (`_first_hook_blocker`, `_before_window`'s early blocker)
- Modify: `src/lado/login_wait.py` (`main`: notes logged, not printed)
- Modify: `src/lado/providers/base.py` (`Blocker.notes` docstring)
- Test: `tests/test_runtime.py`, `tests/test_login_wait.py`, `tests/test_cli.py`, `tests/integration/test_session_start.py`

**Interfaces:** Produces `runtime._first_hook_blocker(...) -> list[str]` returning only the
reason and the warning; notes go to `loop.log(session, f"{agent}: {note}")`.

- [ ] **Step 1: Failing tests.** In `tests/test_runtime.py` rework the tests that expect the
  trust's line in `started.warnings` (grep `recorded Claude Code`): assert
  `started.warnings` holds no `LADO recorded` line and `loop` log holds
  `supervisor: LADO recorded Claude Code's trust in …` once; the same for `spawn_worker`'s
  warnings (`w1: …`). Keep the tests where the config cannot be read: the warning is still
  in `started.warnings`. In `tests/test_login_wait.py` assert that the first-run note is
  not in the captured stdout and is in loop.log. In `tests/test_cli.py` assert `lado start`'s
  stderr has no `LADO recorded`.
- [ ] **Step 2:** `uv run pytest -n0 tests/test_runtime.py -k "trust or first_run or key" -x` → FAIL.
- [ ] **Step 3: Implement.**

```python
def _first_hook_blocker(agent_cli, agent, base_env, launch) -> list[str]:
    blocker = agent_cli.first_hook_blocker(agent.cwd, _launch_env(agent, base_env, launch))
    _log_notes(agent, blocker.notes)
    if blocker.reason:
        state.block(agent.session, agent.name, blocker.reason)
    return [line for line in (blocker.reason, blocker.warning) if line]


def _log_notes(agent: state.Agent, notes: Iterable[str]) -> None:
    """What LADO wrote into the CLI's config: the session's log only (LAD-163)."""
    for note in notes:
        loop.log(agent.session, f"{agent.name}: {note}")
```

  In `_before_window`'s waiting branch: `_log_notes(agent, early.notes)` and
  `lines += [early.warning] if early.warning else []`. In `login_wait.main`: log each note,
  print and log only the reason and the warning.
- [ ] **Step 4:** the same tests → PASS; `uv run pytest -m integration -n0 tests/integration/test_session_start.py` → PASS.
- [ ] **Step 5: Commit** `LADO's writes into Claude Code's config go to the session's log only (LAD-163)`.

### Task 2: Claude's bypass and MCP screens by the agent's own settings (D6)

**Files:**
- Modify: `src/lado/providers/claude.py` (the settings file in `launch`)
- Modify: `tests/smoke/conftest.py:86`, `tests/smoke/test_smoke.py:229` (no `bypassPermissionsModeAccepted` pre-seed)
- Modify: `docs/install.md:256-262`
- Test: `tests/test_providers.py`, `tests/smoke/test_smoke.py`

- [ ] **Step 1: Failing tests** in `tests/test_providers.py`:

```python
@pytest.mark.parametrize("mode", ["bypassPermissions", "default", "auto", "plan", None])
def test_claude_settings_skip_the_bypass_warning_only_in_bypass(tmp_path, mode):
    settings = _claude_settings(tmp_path, permission_mode=mode)  # launch, then read settings.json
    assert settings["enableAllProjectMcpServers"] is True
    assert ("skipDangerousModePermissionPrompt" in settings) == (mode == "bypassPermissions")
```

- [ ] **Step 2:** `uv run pytest -n0 tests/test_providers.py -k bypass` → FAIL.
- [ ] **Step 3: Implement.**

```python
        config = {
            "hooks": {e: hook(e) for e in EVENTS},
            "permissions": {"deny": BUILT_IN_MESSAGING + (EDIT_TOOLS if spec.read_only else [])},
            # Claude Code's screens before the first hook that LADO's own settings answer,
            # with no write to a shared file (checked by hand with 2.1.295): a repository's
            # .mcp.json servers ("New MCP server found"), and bypass mode's warning.
            "enableAllProjectMcpServers": True,
        }
        if session.permission_mode == BYPASS:
            config["skipDangerousModePermissionPrompt"] = True
```

  (`BYPASS = "bypassPermissions"` next to the modes list.)
- [ ] **Step 4:** unit → PASS. Smoke (CI runs it; locally only with the CLIs): in
  `tests/smoke/conftest.py` write `{"hasCompletedOnboarding": true}` only; add
  `test_a_claude_session_with_a_repo_mcp_json_starts_with_no_screen` (a `.mcp.json` with a
  stdio server `true`, `--permission-mode bypassPermissions`, the supervisor reaches its
  first hook, `git status --porcelain` empty). `tests/container/container_helpers.py:219`
  keeps its pre-seed (the image's own test, not about this screen).
- [ ] **Step 5:** docs/install.md: LADO enables a repository's `.mcp.json` servers for its
  Claude agents. **Commit** `Claude agents skip the bypass warning and take the repository's MCP servers by their own settings (LAD-163)`.

### Task 3: The safety net for an agent with no hook (D7)

**Files:**
- Modify: `src/lado/runtime.py` (`START_SILENCE`, `START_SILENCE_REASON`, `check_starts`)
- Modify: `src/lado/loop.py` (the pass calls it after `check_windows`)
- Modify: `src/lado/login_wait.py` (`state.window_opened(session, agent)` before `os.execvpe`)
- Test: `tests/test_liveness.py`, `tests/test_login_wait.py`, `tests/integration/test_session_loop.py`

**Interfaces:** Produces `runtime.check_starts(session: str, now: datetime | None = None) -> None`.

- [ ] **Step 1: Failing tests** in `tests/test_liveness.py` (pattern of the `check_windows` tests at :402):
  - `test_an_agent_with_no_hook_30_s_after_its_window_waits_for_its_terminal`: a `starting`
    agent, `window_at` 31 s ago, `seen_at == 0` → `status_reasons()[name] == START_SILENCE_REASON`, status `waiting`.
  - `test_an_agent_under_30_s_is_left_alone` (29 s).
  - `test_an_agent_that_hooked_is_left_alone` (`state.seen` called, then 31 s).
  - `test_a_blocked_or_login_waiting_agent_is_left_alone` (status `waiting` with a reason).
  - `test_its_first_hook_makes_it_ready`: block by the net, then a SessionStart hook → `idle`, no reason.
  - In `tests/test_login_wait.py`: the window marks `window_at` anew before exec.
- [ ] **Step 2:** `uv run pytest -n0 tests/test_liveness.py -k "30_s or hooked or left_alone or first_hook"` → FAIL.
- [ ] **Step 3: Implement.**

```python
START_SILENCE = 30.0  # seconds from an agent's launch to its first hook before it is shown
START_SILENCE_REASON = (
    "Waiting for an answer in its terminal: no sign from it 30 s after its start. "
    "Open its terminal."
)


def check_starts(session: str, now: datetime | None = None) -> None:
    """One look of the session loop for agents whose CLI holds them before any hook with
    a question LADO does not know: `starting`, no hook since the launch (seen_at 0), the
    window opened (or the login's wait ended) START_SILENCE ago. Their first hook makes
    them ready (hooks: SessionStart of a held agent; any status after the BLOCKED event)."""
    now = now or datetime.now(timezone.utc)
    for agent in state.list_agents(session):
        if agent.status != state.STARTING or agent.seen_at or agent.window_at is None:
            continue
        if (now - _utc(agent.window_at)).total_seconds() >= START_SILENCE:
            state.block(session, agent.name, START_SILENCE_REASON)
```

  In `loop.run`'s pass: `runtime.check_starts(session)` after `check_windows`. In
  `login_wait.main`, before `os.execvpe`: `state.window_opened(session, agent)`.
- [ ] **Step 4:** unit → PASS. Integration in `tests/integration/test_session_loop.py`
  with `LADO_LOOP_INTERVAL` small and a fake agent that never hooks (the fake agent's
  silent mode; add one if missing) and a patched `START_SILENCE` (env or monkeypatch in the
  loop's process: add `LADO_START_SILENCE` only if the loop cannot be patched otherwise;
  prefer the fake agent sleeping past a short value read from the module): `lado ls` shows
  the reason; then the fake agent fires SessionStart and the agent is `idle`.
- [ ] **Step 5: Commit** `An agent with no hook 30 s after its start waits for an answer in its terminal (LAD-163)`.

### Task 4: A resume by hand is refused without the login (D9)

**Files:**
- Modify: `src/lado/logins.py` (`RESUME`, its text in `refusal`)
- Modify: `src/lado/runtime.py` (`start_session(..., wait_for_login: bool = False)`; the check for `old`)
- Modify: `src/lado/cli.py` (`lado start --wait-for-login`, `help=argparse.SUPPRESS`)
- Modify: `src/lado/self_update.py:609` (adds `--wait-for-login`)
- Test: `tests/test_logins.py`, `tests/test_runtime.py`, `tests/test_cli.py`, `tests/test_self_update.py`, `tests/test_server_launch.py`, `tests/integration/test_provider_logins.py`

- [ ] **Step 1: Failing tests.**
  - `tests/test_logins.py`: `refusal(claude, env, RESUME)` gives the resume text.
  - `tests/test_runtime.py`: rework `test_a_stopped_claude_session_resumes_without_a_login_and_waits`
    (:1618) into `test_a_stopped_claude_session_is_not_resumed_by_hand_without_a_login`
    (raises `NotLoggedIn` with the text; `state.get_session("s").stopped_at` still set; no
    `new_session` call), plus `test_a_resume_at_start_waits_for_the_login`
    (`reason=AT_START`), `test_a_resume_with_wait_for_login_waits`,
    `test_a_resume_with_another_provider_goes_on` (`provider="kilo"`).
  - `tests/test_cli.py`: `lado start <repo> --name s` of a stopped session without the login
    exits 1 with the text; `--wait-for-login` resumes; `lado start --help` does not list it.
  - `tests/test_self_update.py`: `_resume` runs `start <repo> --name <n> --no-attach --wait-for-login`.
  - `tests/test_server_launch.py:946`: rework into 400 for `POST /api/sessions/{name}/resume`.
- [ ] **Step 2:** `uv run pytest -n0 tests/test_runtime.py -k resume -x` → FAIL.
- [ ] **Step 3: Implement.**

```python
    if not old or not (wait_for_login or reason == AT_START):
        check_login(agent_cli, base_env, logins.SESSION if not old else logins.RESUME)
```

  at the place of today's `if not old:` check (runtime.py:748), before
  `state.resume_session`. `cmd_start` passes `wait_for_login=args.wait_for_login`.
- [ ] **Step 4:** unit and API → PASS; `uv run pytest -m integration -n0 tests/integration/test_provider_logins.py`
  with the LAD-157 wait tests (:114, :228) moved to `--wait-for-login` and a new one: `lado
  start` of a stopped session refused, the session still stopped.
- [ ] **Step 5: Commit** `A resume by hand is refused while the supervisor's CLI has no login (LAD-163)`.

### Task 5: The CLIs' check in the server (D1, D2, D5)

**Files:**
- Create: `src/lado/server/provider_check.py`
- Modify: `src/lado/server/launch.py` (drop `providers_page`; `provider_logins` gives `waiting` only when the status is not yes; `provider_login` puts its row)
- Modify: `src/lado/server/models.py` (`ProvidersPage.checking`, `.environment`, no `checks`; `ProviderLogins.ready`; `CheckInfo` removed if unused)
- Modify: `src/lado/server/app.py` (`POST /api/providers/check`; the actions start a check)
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)
- Test: `tests/test_server_providers.py`, new `tests/test_provider_check.py`

**Interfaces:** Produces `provider_check.start() -> bool`, `provider_check.snapshot() ->
models.ProvidersPage`, `provider_check.put(row: models.ProviderLogins) -> None`,
`provider_check.reset()` (tests); API `POST /api/providers/check -> ProvidersPage`.

- [ ] **Step 1: Failing tests** in `tests/test_provider_check.py` with providers' reads
  replaced by functions that wait on `threading.Event`s:
  - `test_the_first_snapshot_has_every_provider_not_ready_and_checking`
  - `test_a_row_is_kept_as_soon_as_its_cli_is_read` (release one event, poll `snapshot()`: that row ready, others not)
  - `test_the_login_shell_runs_once_per_check` (count `_environment` calls)
  - `test_start_twice_runs_one_check`
  - `test_a_failing_provider_does_not_stop_the_check` (one read raises → its row's login `unknown` with the error; `checking` false at the end)
  - `test_the_last_rows_stay_while_a_new_check_runs`
  In `tests/test_server_providers.py`: `GET` starts nothing; `POST …/check` answers
  `checking: true`; `PUT …/variables/…` answers the row and starts a check; `waiting` is
  empty for a logged-in row with a waiting agent (D5).
- [ ] **Step 2:** `uv run pytest -n0 tests/test_provider_check.py -x` → FAIL.
- [ ] **Step 3: Implement** `provider_check.py`:

```python
"""Settings → Providers and environment's data (docs/design/ui.md): the last row of each
agent CLI, kept for the server's lifetime and refreshed by one background check at a time,
all CLIs at once and the login shell once; a row is kept as soon as its CLI is read."""

_lock = threading.Lock()
_rows: dict[str, models.ProviderLogins] = {}
_environment = ""
_running = False


def start() -> bool:
    global _running
    with _lock:
        if _running:
            return False
        _running = True
    threading.Thread(target=_check, name="provider-check", daemon=True).start()
    return True


def _check() -> None:
    global _running, _environment
    try:
        registry = [providers.get(name) for name in providers.names()]
        with ThreadPoolExecutor(len(registry) + 1) as pool:
            env = pool.submit(launch._environment)
            list(pool.map(lambda p: _one(p, env), registry))
            _environment = env.result()[1]
    finally:
        with _lock:
            _running = False


def _one(provider, env) -> None:
    try:
        status = doctor.provider_status(provider, shutil.which)
        layers, problem = env.result()
        row = launch.provider_logins(launch._read(provider, status, layers, problem),
                                     launch.provider_info(provider, status))
    except Exception as error:  # one broken CLI never stops the others
        telemetry.record(error)  # or the server's log, as the other background threads do
        row = launch.failed_row(provider, str(error))
    put(row)
```

  `snapshot()` gives a not-ready row (`ready=False`, `cli` with name and title, empty
  rest) for a provider never read. Routes: `GET /api/providers/logins` →
  `provider_check.snapshot()`; `POST /api/providers/check` → `start()` then `snapshot()`;
  each action → `row = launch.provider_login(name); provider_check.put(row);
  provider_check.start(); return row`.
- [ ] **Step 4:** tests → PASS; `make web-types`; `make web` (stale-types check).
- [ ] **Step 5: Commit** `The providers section answers at once from the server's last check (LAD-163)`.

### Task 6: The section's and the Resume window's UI (D3, D4, D9)

**Files:**
- Modify: `web/src/Providers.tsx`, `web/src/api.ts` (`checkProviders()` = `POST /api/providers/check`), `web/src/Launch.tsx` (no resume exceptions), `web/src/styles.css` (`.pv-title`, `.pv-refresh`, `.pv-tested`, `.pv-off`, `.pv-none`, `.pv-env`, `.pv-checking`; drop `.pv-doctor`, `.pv-mark`, `.pv-level-*`, `.pv-again`), `web/src/fakes.ts`
- Test: `web/src/Providers.test.tsx`, `web/src/Launch.test.tsx:770`, `tests/ui/test_providers_section.py`, `tests/ui/test_launch.py:571`

- [ ] **Step 1: Failing vitest** in `Providers.test.tsx`: the subtitle; no "lado doctor",
  no "Check again", no `[ok]`; ↻ named "Check the CLIs again" posts a check; rows of the
  first answer show at once with ↻ turning; polling every second while `checking`, stops
  after; `stops polling when it leaves` (fake timers, unmount, no further fetch); a
  not-ready row shows "checking…"; not installed greyed with the hint; "LADO is tested with
  7.8.x"; "Couldn't check the sign-in" + problem; the no-CLI line; the environment line only
  with `environment`. In `Launch.test.tsx` rework :770: Resume of a CLI without its login →
  option disabled, red note "Log in first", Resume disabled; choosing kilo enables it.
- [ ] **Step 2:** `cd web && npx vitest run src/Providers.test.tsx src/Launch.test.tsx` → FAIL.
- [ ] **Step 3: Implement** to the mockup (`mockup-providers.html`, screens 1-4): the
  heading row with ↻ (`term-spin` while `checking`, none under `prefers-reduced-motion`),
  `useEffect` that posts the check on mount and polls with a counter so the latest answer
  wins; `LoginSheet`'s `onClose` posts a check. `Launch.tsx`: drop `resuming` from the
  option's `disabled`, from `canStart`/`held`, and `ProviderNote`'s amber branch.
- [ ] **Step 4:** vitest → PASS; `make web`. UI e2e:
  - `tests/ui/test_providers_section.py`: the Save test also asserts that the row never
    shows the "waits for this login" line once "Logged in" shows (poll the row's text for
    3 s); a new test `test_the_section_shows_the_last_rows_at_once` (open, leave, open:
    rows visible before the check ends, ↻ turning); screenshots of the section in
    `<temp>/lado-ui-shots/`.
  - `tests/ui/test_launch.py:571`: rework into `test_resume_without_the_login_is_disabled`
    with "Log in first" leading to Settings; a screenshot.
  - A session start with the trust recorded shows no "Warnings:" box (in
    `tests/ui/test_session_head.py` or the launch test that starts a Claude fake).
  Run `uv run pytest -m ui -n0 tests/ui/test_providers_section.py tests/ui/test_launch.py`.
- [ ] **Step 5: Commit** `The providers section shows only what the user can fix, with a ↻ (LAD-163)`.

### Task 7: Docs and the regression run (D11)

**Files:** `docs/design/ui.md` (Providers and environment :2292-2343; the Resume window
:1401-1414), `docs/cli.md` (:244, :254-265, :345-373: the resume refused by hand; the
update's resume waits), `docs/design/agents.md` (start screens, the safety net, notes),
`docs/design/modules.md` (`server/provider_check.py`), `AGENTS.md` (the `server/` line
names `provider_check.py`), `BACKLOG.md` (remove the entry at :425-437 and the bypass item
at :650-669), `CHANGELOG.md` (`## 0.44.0 (unreleased)`: Changed — the section, the resume;
Fixed — the bypass and MCP screens, the warnings box, the glitch).

- [ ] **Step 1:** write the docs; `uv run pytest -n0 tests/test_agents_md.py`.
- [ ] **Step 2: Regression run** (each to its own log, exit status read first):
  `make lint`; `make test`; `uv run pytest -m integration -n auto
  tests/integration/test_session_start.py tests/integration/test_session_loop.py
  tests/integration/test_provider_logins.py`; `uv run pytest -m ui -n auto
  tests/ui/test_providers_section.py tests/ui/test_launch.py tests/ui/test_session_head.py`;
  `make web`; `openspec validate providers-section-and-start-screens --strict`;
  `openspec validate --specs --strict`. The smoke runs in CI (the change touches
  `src/`).
- [ ] **Step 3: Commit** `Docs for the providers section, the start screens and the resume (LAD-163)`.
