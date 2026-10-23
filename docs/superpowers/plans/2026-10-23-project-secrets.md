# Project secrets Implementation Plan

**Goal:** The human sets, replaces and removes a project's secrets (CLI, API), stored one
file per secret under `<LADO_HOME>/projects/<id>/secrets/` and never read back, and every
agent of a session in that project gets them in the project's layer, with the kits'
checks seeing them and no value leaking anywhere else.

**Architecture:** `agent_env.outside`'s body becomes one reader `read_folder(folder,
own=…)` for the outside folder and a project's secrets folder (the latter refuses links
and loose modes); a new `project_secrets.py` owns the data folder with link-safe atomic
writes and removals by `dir_fd`; `projects.py` adds `set_secret`, one-value-per-name, and
create/delete of the data folder; `runtime._base_env` lays the secrets with the plain
variables, so `kits`, `mcp_exec` and the providers are unchanged. The CLI gets `--secret`,
the server two endpoints and a field, `lado doctor` a check, and an integration canary
test proves no value leaks.

**Tech Stack:** Python 3.10+ (standard library: `os` with `dir_fd`/`O_NOFOLLOW`,
`getpass`), FastAPI/pydantic, pytest (unit, server, integration with the fake agent, smoke
with the real CLIs).

**Spec:** `openspec/changes/project-secrets/` (proposal with AC-1..AC-14, `design.md`
D1-D15, delta specs `projects` and `agent-variables`) and
`docs/superpowers/specs/2026-10-23-project-secrets-design.md` (the human's view and the
manual check).

## Global Constraints

- Python 3.10+, standard library only; no new dependency; no schema migration.
- Texts, verbatim (the spec's):
  - `Value of <NAME> (not shown): `; `Set secret <NAME> in project <id>.`;
  - `Agents started from now on get it.` / `…; running sessions of <id> keep the old
    environment until restarted: <names>` after a set; `Agents started from now on do not
    get it.` / `Agents started from now on do not get it; running sessions of <id> keep the
    old environment until restarted: <names>` after an `unset` (plain or secret);
  - `a secret's value is never given on the command line (ps and the shell's history keep
    it); run lado project set <id> <NAME> --secret and type it, or pipe it in`;
  - `the secret <NAME> is empty; to remove it: lado project unset <id> <NAME>`;
  - `<NAME> is a plain variable of <id>; remove it first with lado project unset <id>
    <NAME>`; `<NAME> is a secret of <id>; remove it first with lado project unset <id>
    <NAME>`;
  - `<NAME> looks like a secret (<word>): a plain variable takes no name with TOKEN, KEY,
    SECRET or PASSWORD; set it as a secret with lado project set <id> <NAME> --secret`;
  - `project <id> has no variable or secret <NAME>; its variables: <names>; its secrets:
    <names>`;
  - `<path> is a symbolic link: LADO writes and removes a project's secrets only in its
    own folders`;
  - `<LADO_HOME>/projects/<id> is left from a project <id>: remove it or choose another id`;
  - `  secrets:` / `    <NAME>` / `  secrets: none`;
  - `project secret <name> of <id> not used: <reason>`; `project secrets folder of <id> not
    used: <reason>`; reasons `a symbolic link`, `readable or writable by others: chmod 600
    it` (a file), `readable or writable by others: chmod 700 it` (the folder), and the
    outside folder's (`not a regular file`, `not a variable name`, `a reserved name`,
    `larger than 64 KiB`, `not UTF-8 text`, `cannot be read: …`, `in a subfolder`);
  - `[warn] Project secrets: <id>: <name> not used: <reason>[; …]`.
- `mcp_server.py`, `hooks.py`, `kits.py`, `mcp_exec.py` and the files of one provider do
  not change (the brief's threshold: if they must, stop and ask the human through the
  supervisor).
- No secret's value in a process's arguments, the tmux server's environment, an
  exception's text, a log line, or any file but its own and the launch file `env.json`.
- Never the user's real home in tests: `HOME`, `LADO_HOME`, `LADO_REPOS` into `tmp_path`;
  no fixed path, port or socket.
- Every write of a secret ends with mode 600, every folder of the chain with 700,
  whatever the umask.

## Review Focus

- A link at `projects/`, `<id>/`, `secrets/` or the file, for set, unset and delete: refused
  before anything is written or removed, the link's target untouched (Task 2).
- A value with a line break inside, `=`, spaces, unicode, a trailing `\r\n`, exactly
  64 KiB: stored and given unchanged but for one trailing line break (Tasks 2, 4, 7).
- A replace while a reader reads: old or new value, never a part; a failing write (raise
  in `os.write`) leaves the old file and no `.tmp` (Task 2).
- A refused request through the API, 400/404/422, never echoes the value (Tasks 5, 7).
- A umask of 0 or 077 still ends with 700/600 (Task 2).

## Task 1: One reader for both folders (D8)

**Files:** Modify `src/lado/agent_env.py`. Test: `tests/test_agent_env.py`.

**Produces:** `agent_env.read_folder(folder: str, *, own: Callable[[str], bool] | None =
None) -> Outside`; `outside()` = `read_folder(<LADO_ENV_DIR>)` unchanged in behaviour;
constants `LOOSE_FILE = "readable or writable by others: chmod 600 it"`, `LOOSE_FOLDER =
"readable or writable by others: chmod 700 it"`, `LINK = "a symbolic link"`.

- [ ] Tests, `own` given (a predicate that says `CODEX_HOME` is reserved): a 600 file is
  given; 644 and 660 files are not (`LOOSE_FILE`); a link to a 600 file is not (`LINK`), the
  target never opened; a folder with 755 or a folder that is a link gives nothing, one line
  for the folder; `CODEX_HOME` and `LADO_X` are `a reserved name`; `.tmp` names passed
  over; a missing folder is no line. The outside folder's existing tests stay green
  (links followed, modes ignored).
- [ ] Implement: move `outside`'s body into `read_folder`, the `own` checks before
  `_take` (`entry.is_symlink()`, `entry.stat(follow_symlinks=False).st_mode & 0o077`;
  the folder by `os.lstat`).
- [ ] `uv run pytest -n0 tests/test_agent_env.py`; commit `One reader reads the outside
  folder and a project's secrets (LAD-132)`.

## Task 2: The secrets store (D1, D2, D3)

**Files:** Create `src/lado/project_secrets.py`. Test: `tests/test_project_secrets.py`
(new).

**Consumes:** Task 1. **Produces:** `project_secrets.data_folder(id) -> Path`
(`state.home_path() / "projects" / id`), `folder(id) -> Path` (its `secrets`),
`read(id, reserved: Callable[[str], bool]) -> agent_env.Outside`, `names(id, reserved)
-> list[str]`, `write(id, name, value: str) -> None`, `remove(id, name) -> bool` (False:
no such file), `check_removable(id) -> None`, `remove_all(id) -> None`; all raising
`LinkRefused(ValueError)` with the link's text, `projects` turns it into `ProjectError`.

- [ ] Tests: `write` makes `projects/`, `<id>/`, `secrets/` 700 and the file 600 under
  umask 0 and 077; content byte-exact; a second write replaces, no other entry left;
  `os.write` patched to raise → old content stays, no `.tmp`; a reader thread looping
  over `open().read()` during 200 replaces sees only whole values; `remove` removes and
  returns False for a missing name; a link at each of `projects/`, `<id>/`, `secrets/`
  and the file: `write`, `remove`, `check_removable` and `remove_all` raise naming that
  path, and the target folder or file is unchanged (one test per link × operation,
  parametrized); `names` lists without opening (patch `builtins.open` to fail) and skips
  a link, a bad name, a reserved name; `remove_all` removes `<id>/` whole and leaves
  `projects/` and the other projects.
- [ ] Implement D2 and D3 with `os.open(name, os.O_RDONLY | os.O_DIRECTORY |
  os.O_NOFOLLOW, dir_fd=parent)` per level from `os.open(LADO_HOME, O_DIRECTORY)`; on
  `OSError` with `ELOOP` or `ENOTDIR`, `os.lstat` the path and raise `LinkRefused` when
  it is a link; temp names `.<name>.<secrets.token_hex(6)>.tmp`; `os.rename(tmp, name,
  src_dir_fd=fd, dst_dir_fd=fd)`; `os.fsync(fd)` of the folder; every fd closed in
  `finally`.
- [ ] `uv run pytest -n0 tests/test_project_secrets.py`; commit `A project's secrets are
  files written atomically and never through a link (LAD-132)`.

## Task 3: Secrets in the core: rules, set, unset, create, delete (D4, D5, D10)

**Files:** Modify `src/lado/projects.py`. Test: `tests/test_project_variables_core.py`,
`tests/test_projects_core.py`.

**Consumes:** Task 2. **Produces:** `projects.check_name(name) -> None`,
`projects.check_variable(id, name, value)` (plain: `check_name` + the secret-word test +
value), `projects.set_secret(id, name, value) -> list[str]`, `projects.secrets(id) ->
list[str]`, `projects.unset(id, name) -> list[str]` (either kind, the CLI),
`projects.unset_secret(id, name) -> list[str]` (the API; `unset_variable` stays plain
only),
`projects.reserved(name) -> bool` (the predicate for Task 1/2).

- [ ] Tests: `set_secret` of `GH_TOKEN`, `DATABASE_URL`, `_X` accepted; `LADO_HOME`,
  `PATH`, `CODEX_HOME`, `A-B` refused with S5a's texts; `""` refused (empty), 65 537
  bytes and `"a\0b"` refused; unknown project `NoSuchProject`; plain↔secret conflict both
  ways with the texts, nothing stored; `unset` removes a secret, a plain one, and
  refuses a missing name listing both kinds; `unset_variable` of a secret's name and
  `unset_secret` of a plain name raise `NoSuchVariable`; `check_variable("GH_TOKEN")` hint without
  "(not built yet)"; `create` refuses an id with a left data folder; `delete --yes`
  removes the data folder, then `create` again → `secrets(id) == []`; a link in the data
  folder makes `delete` refuse before the workspace folder is touched (the folder still
  there), the record stays.
- [ ] Implement.
- [ ] `uv run pytest -n0 <those files>`; commit `A project holds secrets beside its plain
  variables (LAD-132)`.

## Task 4: The project's layer and its warnings (D7)

**Files:** Modify `src/lado/runtime.py`. Test: the runtime tests that cover `_base_env`
and `_layer_warnings` (`tests/test_runtime*.py`), `tests/test_agent_env.py` if needed.

**Consumes:** Tasks 2, 3.

- [ ] Tests: `start_session` of a session in `shop` with the secret `GH_TOKEN` and the
  plain `BOARD_URL` writes both into `env.json` (read the file the recorder's command
  names); a session without a project has neither; `spawn_worker` and a resume read the
  secrets anew (set after the start → the worker has it); `LADO_ENV_DIR` with `GH_TOKEN=out`
  loses to the project's; a kit MCP server with `${YOUGILE_API_KEY}` passes `_spec` when
  the key is only a project secret and its config holds the name, not the value; a 644
  secret file → `started.warnings` has `project secret GH_TOKEN of shop not used:
  readable or writable by others: chmod 600 it` and `env.json` lacks it.
- [ ] Implement `_base_env` and the `files=True` lines of `_layer_warnings`.
- [ ] `uv run pytest -n auto <those files>`; commit `Agents of a session in a project get
  its secrets (LAD-132)`.

## Task 5: CLI and server (D6, D9)

**Files:** Modify `src/lado/cli.py`, `src/lado/server/app.py`, `src/lado/server/models.py`,
`src/lado/server/launch.py`; `web/openapi.json`, `web/src/api.gen.ts` (`make
web-types`). Test: `tests/test_cli.py` (where `lado project set` is tested today),
`tests/test_server_projects.py`.

**Consumes:** Task 3. **Produces:** `models.SecretValue`, `ProjectInfo.secrets: list[str]`,
routes `PUT`/`DELETE /api/projects/{id}/secrets/{name}`.

- [ ] CLI tests: `--secret` with a tty (patch `sys.stdin.isatty` → True and
  `getpass.getpass` → value; assert the prompt text) and from stdin (`"v\r\n"` → `v`,
  `"a\nb\n"` → `a\nb`); a value argument with `--secret` refused before stdin is read;
  empty refused; `LADO_AGENT` set → refused and stdin not read; `show` prints `  secrets:`
  names and never the value (capture); `unset` prints `do not get it` for plain and
  secret, with the running sessions; the S5a `set` test still passes.
- [ ] Server tests: `PUT` stores, answers `project.secrets` with the name, the response
  body has no value; `PUT` again replaces; `DELETE` removes; unknown project 404, unknown
  secret 404, `DELETE /variables/GH_TOKEN` of a secret 404 (the secret stays), reserved name 400, empty 400, conflict 400; `{"secret": "v"}` and
  `{"value": 5}` → 422 without `v`/`5` in the body; without the change token 403 as the
  other changes; `GET /api/projects/{id}` has `secrets`.
- [ ] Implement; `make web-types`; `make web`.
- [ ] `uv run pytest -n auto <those files>`; commit `lado project set --secret and the
  server's secret endpoints (LAD-132)`.

## Task 6: lado doctor (D11)

**Files:** Modify `src/lado/doctor.py`. Test: `tests/test_doctor.py`.

- [ ] Tests: a 644 secret and a link in `shop` → `[warn] Project secrets: shop: GH_TOKEN
  not used: …; shop: X not used: a symbolic link`, exit 0, no value in the output; all
  usable → no line; a secret named like an outside file → the `Project variables`
  override line names it; no lado.db → no line.
- [ ] Implement; `uv run pytest -n0 tests/test_doctor.py`; commit `lado doctor names a
  project's secret file it cannot use (LAD-132)`.

## Task 7: End to end and the canary (D12, D14)

**Files:** Create `tests/integration/test_project_secrets.py`,
`tests/integration/test_project_secrets_canary.py`; modify `tests/smoke/test_smoke.py`,
`tests/smoke/probe_mcp.py` (or the probe kit's files).

- [ ] `test_project_secrets.py` (fake agent): two projects, one secret name, each agent kind
  (supervisor, worker through MCP, flow run's worker, `start_session`) with its project's
  value; the layers' order with `LADO_ENV_DIR`; no project, no secret; `unset` then a new
  worker lacks it; a kit key only as a project secret reaches the MCP server through
  `mcp_exec`, refused in a session without the project; `lado project delete --yes` then
  `create` → no secrets.
- [ ] `test_project_secrets_canary.py` as D12: value `canary-<uuid4>`, telemetry on to
  `tests/fake_endpoint.py`; every place of the spec's scenario "The places checked";
  `ps -eo args` and `tmux -L <socket> show-environment -g` while the agents run; a walk
  of `LADO_HOME` but `projects/<id>/secrets/` reading every file as bytes; no `env.json`
  under the agents' config folders once the windows run.
- [ ] Smoke: the probe kit's second template `PROBE_SECRET: ${SMOKE_PROBE_TOKEN}`, set with
  `projects.set_secret`; the probe's JSON gains `secret`, asserted per provider.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_project_secrets.py
  tests/integration/test_project_secrets_canary.py`; `uv run pytest -m smoke --collect-only
  tests/smoke` (the smoke runs in CI); commit `Project secrets end to end and the canary
  (LAD-132)`.

## Task 8: Docs and CHANGELOG (D13, D15)

**Files:** `docs/cli.md`, `docs/design/projects.md`, `docs/design/agents.md`,
`docs/design/modules.md`, `docs/install.md`, `CHANGELOG.md`, the docstrings of
`agent_env.py`, `projects.py`, `project_secrets.py`.

- [ ] Write what D15 lists; one CHANGELOG line under `## 0.43.0 (unreleased)`, `### Added`:
  **Project secrets**, `lado project set <id> NAME --secret`, files under
  `~/.lado/projects/<id>/secrets/`, never shown.
- [ ] `make lint`; `openspec validate project-secrets --strict`; `openspec validate
  --specs --strict`; commit `Docs of project secrets (LAD-132)`.

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_project_variables.py tests/integration/test_project_secrets.py
tests/integration/test_project_secrets_canary.py`; `make web`; `openspec validate
project-secrets --strict`; `openspec validate --specs --strict`; the trial archive in a
scratch copy of `openspec/` (the brief); CI with the smoke and container cells.

## Tests per requirement

| Requirement (delta) | Layer | Task |
|---|---|---|
| set --secret stores a secret in its own file | unit | 2, 3, 5 |
| value asked without echo, or read from stdin | unit (CLI) | 5 |
| value never on the command line | unit (CLI) | 5 |
| a non-empty short text | unit | 3, 5 |
| setting again replaces atomically | unit | 2 |
| name checked by the variables' rule | unit | 3 |
| plain variable or secret, never both | unit | 3, 5 |
| show lists secrets by name | unit (CLI) | 5 |
| no write or removal through a link | unit | 2, 3 |
| server sets/removes, refuses as the CLI | unit (server) | 5 |
| deleting removes the data folder; create refuses a left one | unit, integration | 3, 7 |
| agents cannot change projects (secret) | unit (CLI) | 5 |
| GET gives secrets' names | unit (server) | 5 |
| unset removes plain or secret, new text | unit (CLI) | 3, 5 |
| agents of a session in a project get its secrets | unit, integration | 4, 7 |
| kits' checks see the secrets | unit, integration, smoke | 4, 7 |
| one reader; no link, no loose mode | unit | 1 |
| a file not given is named | unit | 1, 4, 6 |
| secrets stay out of LADO's records | integration (canary) | 7 |
| doctor checks secrets folders; override line | unit | 6 |
