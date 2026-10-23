Task: LAD-130

## Why

Step S5a of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "Environment
variables and secrets" without the secrets, "Where a project's data lives", "The security
boundary" and "The architectural frame"). Since S3 a session belongs to a project, but its
agents still get the one environment of the whole LADO: the login shell's, then the
outside folder `LADO_ENV_DIR` (`/run/secrets` in LADO's image). Two sessions of two
projects that need different values of one variable (a board's address, a local model's
address) cannot get them.

The root cause: an agent's environment has no layer between the outside folder and LADO's
own variables. `runtime._base_env()` returns `agent_env.resolve()` (login shell, then the
outside folder) for every launch, whatever its session's project; `lado.db` keeps no
variables; the kits' `${NAME}` check of MCP servers (`kits.ResolvedAgent.mcp_servers`)
and `_check_commands` look at that same base environment, so a value set only in a
project could not pass them either.

## What Changes

- **Store.** A table `project_variables` in `lado.db` (schema 34), one row per variable
  of a project, removed with its project (`ON DELETE CASCADE`).
- **CLI.** `lado project set <id> NAME VALUE` sets a plain variable (a new one or over the
  old value); `lado project unset <id> NAME` removes it. Both refuse inside an agent, as
  the other changing `lado project` commands do; no MCP tool is added. Both say that the
  agents started from now on get the change and name the project's sessions that run now
  (they keep the environment they started with until restarted). `lado project show`
  lists the project's variables with their values (`  variables:` after the
  repositories, `  variables: none` without).
- **Protected names**, one list in the core shared by the CLI and the API:
  - a name that is no environment variable name (`[A-Za-z_][A-Za-z0-9_]*`) is refused;
  - a reserved name is refused: the names the login shell and the terminal keep (those
    the outside folder already refuses: `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `PWD`,
    `OLDPWD`, `SHLVL`, `_`, `TERM`, `TERM_PROGRAM`, `TERM_PROGRAM_VERSION`, `TMUX`,
    `TMUX_PANE`), every `LADO_*`, and the exact names LADO sets for the agent CLIs
    (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`,
    `OPENCODE_DISABLE_AUTOUPDATE`, `KILO_CONFIG`, `KILO_CONFIG_CONTENT`,
    `KILO_DISABLE_AUTOUPDATE`, `KILO_NO_DAEMON`);
  - a name that looks like a secret (`TOKEN`, `KEY`, `SECRET` or `PASSWORD` anywhere in it,
    in any case) is refused as a plain variable, with a hint at `--secret`, which step S5b
    brings.
- **The project's layer.** An agent's environment becomes: login shell → outside folder →
  the project's variables → LADO's and the agent CLI's variables, each later layer over the
  one before, built by one core function for every provider (`agent_env.resolve` with the
  project's variables; `runtime._base_env` reads them for the session's project). The
  whole session in a project gets them: its supervisor (start and resume), its workers,
  its flow runs' workers, and a session `start_session` starts (it is in the same project
  since S3); the CLI's subagents and the kits' MCP servers inherit them from the agent. A
  session without a project gets none. A project variable whose name LADO or the
  provider sets for a launch keeps LADO's value, with a warning in that launch's warnings.
- **Kit keys.** The kits' checks (`${NAME}` of an MCP server, `expects` commands on
  `PATH`) see the project's variables: a key set only in the project passes, and reaches
  the server through `lado.mcp_exec` from the agent's environment; the same kit in a
  session without the key is refused as today. In this step a key whose name looks like a
  secret (`YOUGILE_API_KEY`, `GH_TOKEN`) cannot be a plain variable: it comes per project
  with S5b's secrets, through the same layer.
- **The server's API** (for the UI of S6 and the LADO manager, with the token, in
  OpenAPI): `GET /api/projects/{id}` gains `variables`; `PUT
  /api/projects/{id}/variables/{name}` with `{value}` sets one and `DELETE
  /api/projects/{id}/variables/{name}` removes one, both through `guard.changes`, both
  answering the project and the names of its running sessions; 404 for an unknown project
  (and an unknown variable on delete), 400 for a refused name or value.
- **`lado doctor`** prints `[info] Project variables: <id> overrides <NAME>[, …] of
  LADO_ENV_DIR[; …]` when a project's variable has the name of a file the outside folder
  gives; no value, no line otherwise.
- **Docs**: `docs/cli.md`, `docs/design/projects.md` (variables built; the security
  boundary said plainly; sessions made under `projects/` before S3 have no project and get
  no variables, #808), `docs/design/agents.md` (the layers), `docs/design/modules.md`,
  `docs/install.md` where it describes the agents' variables.
- **CHANGELOG**: one line under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- **AC-1** `lado project set shop BOARD_URL https://a` and `lado project set acme
  BOARD_URL https://b`, then a session in each project: in `shop` the supervisor, a worker,
  a flow run's worker and the session its supervisor starts with `start_session` have
  `BOARD_URL=https://a`; in `acme` every agent has `https://b`.
- **AC-2** The layers: with `BOARD_URL` from the login shell and from a `LADO_ENV_DIR`
  file, an agent of `shop` has the project's value; without the project's variable it has
  the outside folder's; a session without a project has the outside folder's.
- **AC-3** A session without a project gets no project's variable.
- **AC-4** `lado project unset shop BOARD_URL`: an agent started after it has no
  `BOARD_URL` from the project; agents started before keep theirs; the command prints that
  only agents started from now on get the change and names the running sessions of `shop`.
- **AC-5** Refused names, exit 1, nothing stored: `GH_TOKEN`, `yougile_api_key`,
  `DB_PASSWORD` (looks like a secret, the hint names `--secret`); `PATH`, `HOME`,
  `LADO_HOME`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME` (reserved); `1X`, `A-B` (no variable
  name); a value over 64 KiB or with a NUL.
- **AC-6** From an agent (`LADO_AGENT` set) `lado project set` and `unset` exit 1 with
  `lado: lado project set is for the human; agent "<agent>" cannot use it` (and `unset`);
  `lado project show` works and lists the variables.
- **AC-7** An unknown project: `set`, `unset` and `show` exit 1 with `lado: unknown project
  "<id>"`; `unset` of a name the project lacks exits 1 naming the project's variables.
- **AC-8** `lado project delete shop --yes` removes its variables with it: a project made
  again as `shop` has none.
- **AC-9** A kit whose MCP server has `env: {URL: ${BOARD_URL}}`: a session of `shop`
  (with `BOARD_URL` only in the project) starts and the server's process gets
  `URL=https://a` through `mcp_exec`; a session without a project and without
  `BOARD_URL` is refused with the kit's error naming `BOARD_URL`, as today.
- **AC-10** A project variable named as a variable a provider sets for its launch (stored
  before that name became reserved) keeps the provider's value, and the launch's warnings
  say `project variable <NAME> of <id> not used: LADO sets <NAME> for <provider>`.
- **AC-11** `lado doctor` with `LADO_ENV_DIR` giving `BOARD_URL` and project `shop`
  setting it prints `[info] Project variables: shop overrides BOARD_URL of LADO_ENV_DIR`;
  with no overlap there is no such line; no value is printed; the bug report has no
  project variable's name or value.
- **AC-12** The API: `GET /api/projects/shop` has `variables`; `PUT
  …/variables/BOARD_URL` sets it and answers the project and the running sessions; `DELETE`
  removes it; an unknown project 404, an unknown variable on `DELETE` 404, a refused name
  400 with its reason; without the token 401/403 as the other changes; `web/openapi.json`
  and `web/src/api.gen.ts` are current.
- **AC-13** `lado.db` of schema 33 migrates to 34 with its projects and sessions intact,
  from `tests/agent_helpers.previous_schema`.
- **AC-14** The smoke of each provider (Claude Code, Codex, OpenCode, Kilo): a test kit's
  MCP server, started by the real CLI in a session of a project, writes whether it sees the
  project's variable (through its `${NAME}` and its own environment), and the test reads
  `yes`.

## Out of scope

- Secrets (`--secret`, `~/.lado/projects/<id>/secrets/`, the canary test): step S5b. Until
  then a kit key whose name looks like a secret cannot be set per project (AC-9 uses a
  plain name).
- The UI of variables, the mark of overridden outside values and the security boundary's
  warning in the UI: step S6.
- Global variables and variables of a session without a project; outside secrets per
  project (`/run/secrets/projects/<id>/`): "Not now" of the concept.
- Giving a new value to an agent that runs: an operating system process cannot change its
  environment from outside; the commands say to restart the session.
- S2's findings, G1 of S3, X3 of S4: step S7.
- Variables in the bug report, telemetry or `lado log`: none (nothing to count is needed
  yet).
- Under `LADO_AGENT_ENV=inherit` (tests, special setups) an agent that launches another
  passes its own environment on, project variables and outside values included, as for
  the outside folder today; the default (`shell`) resolves anew and is exact.

## Impact

- Code: `src/lado/state.py` (table, migration 33→34, the variables' reads and writes),
  `projects.py` (`set_variable`, `unset_variable`, `variables`, the name rule, running
  sessions), `agent_env.py` (the project's layer in `resolve`, the reserved list),
  `providers/base.py` (the names LADO sets for the agent CLIs, one list), `runtime.py`
  (`_base_env` with the session's project at a start, resume and `spawn_worker`; the launch
  warnings for a project variable LADO overrides), `cli.py` (`lado project set|unset`,
  `show`), `doctor.py`, `server/app.py`, `server/models.py`, `server/launch.py`;
  `web/openapi.json`, `web/src/api.gen.ts`.
- Not changed: `mcp_server.py`, `hooks.py`, the files of one provider, `kits.py`'s rules
  (they get the environment with the project's layer), the UI's screens.
- Tests: unit, server, migration, integration with the fake agent, smoke per provider.
- Users: new CLI commands and API endpoints, a schema migration. Version: **minor**
  (0.43.0 is already the unreleased minor; one CHANGELOG line).
