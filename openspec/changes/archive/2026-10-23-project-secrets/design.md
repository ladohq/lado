## Context

S5a (`project-variables`, archived 2026-10-23) gave a project plain variables in
`lado.db` (`project_variables`, schema 34) and an environment layer:
`runtime._base_env(project)` reads them and passes them to
`agent_env.resolve(project=…)`, which lays them over the login shell's and the outside
folder's (`agent_env.outside`, the `LADO_ENV_DIR` folder, `/run/secrets` in LADO's
image). Everything that reads the base environment (the kits' `${NAME}` check through
`ResolvedAgent.mcp_servers`, `expects` commands, the provider's first-hook check) and
`mcp_exec`, which fills a server's templates from the agent's own environment, saw the
project's variables with no change of its own. A name with `TOKEN`, `KEY`, `SECRET` or
`PASSWORD` is refused as a plain variable, waiting for this step.

The agent's environment reaches its tmux window through `agent_env.command`: a file
`env.json` (600) in the agent's config folder under `LADO_HOME`, read and removed by the
window's first process (`agent_env.main`) before it execs the CLI. No value goes into a
process's arguments or the tmux server's environment; the spec `agent-variables` already
names this file as the one place outside values go.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the
epic's plan (S5b) and the brief of gate #87. The human's answers of this step: questions
#1060 (one value per name), #1062 (any name may be a secret), #1064 (the launch file),
#1066 (entering the value), #1068 (a file with loose permissions).

## Goals / Non-Goals

Goals: secrets per project in files, set, replaced and removed by the human (CLI, API),
never read back; the same layer as plain variables; one reader with the outside folder;
link-safe writes and removals; `lado doctor`; deletion with the project; a canary test.

Non-goals: the UI (S6), outside secrets per project, isolation of projects, a way to
deliver the environment without `env.json`, reading a secret back by any means.

## Options

Where a secret's value lives:
1. **One file per secret in `<LADO_HOME>/projects/<id>/secrets/`, read by the outside
   folder's reader** (chosen; the concept's). Atomic per secret by a rename, so the CLI
   and the UI never overwrite each other's names without a lock; listing never opens a
   value; a backup of `lado.db` and the bug report's counts never see one; the same
   checks and `doctor` lines as `/run/secrets`. Cost: a second store beside `lado.db`
   (the conflict rule D4) and link-safe file code (D3).
2. A column in `lado.db` with a "secret" flag. One store and one transaction, but a value
   then sits in every copy of the database, in SQLite's free pages after a replace, and
   one query away from the API's variables; the concept rules it out.
3. The OS keychain. No such thing in LADO's container or on a headless Linux, and a
   different backend per platform: against "neutral core" and the LADO manager's API.

How the reader is shared:
1. **`agent_env.read_folder(folder, own=…)`, the body of today's `outside`, with the
   project's extra checks behind `own`** (chosen): one function, one set of rules, as the
   concept asks.
2. A second reader in `projects`. Two copies of the rules would drift (the size, the line
   break, the names).

## Decisions

**D1. The store.** `project_secrets.py` (new, standard library) owns
`<LADO_HOME>/projects/<id>/secrets/`: `folder(id)` derives it from `state.home_path()`;
`names(id)` lists the files of the folder that pass the reader's checks needing no
content (no link, a regular file, a variable name, not reserved), sorted, without opening
any: `show` and the API list them, the concept's "the list of files shows which secrets
are set, never their values"; `read(id)` is the reader itself, called only for a launch
and by `doctor`; `write(id, name, value)`, `remove(id,
name)` and `remove_all(id)` are the only writers. The security code of the step is in
this one module so a review reads it whole. `projects.py` keeps the rules and calls it.

**D2. Atomic write.** `write` opens each folder from `LADO_HOME` down with `os.open(…,
O_DIRECTORY | O_NOFOLLOW)` relative to the one above (`dir_fd`), making a missing one with
`mkdir(mode=0o700, dir_fd=…)` and `fchmod` 700 (umask), then creates a temporary
`.<name>.<random>.tmp` with `O_CREAT | O_EXCL | O_NOFOLLOW`, mode 600, writes, `fsync`s,
renames it over `<name>` with both `dir_fd`s, and `fsync`s the folder. Any failure
removes the temporary file before it raises. Names starting with `.` are passed over by
the reader, so a temporary file is never given to an agent. `os.open`'s `dir_fd`,
`O_NOFOLLOW`, `mkdir`/`rename`/`unlink`/`stat` with `dir_fd` work on Linux and macOS, the
platforms LADO runs on (native Windows is refused by `console.py`).

**D3. No link on the way.** Each folder is opened with `O_NOFOLLOW`; a link there fails
with `ELOOP` (Linux) or `ENOTDIR`-like errors, which `write`/`remove` turn into
`ProjectError("<path> is a symbolic link: LADO writes and removes a project's secrets only
in its own folders")` after an `lstat` names the link. Before a rename or an unlink the
target is `stat`ed with `follow_symlinks=False`: a link there is refused, not replaced.
`remove_all(id)` checks `projects/`, `<id>/`, `secrets/` and every entry of `secrets/`
before it removes anything, then removes the entries, `secrets/` and `<id>/` by `dir_fd`.
`LADO_HOME` itself may be a link (the human's choice); the chain starts below it.

**D4. One value per name.** `projects.set_secret` refuses a name that is a plain variable
of the project, and `set_variable` a name that is a secret, both with the `unset` hint
(question #1060). The two stores have no common transaction, so moving a value from one
to the other in one command could leave both after a failure; the human does it in two.
`projects.unset(id, name)` removes the name from whichever store holds it, so the CLI's
one `unset` serves both; `unset_variable` (plain only) and `unset_secret` (secret only)
stay for the API, whose routes are by kind (D9).

**D5. Names.** `check_variable` is split: `check_name(name)` (a variable name, not
reserved) for both kinds, and the secret-looking test for a plain variable only. A secret
may take any name `check_name` passes (question #1062). The refusal's hint loses "(not
built yet)".

**D6. The value in the CLI.** `--secret` makes the positional value optional; given with
it, the command refuses before anything else (`argparse` cannot tell where the value
came from, so the check is on its presence). `_human_only` runs before stdin is read. On a
terminal (`sys.stdin.isatty()`) `getpass.getpass("Value of NAME (not shown): ")` reads
one line; otherwise `sys.stdin.buffer.read(MAX_VALUE + 2)` reads the whole input, decoded
as UTF-8, with one `\n` or `\r\n` at the end dropped; more than 64 KiB is refused as for a
plain value. An empty value is refused (question #1066). The value never goes into an
exception's text.

**D7. The layer.** `runtime._base_env(project)` passes `{**state.project_variables(id),
**project_secrets.read(id).values}` to `agent_env.resolve(project=…)`; D4 keeps the two
disjoint, and the secret goes last should a hand-made file collide. `_layer_warnings`
adds the reader's unused lines for the project's secrets folder at a start or resume
(`files=True`), as `project secret <name> of <id> not used: <reason>`. A secret whose name
LADO or the provider sets cannot occur: every such name is reserved, and the reader
refuses a reserved name in the project's folder. `kits.py`, `mcp_exec.py`,
`mcp_server.py`, `hooks.py` and the providers do not change.

**D8. The reader.** `agent_env.read_folder(folder, *, own)` returns
`Outside(folder, values, unused)`; `outside()` becomes `read_folder(LADO_ENV_DIR's
folder, own=None)`. `own` is a predicate of reserved names (the project's
`RESERVED_NAMES`, which `agent_env` cannot import from `projects`); with it the reader
also refuses the folder when it is a link or has any of the mode's 077 bits (`not used:
a symbolic link` / `readable or writable by others: chmod 700 it`), and a file that is a
link (`a symbolic link`; `DirEntry.is_symlink`, no following) or has any 077 bit
(`readable or writable by others: chmod 600 it`, question #1068). The outside folder
keeps following links (Docker's and Kubernetes' secrets are links) and its modes
(Docker's). A missing folder is no layer and no line, as for the outside folder.

**D9. Server.** `PUT` and `DELETE /api/projects/{id}/secrets/{name}` under
`guard.changes`, answering `VariableChange`; `ProjectInfo.secrets: list[str]`. The body
model is `SecretValue {value: str}`. FastAPI's 422 echoes the input it could not read
(`detail[].input`); a `RequestValidationError` handler answers 422 without `input` (and
without `ctx`) when the path is under `/api/projects/{id}/secrets/`, other routes keep
their answers. An unknown secret on `DELETE` is 404 (`NoSuchVariable`); `DELETE
/api/projects/{id}/variables/{name}` stays plain only, a secret's name there is 404, so
the UI of S6 never removes a secret through the variables' route by mistake. `make
web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.

**D10. Delete and create.** `projects.delete` checks the data folder for links
(`project_secrets.check_removable`) before it removes anything, then removes the project
folder, forgets the sessions, calls `project_secrets.remove_all`, and removes the record
last; a failure keeps the record and a rerun finishes. `projects.create` refuses an id
whose `<LADO_HOME>/projects/<id>` exists (`lexists`): only a failed deletion leaves one,
and a new project must not inherit its secrets. `lado uninstall` removes `LADO_HOME`, the
secrets with it, unchanged.

**D11. doctor.** `check_project_secrets()` reads each project's folder with the reader
and prints `[warn] Project secrets: <id>: <name> not used: <reason>; …` when any file or
folder is unused, nothing otherwise. `check_project_variables` takes the secrets' names
with the plain ones for the override line. Neither opens a value for its text.

**D12. The canary.** `tests/integration/test_project_secrets_canary.py` with the fake
agent and telemetry on, sent to `tests/fake_endpoint.py`: a unique value
(`canary-<uuid>`) set by `lado project set --secret` from stdin and by `PUT` through a
real server; a session of the project started, a worker and a flow run's worker spawned,
`start_session`; a refused set (a conflict), refused API calls (400, 404, 422); `lado
doctor`, `lado bug-report`, `lado log`, `lado project show`, `GET /api/projects/{id}`,
the change feed's entries. While the agents run it reads every process's arguments
(`ps -eo args`) and `tmux show-environment -g` of the test's server; at the end it
searches every file under `LADO_HOME` except `projects/<id>/secrets/` (so `lado.db`,
`errors.jsonl`, the logs, telemetry's outbox, the agents' config folders), every output
and every answer for the value, and finds it nowhere; no `env.json` is left. The UI feed
is the server's change feed, checked without a browser (the brief's threshold: no place
needs a manual check).

**D13. `LADO_AGENT_ENV=inherit`.** As D12 of S5a: in that mode a supervisor's `lado mcp`
spawns workers from its own environment, so an `unset` of a secret does not reach the
workers of a supervisor that ran before it. `docs/design/agents.md` says so beside D12.

**D14. The smoke.** The S5a probe kit gains a second env template, `PROBE_SECRET:
${SMOKE_PROBE_TOKEN}`; the smoke test sets `SMOKE_PROBE_TOKEN` as the project's secret
(`project_secrets` through `projects.set_secret`) and asserts the probe got it, per
provider.

**D15. Docs and version.** `docs/cli.md` (`--secret`, the prompt, stdin, the refusals,
`unset`'s line, `show`'s secrets), `docs/design/projects.md` (the "What is built" box:
S5b; "Variables and secrets": built; "Where a project's data lives": the secrets folder
built; a backup of the volume holds the secrets; `lado uninstall` removes them with
`LADO_HOME`; the security boundary said plainly), `docs/design/agents.md` (the layers
with secrets, D13), `docs/design/modules.md` (`project_secrets.py`, `agent_env.py`,
`projects.py`), `docs/install.md` (secrets per project beside the outside folder; for
clients that must not mix, a separate LADO), CHANGELOG under `## 0.43.0 (unreleased)`.
The minor is already bumped for 0.43.0; no schema migration.

## Risks / Trade-offs

- The launch file `env.json` holds a secret for the moment between the launch and the
  window's start, as it does every key today (question #1064); a window that never starts
  leaves it until the agent's next launch overwrites it. The canary test checks that none
  is left after a normal start.
- A process of the same OS user can read every project's secrets: projects of one LADO
  are no security boundary (the concept); the docs say so.
- The file mode check makes a secret unusable after a careless `chmod`; the warning at
  the start and in `doctor` names the fix.
