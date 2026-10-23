Task: LAD-132

## Why

Step S5b of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "Environment
variables and secrets", "Where a project's data lives", "The security boundary",
"Deletion" and "The architectural frame"). S5a gave a project plain variables, but a
name that looks like a secret (`YOUGILE_API_KEY`, `GH_TOKEN`) cannot be one: the keys a
kit's MCP server needs, which differ per client, still come only from the login shell or
the outside folder of the whole LADO. The epic's goal, sessions for different clients
with different keys, is reached only when a project can hold such a key.

The root cause: the project's layer (`agent_env.resolve(project=…)`,
`runtime._base_env`) is fed from `lado.db` alone, and `lado.db` is no place for a value
nobody may read back (it goes into backups of the database, the bug report counts rows,
the API returns every variable's value). The concept puts secrets in files beside the
database, in the outside folder's form, read by the same core function.

## What Changes

- **Store.** One file per secret in `<LADO_HOME>/projects/<id>/secrets/` (in LADO's image
  on the home volume, not in the workspace): the file's name is the variable's name, its
  content the value. Folders 700, files 600. Each secret is written atomically on its own
  (a temporary file in the same folder, then a rename); no lock. The list of secrets is
  the list of files; no value is read to list them.
- **One reader.** The outside folder's reader of `agent_env` becomes one function for both
  folders, with all its checks (a name, a regular file, at most 64 KiB, UTF-8 without NUL,
  one line break at the end dropped, a reserved name refused). For the project's folder
  it also refuses a symbolic link and a file or folder that others may read or write
  (not 600 / 700): such a file is not used and is named with why, never with its content.
- **No link on the way.** Writing or removing a secret, and removing the project's data
  folder, refuse when `<LADO_HOME>/projects`, `<id>`, `secrets` or the secret's file is a
  symbolic link, naming the link; nothing is followed.
- **CLI.**
  - `lado project set <id> NAME --secret` asks for the value without echo (`Value of NAME
    (not shown): `) on a terminal; without one it reads the whole of stdin (one line
    break at the end dropped), for scripts and the LADO manager. A value given on the
    command line with `--secret` is refused (`ps` and the shell's history keep it); an
    empty value is refused with the hint at `unset`. A second `set --secret` replaces the
    secret. It prints `Set secret NAME in project <id>.` and the agents' line of S5a.
  - `lado project unset <id> NAME` removes a plain variable or a secret, whichever the
    name is; its agents' line is fixed: `Agents started from now on do not get it.`
    (S5a printed "get it" after a removal).
  - `lado project show` lists the secrets by name after the variables (`  secrets:` and
    one name per line, or `  secrets: none`), never a value.
  - All three refuse inside an agent, as the other changing `lado project` commands do.
- **Names.** S5a's rule (`projects.check_variable`) stays one rule for the CLI and the
  API: a name that is no variable name, or reserved, is refused for a secret too. A secret
  may take any other name, also one that does not look like a secret (`DATABASE_URL`). A
  name is either a plain variable or a secret: setting one while the other holds the name
  is refused with the hint to `unset` it first. The hint of S5a's refusal of a
  secret-looking plain variable loses its "(not built yet)".
- **The project's layer.** `runtime._base_env` lays the project's secrets with its plain
  variables (`agent_env.resolve(project=…)`): login shell → outside folder → project →
  LADO and the agent CLI. A project's secret wins over the outside folder's value of the
  same name. The kits' `${NAME}` check and `mcp_exec` see a project's secret as they see a
  plain variable: a kit key set only as the project's secret passes and reaches the MCP
  server. A launch names a secret file not used, and a secret whose name LADO sets for the
  launch, in its warnings, as for the outside folder.
- **Server API** (with the token for changes, `guard.changes`, in OpenAPI):
  `PUT /api/projects/{id}/secrets/{name}` with `{value}` sets or replaces a secret,
  `DELETE /api/projects/{id}/secrets/{name}` removes one, both answering `{project,
  running}` as the variables' endpoints do; `GET /api/projects/{id}` gains `secrets`, the
  names. No endpoint returns a value. A request the server cannot read (422) on these
  routes answers without the input it was given.
- **`lado doctor`.** A check `Project secrets` warns of each file of a project's secrets
  folder that is not used, by project and file name with why, never its content; the
  `Project variables` override line names the secrets that override the outside folder
  too.
- **Delete and create.** `lado project delete --yes` removes `<LADO_HOME>/projects/<id>/`
  too, after the workspace folder and the sessions, before the record; a link on the way
  refuses and the record stays. `lado project create` refuses an id whose data folder is
  still there (left by a failure), so a new project never inherits old secrets.
- **The canary.** An integration test sets a unique secret through the CLI (stdin) and
  the API, runs sessions, workers, refusals, `lado doctor`, `lado bug-report`, `lado log`
  and the API (errors too), and finds the value nowhere: not in the API's answers or the
  change feed, LADO_HOME's logs and `errors.jsonl`, `lado.db`, `lado log`, the bug report,
  telemetry's payload, `show`'s and `doctor`'s output, a process's arguments or the tmux
  server's environment; outside `secrets/` only in the agent's launch file while the
  window starts, which is gone once it has.
- **Docs.** `docs/cli.md`, `docs/design/projects.md` (what is built; the backup of the
  volume holds the secrets; `lado uninstall` removes `LADO_HOME` with them; the security
  boundary said plainly), `docs/design/agents.md` (the layers; secrets under
  `LADO_AGENT_ENV=inherit` as D12 of S5a), `docs/design/modules.md`, `docs/install.md`
  (secrets per project beside the outside folder), CHANGELOG under `## 0.43.0
  (unreleased)`.

## Acceptance criteria

- AC-1. `lado project set shop GH_TOKEN --secret` on a terminal asks without echo and
  stores the value in `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` (600, folders 700);
  without a terminal it takes stdin; a value on the command line, an empty value, a
  reserved or invalid name, an unknown project and a run inside an agent are refused and
  store nothing.
- AC-2. A second `set --secret` replaces the value atomically: no temporary file stays,
  and a reader sees the old or the new value, never a part.
- AC-3. `lado project unset shop GH_TOKEN` removes the secret; `unset` of a plain
  variable or a secret prints `Agents started from now on do not get it.` (with the
  running sessions when there are).
- AC-4. A name is a plain variable or a secret, never both: setting the other kind is
  refused with the `unset` hint; a secret may take a name that does not look like one.
- AC-5. `lado project show` and `GET /api/projects/{id}` list secrets by name, never a
  value.
- AC-6. Every agent of a session in the project (supervisor at start and resume, worker,
  flow run's worker, `start_session`'s supervisor) gets the project's secrets; two
  projects with one secret name each get their own value; a session without a project
  gets none; a project's secret wins over `LADO_ENV_DIR`'s.
- AC-7. A kit's MCP server whose `${NAME}` is only a project's secret starts and gets the
  value through `mcp_exec`; in a session without the project the same kit is refused as
  today.
- AC-8. The server sets, replaces and removes a secret with the change token; an unknown
  project or secret is 404, a refused name or value or a name held by a plain variable
  400; no answer, errors and 422 included, holds the value.
- AC-9. A file of a project's secrets folder that is not usable (a link, not a regular
  file, larger than 64 KiB, not UTF-8, an invalid or reserved name, readable or writable
  by others, or the folder so) is not given to agents and is named in the launch's
  warnings and by `lado doctor` with why, never with its content.
- AC-10. Writing or removing a secret, and `lado project delete`, refuse when
  `projects/`, `<id>/`, `secrets/` or the secret's file under `<LADO_HOME>` is a symbolic
  link, and touch nothing behind it.
- AC-11. `lado project delete shop --yes` removes `<LADO_HOME>/projects/shop/`; after a
  new `lado project create shop` it has no secrets. `create` refuses an id whose data
  folder is still there.
- AC-12. The canary test passes: the value is in none of the places listed under "The
  canary".
- AC-13. The smoke test of each provider sees a project's secret in a kit's MCP server as
  it sees a plain variable.
- AC-14. The docs and CHANGELOG say what is built; the minor version 0.43.0 (unreleased)
  carries it.

## Out of scope

- The UI of secrets (replace and remove on the project's page) and marking the outside
  values a project overrides in the UI: step S6.
- Outside secrets per project (`/run/secrets/projects/<id>/`) and isolation of projects
  from one another: "Not now" of the concept.
- Delivering the environment to the agent's window without the launch file `env.json`:
  every key travels that way today (spec `agent-variables`); the human accepted it for
  project secrets (question #1064).
- A second entry of the value for checking: one entry, as `gh secret set`.
- The findings of S2, G1 of S3, X3 of S4 and F5 of S5a: step S7.
- The release checklist's live run with a secret (`docs/release.md` 4.3): the epic's
  lead edits it at review.

## Impact

- Code: `agent_env.py` (one reader for both folders), a new `project_secrets.py` (the
  data folder, link-safe write and removal, listing), `projects.py` (set/unset of both
  kinds, the conflict, create and delete), `runtime.py` (`_base_env`,
  `_layer_warnings`), `cli.py`, `server/app.py`, `server/models.py`, `server/launch.py`,
  `doctor.py`; `web/openapi.json` and `web/src/api.gen.ts`.
- No change of `mcp_server.py`, `hooks.py`, a provider's files or the agents' protocol; no
  schema migration (secrets are on disk).
- Version: the minor (a CLI flag and API endpoints), already 0.43.0 (unreleased); one
  CHANGELOG line.
