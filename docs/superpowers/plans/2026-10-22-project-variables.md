# Project variables Implementation Plan

**Goal:** The human sets and removes a project's plain variables (CLI, API), and every
agent of a session in that project gets them, over the outside folder's and under
LADO's, with the kits' checks seeing them.

**Architecture:** A table `project_variables` (schema 34) with set/unset in
`lado.projects` behind one name rule; `agent_env.resolve(project=…)` lays the project's
layer over the outside folder's and `runtime._base_env(project)` reads it for the
session's project at every launch, so the kits' `${NAME}` check, `expects`, the
provider's checks and `mcp_exec` see it unchanged. The CLI gets `lado project set|unset`
and the variables in `show`; the server two endpoints and a field; `lado doctor` an
override line; the smoke a probe MCP server.

**Tech Stack:** Python 3.10+ (standard library), SQLite, FastAPI/pydantic, pytest (unit,
server, integration with the fake agent, smoke with the real CLIs).

**Spec:** `openspec/changes/project-variables/` (proposal with AC-1..AC-14, `design.md`
D1-D13, delta specs `projects` and `agent-variables`) and
`docs/superpowers/specs/2026-10-22-project-variables-design.md` (the human's view and the
manual check).

## Global Constraints

- Python 3.10+, standard library only; no new dependency.
- Texts, verbatim (the spec's):
  - `Set <NAME> in project <id>.`; `Removed <NAME> from project <id>.`; `Agents started
    from now on get it.`; `Agents started from now on get it; running sessions of <id>
    keep the old environment until restarted: <names>`;
  - `the name <NAME> is not a variable name: Latin letters, digits and _, not starting
    with a digit`; `<NAME> is reserved: LADO or the agent CLIs set it`; `<NAME> looks like
    a secret (<word>): a plain variable takes no name with TOKEN, KEY, SECRET or
    PASSWORD; secrets come with lado project set <id> <NAME> --secret (not built yet)`;
    `the value of <NAME> is larger than 64 KiB`; `the value of <NAME> is not UTF-8 text`;
    `project <id> has no variable <NAME>; its variables: <names>`;
  - `  variables:` / `    <NAME>  <value>` / `  variables: none`;
  - `project variable <name> of <id> not used: LADO sets <name> for <provider>`;
  - `[info] Project variables: <id> overrides <NAMES> of LADO_ENV_DIR`.
- `mcp_server.py`, `hooks.py`, the files of one provider and `kits.py` do not change (the
  brief's threshold: if they must, stop and ask the human through the supervisor).
- A schema change: `SCHEMA_VERSION` 34, `MIGRATIONS[33]`, `tests/agent_helpers.schema_before`.
- Never the user's real home in tests: `HOME`, `LADO_HOME`, `LADO_REPOS` into `tmp_path`;
  tests set no fixed path, port or socket.
- No value of a project variable in `loop.log`, `hooks.log`, `errors.jsonl`, `lado log`,
  the bug report or telemetry (they are plain, but nothing needs them there).

## Review Focus

- A worker spawned by a supervisor's `lado mcp` (not by the test process) gets the
  project's current value: the read is from `lado.db` in that process (Task 3, integration).
- A resume of a stopped session reads the variables anew (Task 3).
- A session `start_session` starts from a session in a project gets that project's
  values, and a session without a project none, also when another project with the same
  name runs at the same time (Task 6).
- A value with a line break, `=`, spaces or unicode passes through `env.json` and
  `mcp_exec` unchanged (Tasks 3, 6).
- `lado project delete --yes` leaves no row: a project made again with the same id has
  none (Task 1).

## Task 1: The store and the migration (D1)

**Files:** Modify `src/lado/state.py`; `tests/agent_helpers.py`. Test:
`tests/test_state_projects.py` (or the file that tests `state`'s projects today),
`tests/test_migrations.py` (the file that runs `previous_schema`).

**Produces:** `state.project_variables(id) -> dict[str, str]`,
`state.set_project_variable(id, name, value) -> None`,
`state.unset_project_variable(id, name) -> bool`, `state.PROJECT_VARIABLES_TABLE`.

- [ ] Tests: set, set again (replaced), read by name, unset (True, then False), two
  projects with one name keep their own values, `delete_project` removes the rows (and a
  project made again with the id has none); migration from `previous_schema` keeps
  `projects` and `sessions.project` and adds the table.
- [ ] Implement D1; `schema_before` asserts `MIGRATIONS[33] == [state.PROJECT_VARIABLES_TABLE]`
  and drops the table.
- [ ] `uv run pytest -n0 <those files>`; commit `A project keeps plain variables in lado.db (LAD-130)`.

## Task 2: The name rule and set/unset in the core (D2, D3, D6)

**Files:** Modify `src/lado/projects.py`, `src/lado/providers/base.py`. Test:
`tests/test_project_variables.py` (new), `tests/test_providers.py` (or the providers'
launch tests).

**Consumes:** Task 1. **Produces:** `projects.check_variable(id, name, value: str |
None) -> None`, `projects.set_variable(id, name, value) -> list[str]`,
`projects.unset_variable(id, name) -> list[str]`, `projects.running(id) -> list[str]`,
`projects.NoSuchVariable(ProjectError)`, `projects.SECRET_WORDS`,
`projects.RESERVED_NAMES`, `providers.base.CLI_VARIABLES`.

- [ ] Tests (each requirement of the `projects` delta about names and values):
  `A-B`, `1X`, `` → not a variable name; `PATH`, `HOME`, `TERM`, `LADO_HOME`,
  `LADO_ANYTHING`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_CONFIG_CONTENT`,
  `KILO_NO_DAEMON` → reserved; `GH_TOKEN` (TOKEN), `yougile_api_key` (KEY),
  `DB_PASSWORD` (PASSWORD), `MY_SECRET` (SECRET), `MONKEY_MODE` (KEY) → secret with the
  word; `BOARD_URL`, `ANTHROPIC_BASE_URL`, `_X` → accepted; value of 65 537 bytes → too
  large; `"a\0b"` and `"\udcff"` → not UTF-8 text; `""` accepted; unknown project →
  `NoSuchProject`; `unset` of a missing name → `NoSuchVariable` listing the others or
  `none`; `running` lists only sessions not stopped, of this project only.
- [ ] Test: for each provider, its `launch_command(...)` `Launch.env` keys are in
  `projects.RESERVED_NAMES` (build the launches as the providers' tests do).
- [ ] Implement D2, D3, D6.
- [ ] `uv run pytest -n0 tests/test_project_variables.py …`; commit `A project variable's
  name is checked by one rule (LAD-130)`.

## Task 3: The project's layer at every launch (D4, D5)

**Files:** Modify `src/lado/agent_env.py`, `src/lado/runtime.py`. Test:
`tests/test_agent_env.py`, `tests/test_runtime*.py` (the files testing `_base_env`,
`_outside_warnings`, `start_session`, `spawn_worker` with the tmux recorder).

**Consumes:** Task 1, 2. **Produces:** `agent_env.resolve(project: Mapping[str, str] |
None = None)`, `runtime._base_env(project: str | None)`,
`runtime._layer_warnings(agent, launch, project, *, files)`.

- [ ] Unit tests: `resolve` order shell → outside → project (all three set one name);
  `resolve()` without a project as before; `start_session` of a project passes the
  project's variables into `env.json` (read the file the recorder's command names) and a
  session without a project does not; a resume reads them anew; `spawn_worker` of a
  session in a project gets them; a kit MCP server with `${BOARD_URL}` passes `_spec`
  when `BOARD_URL` is only in the project and fails (`environment variable BOARD_URL is
  not set`) without; a row with a provider's name (inserted with `state.set_project_variable`
  directly) keeps the provider's value and gives the warning line.
- [ ] Implement D4 and D5.
- [ ] `uv run pytest -n0 <files>`; commit `Agents of a session in a project get its
  variables (LAD-130)`.

## Task 4: The CLI (D7)

**Files:** Modify `src/lado/cli.py`. Test: `tests/test_cli.py` (or the project CLI
tests).

**Consumes:** Task 2.

- [ ] Tests: `set` prints the two lines with and without a running session; `set` again;
  `unset` and its missing-name refusal; each refusal of Task 2 exits 1 with `lado: …`;
  from an agent (`LADO_AGENT`) `set` and `unset` exit 1 with the human-only text and
  change nothing, `show` works; `show` lists variables padded, a value with `\n` shown as
  `\n`, `  variables: none`; unknown project for `set`, `unset`, `show`; `set shop X --
  -v` stores `-v`.
- [ ] Implement D7.
- [ ] Commit `lado project set and unset (LAD-130)`.

## Task 5: The server's API (D8)

**Files:** Modify `src/lado/server/app.py`, `models.py`, `launch.py`;
`web/openapi.json`, `web/src/api.gen.ts` (`make web-types`). Test:
`tests/test_server_projects.py`.

**Consumes:** Task 2.

- [ ] Tests: `GET /api/projects/shop` has `variables` by name; `PUT
  …/variables/BOARD_URL` sets it and answers `{project, running}` (a running session
  named); `DELETE` removes it; 404 for an unknown project (both) and an unknown variable
  (`DELETE`); 400 with the text for `GH_TOKEN`, `PATH`, `A-B`, a value too large; without
  the change token refused as the other `guard.changes` endpoints.
- [ ] Implement D8; `make web-types`; `make web`.
- [ ] Commit `The server sets and removes a project's variables (LAD-130)`.

## Task 6: End to end with the fake agent

**Files:** Create `tests/integration/test_project_variables.py`.

**Consumes:** Tasks 1-5.

- [ ] Two projects `shop` and `acme`, each with a repository (`projects.add_new`), one
  name `BOARD_URL` with `https://a` / `https://b` (a value with a space and `=` in
  `shop`); `LADO_ENV_DIR` folder with `BOARD_URL=out` and `OTHER=o`; a session in each:
  the supervisor's environment (the fake agent writes its env, as
  `test_outside_variables.py` reads it), a worker spawned by the supervisor through its
  MCP tool, a flow run's worker, and the supervisor of the session `start_session` starts
  have the project's value; a session without a project has `out`.
- [ ] `unset` in `shop`, then a worker spawned from the test process has no project's
  `BOARD_URL` (it has `out`), the supervisor keeps `https://a` (D12).
- [ ] A kit with an MCP server `env: {URL: ${BOARD_URL}}` (no outside folder): starts in
  `shop`, and the server's process (a fake server that writes its env) has `URL=https://a`;
  a session without a project is refused naming `BOARD_URL`.
- [ ] A row with a provider's name gives the warning at the start (fake provider's
  launch variable).
- [ ] `uv run pytest -m integration -n auto tests/integration/test_project_variables.py`;
  commit `End-to-end tests of project variables (LAD-130)`.

## Task 7: lado doctor (D9)

**Files:** Modify `src/lado/doctor.py`. Test: `tests/test_doctor.py`.

- [ ] Tests: an overlap prints `[info] Project variables: shop overrides BOARD_URL of
  LADO_ENV_DIR`; two projects joined by `; `; no overlap, no `LADO_ENV_DIR`, no
  `lado.db` → no line; no value in the output; the bug report (`doctor.report`) has no
  project variable's name or value.
- [ ] Implement D9; commit `lado doctor names project variables over the outside folder
  (LAD-130)`.

## Task 8: The smoke probe (D10)

**Files:** Create `tests/smoke/probe_kit/` (its `kit.yaml`, `probe.py`); modify
`tests/smoke/test_smoke.py` (a new test) and, if needed, `tests/smoke/conftest.py`.

- [ ] A test per provider (the existing `smoke_provider` fixture): a project with
  `SMOKE_PROBE_VALUE` only in it, a repository with `projects.add_new`, a session in it
  with the probe kit; wait (as the smoke waits for `mcp_ready`) for the probe's file;
  assert `template` and `inherited` are the project's value.
- [ ] The smoke cannot run locally without the CLIs: say "written, CI runs it" in the
  build report; CI's smoke cells on the pull request must be green. A provider whose CLI
  does not start the kit's server without a model: stop and ask the human through the
  supervisor (the brief's threshold), with the CI log.
- [ ] Commit `The smoke proves project variables reach a kit's MCP server (LAD-130)`.

## Task 9: Documents and version (D13)

- [ ] `docs/cli.md`, `docs/design/projects.md`, `docs/design/agents.md`,
  `docs/design/modules.md`, `docs/install.md`; CHANGELOG one line under `## 0.43.0
  (unreleased)`, Added. `uv run pytest tests/test_agents_md.py`.
- [ ] Commit `Docs of project variables (LAD-130)`.

## Task 10: Regression

- [ ] `make lint`; `make test` (counts in the build report); `uv run pytest -m
  integration -n auto tests/integration/test_project_variables.py
  tests/integration/test_outside_variables.py tests/integration/test_project_sessions.py
  tests/integration/test_project_repositories.py tests/integration/test_agent_kits.py`;
  `make web`; `openspec validate project-variables --strict`; `openspec validate --specs
  --strict`; the trial archive in a copy of `openspec/` in the scratchpad (`openspec
  archive project-variables -y`, then `openspec validate --specs --strict` there); CI
  green with the container and smoke cells.
