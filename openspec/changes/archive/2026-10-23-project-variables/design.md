## Context

S2 (`projects-in-core`) made a project a record in `lado.db` (`projects`, schema 32); S3
(`sessions-in-projects`) gave a session its project (`sessions.project`, schema 33) and
made a session started with `start_session` inherit it; S4 (`project-repositories`) added
and removed repositories. An agent's environment is built today in two places:
`agent_env.resolve()` (the login shell's, or the starting process's with
`LADO_AGENT_ENV=inherit`, then the outside folder `LADO_ENV_DIR`, read anew at each
launch) and `runtime._launch_env` (that base, then `providers.agent_env(agent)`, LADO's
variables, then the provider's `Launch.env`). `runtime._base_env()` is called once per
launch in `start_session` (a start and a resume) and `spawn_worker` (a worker, a flow
run's worker through `runs.spawn_worker`); its result also feeds the kits' checks:
`_check_commands` (`expects` commands on `PATH`) and `_spec` →
`ResolvedAgent.mcp_servers(base_env)`, which refuses an MCP server whose `${NAME}` the
base lacks and otherwise wraps it in `lado.mcp_exec`, which fills the values from the
agent's own environment when the CLI starts the server. `runtime._outside_warnings` names
a file of the outside folder whose name LADO or the provider sets for that launch.

A supervisor's `spawn_worker` and `start_session` run in its `lado mcp` process, which
has `LADO_HOME` and reads the same `lado.db`; the project's variables are read there from
the database, not passed through the environment.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the
epic's plan (S5a) and the brief of gate #79. The human's answers of this step: question
#966.

## Goals / Non-Goals

Goals: plain variables stored per project, set and removed by the human (CLI, API); one
name rule; the project's layer in every agent of a session in a project; the kits' checks
seeing it; `lado doctor`'s override line; the smoke proving it per provider.

Non-goals: secrets (S5b), the UI (S6), global or session variables, outside secrets per
project, giving a value to an agent that runs.

## Options

Where the project's layer goes:
1. **`agent_env.resolve(project=…)` lays the project's variables over the outside
   folder's; `runtime._base_env(project)` reads them from `lado.db` for the session's
   project** (chosen). One function builds the base for every provider, and everything
   that already reads the base (the kits' `${NAME}` check, `expects`, the provider's
   first-hook check, `mcp_exec` through the agent's environment) sees the project with no
   change of its own. Cost: one argument and one read per launch.
2. A third layer in `runtime._launch_env`, after the base. The kits' checks run on the
   base, not on the launch environment: a key only in the project would be refused, and
   each check would need the project passed separately (two places to keep in step).
3. Put the variables into `providers.agent_env(agent)` beside LADO's. They would then
   rank with LADO's own variables (over the provider's checks' view) and be named in the
   warnings as LADO's; and the kits' checks would still miss them.

Where the reserved names live:
1. **`agent_env.RESERVED` and `LADO_` (the shell's and LADO's, shared with the outside
   folder) plus `providers.base.CLI_VARIABLES`, the exact names LADO sets for the agent
   CLIs, with a unit test that every provider's `Launch.env` keys are in it** (chosen).
   One list, guarded against drift; no file of one provider changes (the brief's
   threshold).
2. A list per provider class: the names live next to the code that sets them, but four
   provider files change for a constant (the brief's threshold asks the human first),
   and the same test is still needed for names set outside the constant.
3. Whole prefixes (`CLAUDE_*`, `CODEX_*`, `OPENCODE_*`, `KILO_*`): refuses the CLIs' own
   model settings a project may want (the concept's example of a plain variable is a
   local model's address); the human chose exact names (#966).

## Decisions

**D1. The store.** `state.PROJECT_VARIABLES_TABLE`:
`CREATE TABLE IF NOT EXISTS project_variables (project TEXT NOT NULL REFERENCES
projects(id) ON DELETE CASCADE, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY
(project, name))`; `SCHEMA += …`, `SCHEMA_VERSION = 34`, `MIGRATIONS[33] =
[PROJECT_VARIABLES_TABLE]`; `tests/agent_helpers.schema_before` asserts the step and
drops the table to go back. `connect()` already sets `PRAGMA foreign_keys = ON`, so
`state.delete_project` takes the variables along. Functions: `state.project_variables(id)
-> dict[str, str]` (by name), `state.set_project_variable(id, name, value)` (`INSERT …
ON CONFLICT(project, name) DO UPDATE`), `state.unset_project_variable(id, name) -> bool`.

**D2. The name and value rule.** In `lado.projects`, one function for the CLI and the
server: `check_variable(id, name, value: str | None)` raising `ProjectError`, in this
order:
- `agent_env.VARIABLE_NAME.fullmatch(name)` or `the name <NAME> is not a variable name:
  Latin letters, digits and _, not starting with a digit`;
- `name in RESERVED_NAMES or name.startswith(agent_env.RESERVED_PREFIX)`, where
  `RESERVED_NAMES = agent_env.RESERVED | providers.base.CLI_VARIABLES`: `<NAME> is
  reserved: LADO or the agent CLIs set it`;
- the first of `SECRET_WORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD")` in `name.upper()`:
  `<NAME> looks like a secret (<word>): a plain variable takes no name with TOKEN, KEY,
  SECRET or PASSWORD; secrets come with lado project set <id> <NAME> --secret (not built
  yet)`;
- with a value: its UTF-8 bytes over `agent_env.MAX_VALUE` → `the value of <NAME> is
  larger than 64 KiB`; a NUL, or text that does not encode as UTF-8 (lone surrogates
  from argv) → `the value of <NAME> is not UTF-8 text`. An empty value is a value.
The substring match refuses names such as `MONKEY_MODE` too: the price of the concept's
simple rule, accepted (#966).

**D3. The CLI's names.** `providers.base.CLI_VARIABLES = frozenset({"CLAUDE_CONFIG_DIR",
"CODEX_HOME", "OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_DISABLE_AUTOUPDATE",
"KILO_CONFIG", "KILO_CONFIG_CONTENT", "KILO_DISABLE_AUTOUPDATE", "KILO_NO_DAEMON"})`.
Claude Code's launch sets none today; `CLAUDE_CONFIG_DIR` is reserved because it picks
the CLI's login, and `OPENCODE_CONFIG`/`KILO_CONFIG` because they would replace the
config LADO writes. A unit test builds each provider's `launch_command` (as the
providers' tests do) and asserts its `Launch.env` keys are reserved; a provider that
adds a variable fails it until the list grows.

**D4. The layer.** `agent_env.resolve(project: Mapping[str, str] | None = None)` returns
`{**base, **outside().values, **(project or {})}`; `timed()` keeps calling it without a
project (doctor). `runtime._base_env(project: str | None)` passes
`state.project_variables(project)` when `project` is set. Callers:
- `start_session`: the session's project is `old.project if old else project`, known
  before `_new_sessions_provider`; both `_base_env()` calls take it (a start, a resume,
  and a session `start_session` starts from a supervisor, whose `project` S3 fills);
- `spawn_worker`: `sess.project` (a worker and a flow run's worker alike).
`cli._agents_path` (`lado kit show`'s `expects` lines) stays without a project: `PATH` is
reserved, so a project never changes it.

**D5. A project's name LADO sets.** `runtime._outside_warnings` becomes
`_layer_warnings(agent, launch, project, *, files)`: besides the outside folder's lines,
each name of `state.project_variables(project) & ours.keys()` gives `project variable
<name> of <id> not used: LADO sets <name> for <provider>`, at a start, a resume and a
spawn; `_launch_env` already lets LADO's and the provider's values win. The name rule
makes this almost impossible; it remains for a provider that adds a variable later and a
row stored before.

**D6. Set and unset in the core.** `projects.set_variable(id, name, value) -> list[str]`
and `projects.unset_variable(id, name) -> list[str]`: `get(id)` first (`NoSuchProject`,
`unknown project "<id>"`), then D2, then the write; both answer `running(id)`, the names
of `state.project_sessions(id)` whose `runtime.session_status` is not `STOPPED`, by name.
`unset_variable` of a name the project lacks raises `NoSuchVariable(ProjectError)`:
`project <id> has no variable <NAME>; its variables: <names>` (`projects.names`, or
`none`). `unset` checks no name rule: a row stored before a rule changed can still be
removed.

**D7. The CLI.** `lado project set <id> NAME VALUE` and `lado project unset <id> NAME`,
subparsers of `project`, `_human_only("project set")` / `("project unset")` first (in
`cmd_project`'s list with `create`, `rename`, `delete`). Output: `Set <NAME> in project
<id>.` / `Removed <NAME> from project <id>.`, then `Agents started from now on get it.`
or `Agents started from now on get it; running sessions of <id> keep the old environment
until restarted: <names>` (`projects.names`). A value starting with `-` is given after
`--` (argparse's rule; `docs/cli.md` says so). `lado project show` prints after the
repositories `  variables:` and `    <NAME>  <value>` by name, names padded to one width,
`\n` and `\r` in a value shown as the two characters `\n`, `\r`; or `  variables: none`.

**D8. The server.** `models.ProjectVariable{name, value}`; `ProjectInfo.variables:
list[ProjectVariable]` (`launch.project_info`, by name); `models.VariableValue{value}`;
`models.VariableChange{project: ProjectInfo, running: list[str]}`.
`PUT /api/projects/{id}/variables/{name}` (`guard.changes`, body `VariableValue`) →
`projects.set_variable`; `DELETE /api/projects/{id}/variables/{name}` (`guard.changes`)
→ `projects.unset_variable`; both through `project_core` with `NoSuchVariable` added to
its 404s (`project_refused`'s text: no such project, repository or variable); another
`ProjectError` is 400 with its text. `make web-types`; the UI does not use them yet (S6).

**D9. `lado doctor`.** `doctor.check_project_variables() -> Check | None`: with
`agent_env.outside().values` not empty, each project (by id) whose variables share names
with it gives `<id> overrides <NAMES> of LADO_ENV_DIR` (names sorted, `, `); the projects
joined by `; `; `Check("Project variables", INFO, …)`, placed after `Variables from
outside`; none → no line. A database that cannot be read (no `lado.db` yet) → no line.
`doctor.report` (the bug report) does not change: it holds neither.

**D10. The test MCP server of the smoke.** A kit under `tests/smoke/` (a folder kit, as
the integration tests' kits are made) whose worker or lead has an MCP server `probe`:
`command: [<python>, <probe.py>]`, `env: {PROBE_VALUE: ${SMOKE_PROBE_VALUE}, PROBE_OUT:
<file>}`. `probe.py` (standard library) writes to `PROBE_OUT` JSON `{"template": <PROBE_VALUE>, "inherited": <its own SMOKE_PROBE_VALUE or null>}`, then serves nothing and exits. The smoke test makes a project
with `SMOKE_PROBE_VALUE` set only there, a repository with `--new`, starts the session in
it with that kit, waits for the file and asserts both values are the project's. A server that exits is a failed MCP server to
the CLI, which goes on (no model is needed). If a provider does not start a kit's MCP
server before its first model call, the brief's threshold applies: the developer asks the
human through the supervisor (live run before the release, or another way). The variable's
name is a plain one (not `*KEY*`): S5a has no secrets.

**D11. No protocol change.** `mcp_server.py`, `hooks.py` and the files of one provider do
not change; no MCP tool is added (the concept: only the human sets variables). `kits.py`
does not change: it already checks the environment it is given.

**D12. `LADO_AGENT_ENV=inherit`.** In that mode an agent's `lado mcp` launches others from
its own environment, which holds its project's variables of its start: an `unset`
reaches a worker its supervisor spawns only in the default mode `shell`, which resolves
the login shell anew. The outside folder has the same limit today; `docs/design/agents.md`
says so, and the integration tests that check `unset` spawn from the test process.

**D13. Docs and version.** `docs/cli.md` (`lado project set|unset`, `show`'s
variables, `--` before a value starting with `-`), `docs/design/projects.md` (the "What
is built" box: S5a; "Variables and secrets": plain variables built, secrets not; "Where a
project's data lives": the table, schema 34; the security boundary said plainly: projects
of one LADO share one operating-system user and are not isolated; sessions made under
`projects/` before S3 have no project and get no variables, #808), `docs/design/agents.md`
(the layers, D4, D5, D12), `docs/design/modules.md` (`projects.py`, `agent_env.py`,
`state.py`, `doctor.py`, `providers/base.py`, `server/`), `docs/install.md` (the agents'
variables: per project with `lado project set`). CHANGELOG: one line under `## 0.43.0
(unreleased)`, Added. Minor (already).

## Risks / Trade-offs

- A project variable can change how the agent CLI or its tools behave (`NODE_OPTIONS`,
  `PYTHONPATH`, a model's address): that is its purpose; only the human sets it (agents
  are refused), and the security boundary is stated: projects of one LADO are not
  isolated.
- `KEY` and the other words as substrings refuse some harmless names (`MONKEY_MODE`,
  `KEYBOARD`); until S5b such a name has no way in; the refusal says why.
- Values are visible: `lado project show` (agents can run it) and the API show them, as
  the concept wants plain variables. Anything secret waits for S5b.
- Between `lado project set` and the next launch nothing is checked against the kits: a
  removed key shows only when the next agent of the session is refused.
