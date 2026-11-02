# Models in settings: Implementation Plan

**Goal:** the human saves model servers (name, address, key) and configured models (name,
CLI, the CLI's model, an optional server) from the CLI, checked on adding, kept in
`lado.db` with each key in a file of its own; `lado doctor` checks the servers; no session
uses them yet.

**Architecture:** `state.py` adds two tables (schema 38) and their reads and writes;
`model_settings.py` holds the rules (names, the key file through `project_secrets`'
writer, the checks on adding, doctor's lines); `model_servers.py` names the running
command in its messages and gets the plain-http rule; `model_check.verdict` takes whose
list it is; `cli.py` adds `lado model-server add|list|remove` and `lado model
add|list|remove`; `doctor.py` adds the `Model servers` line.

**Tech Stack:** Python 3.10+ standard library (`sqlite3`, `ipaddress`, `threading`,
`os` with `dir_fd`), pytest (unit with `-n auto`, integration with the marker),
`tests/fake_model_server.py`.

**Spec:** `openspec/changes/model-settings/` (proposal, deltas `model-servers` and
`configured-models`, design.md D1-D11) and
`docs/superpowers/specs/2026-11-02-model-settings-design.md`.

## Global Constraints

- No new dependency; no API, UI or `web/` change; no provider change; nothing above
  `providers/` names a provider.
- Schema 37 → 38: `SCHEMA_VERSION = 38`, `MIGRATIONS[37] = [MODEL_SERVERS_TABLE,
  MODELS_TABLE]`, both also in `SCHEMA`; `tests/agent_helpers.schema_before` asserts and
  undoes step 37.
- The key: never in argv, an exception's text, output, `lado.db`, the error journal, any
  file of `LADO_HOME` but `model-servers/<id>/key`, or a secrets folder.
- Texts exact as in the deltas (`Saved model server "<name>".`, `Replaced model server
  "<name>".`, `Removed model server "<name>".`, the used-by refusal, the name-taken
  refusals, the empty lists' lines, the plain-http warning, `Saved model "<name>": …`,
  `Removed model "<name>".`, `<server> does not suit <title>: it has no <API>; it suits …`,
  `LADO cannot check <model>`).
- CHANGELOG.md: one line under `## 0.45.0 (unreleased)`, `### New`.
- No step numbers of the epic, no link to `docs/epics/` in code, docs or specs.
- Unit suites with `-n auto`; integration files with `-m integration`; single node ids
  with `-n0`.

## Review Focus

- The key canary (Task 7) and the argv refusal without echo (Task 5).
- The key file: 600/700 whatever the umask, rename, a link refused, removed with the
  server (Task 3).
- The foreign key and the used-by refusal (Tasks 1, 3).
- `probe` still never migrates or writes `lado.db` (Task 5).
- `doctor` never fails its exit on a server and never migrates (Task 6).

---

### Task 1: The store (D1)

**Files:** `src/lado/state.py`, `tests/agent_helpers.py`, `tests/test_state.py`.

- Tables, migration, `ModelServer(id, name, address, kind, apis: tuple[str, ...],
  created_at)`, `ConfiguredModel(name, cli, model, server: str | None, created_at)`;
  `add_model_server`, `replace_model_server(id, address, kind, apis)`, `model_servers()`,
  `model_server(name)` (by `casefold`), `remove_model_server(id)`, `add_model`, `models()`,
  `model(name)`, `remove_model(name)`, `models_on(server_id)`. A taken name raises
  `state.NameTaken(existing_name)` from the `UNIQUE` / `PRIMARY KEY` violation.

Tests:
- `test_migration_37_to_38_adds_empty_tables` (from `previous_schema`; sessions, agents
  unchanged).
- `test_model_server_name_taken_ignoring_case` (`LM Studio дома` / `lm studio ДОМА`).
- `test_model_name_taken_ignoring_case` (`Быстрая` / `быстрая`).
- `test_model_refers_to_saved_server_only` (foreign key).
- `test_remove_server_with_models_refused_by_foreign_key`.
- `test_replace_keeps_models_reference`.
- `test_lists_sorted_ignoring_case`.

### Task 2: The probe's command and the plain-http rule (D5, D6)

**Files:** `src/lado/model_servers.py`, `src/lado/model_check.py`,
`tests/test_model_servers.py`, `tests/test_model_check.py`.

- `probe(text, key=None, command="lado model-server probe")`; the asks-for-a-key line and
  `_container_hint` use it. `plain_http_warning(root, key) -> str | None`.
- `model_check.verdict(provider, model, listed, whose=None)`.

Tests:
- `test_asks_for_key_names_the_command` (probe and `lado model-server add "work"`).
- `test_container_hint_names_the_command` (with `--replace`).
- `test_plain_http_warning_public_host` (`llm.example.com`, a public IP).
- `test_plain_http_no_warning_local` (`localhost`, `127.0.0.1`, `::1`, `10.0.0.5`,
  `192.168.1.10`, `172.16.0.1`, `169.254.1.1`, `fd00::1`, `fe80::1`,
  `host.docker.internal`).
- `test_plain_http_no_warning_without_key_or_https`.
- `test_verdict_names_whose_list`.
- Existing probe tests stay green (the default command).

### Task 3: Servers and their keys (D2, D3, D4, D7)

**Files:** `src/lado/project_secrets.py`, `src/lado/model_settings.py` (new),
`tests/test_model_settings.py` (new), `tests/test_project_secrets_store.py`.

- `project_secrets.write_at` / `remove_at` public (old callers moved, behaviour unchanged).
- `model_settings.check_name`, `add_server(name, address, key, replace=False) ->
  (Probe, replaced: bool)`, `server_key(server)`, `remove_server(name)`, `Refused`.

Tests:
- `test_check_name_rules` (empty, 65 chars, a line break, a hidden character, spaces at
  the ends refused; `LM Studio дома`, 64 chars kept).
- `test_add_server_saves_address_kind_apis_not_models`.
- `test_add_server_refuses_without_writing` (does not answer, 401, unknown; no row, no
  folder).
- `test_add_server_name_taken_sends_no_request` (fake server's record empty).
- `test_key_file_modes_under_umask_077_and_000` (700/600).
- `test_key_file_refuses_link_on_the_way` (`model-servers` a link).
- `test_replace_with_new_key_rewrites_file` / `test_replace_without_key_keeps_and_sends_old`.
- `test_replace_failed_probe_changes_nothing`.
- `test_replace_unknown_name_refused`.
- `test_remove_server_removes_folder`.
- `test_remove_server_used_by_models_refused_naming_them`.
- `test_failed_insert_removes_written_key` (a concurrent `NameTaken`).
- `tests/test_project_secrets_store.py` suite unchanged and green.

### Task 4: Models (D8)

**Files:** `src/lado/model_settings.py`, `tests/test_model_settings.py`.

- `add_model(name, cli, model, server_name, env) -> (Verdict, warnings)`, `remove_model`.

Tests:
- `test_add_model_alias_saved` (fake provider with aliases).
- `test_add_model_not_in_cli_list_refused`.
- `test_add_model_no_cli_list_saved_with_warning`.
- `test_add_model_unknown_cli_refused_naming_clis`.
- `test_add_model_unknown_server_refused_without_request`.
- `test_add_model_server_does_not_answer_refused`.
- `test_add_model_server_does_not_suit_cli_refused` (Responses API missing for Codex;
  `it suits no CLI`).
- `test_add_model_server_list_checks` (in list saved; not in list refused; no list saved
  with warning).
- `test_add_model_claude_on_anthropic_server_saved`.
- `test_add_model_strips_spaces`.
- `test_remove_model_keeps_server`.

### Task 5: The commands (D10)

**Files:** `src/lado/cli.py`, `tests/test_cli_model_settings.py` (new),
`tests/test_cli_model_server.py`.

- `lado model-server add|list|remove`, `lado model add|list|remove`, `lado model` alone
  prints help; `NOT_MIGRATING` by (command, sub): `probe` stays out.

Tests:
- `test_model_server_add_prints_probe_lines_and_saved`.
- `test_model_server_add_key_in_argv_refused_unechoed` (`--key s3cr3t`, `--key -s3cr3t`,
  `--help=s3cr3t`, a word more; nothing saved, no request).
- `test_model_server_add_empty_key_refused`.
- `test_model_server_add_plain_http_warning_on_stderr`.
- `test_model_server_add_bad_address_exit_2`.
- `test_model_server_list_table_and_no_request` / `test_model_server_list_empty_line`.
- `test_model_server_remove_used_refused` / `test_model_server_remove_done`.
- `test_model_add_outputs` (alias, server list, warning on stderr).
- `test_model_list_table` / `test_model_list_empty_line`.
- `test_model_remove_unknown_exit_1`.
- `test_probe_does_not_migrate` (schema 37 stays) and `test_add_migrates`.
- `test_lado_start_reads_no_entry` (start without `--model` with entries saved: power
  None).

### Task 6: doctor (D9)

**Files:** `src/lado/doctor.py`, `tests/test_doctor.py`.

Tests:
- `test_no_servers_no_line`.
- `test_servers_ok_line` / `test_server_not_answering_warns_exit_unchanged`.
- `test_key_file_loose_mode_warns`.
- `test_left_over_folder_warns_without_servers`.
- `test_other_schema_says_not_checked_and_does_not_migrate`.
- `test_probes_run_at_once` (two hanging servers: the line within about one probe's time).

### Task 7: Integration and the key canary

**Files:** `tests/integration/test_model_settings.py` (new).

Tests (real `lado` processes, `tests/fake_model_server.py` in its own process, a temp
`LADO_HOME`):
- `test_add_list_remove_server_and_model` (add server with a piped key, add a model on it,
  lists, the used-by refusal, remove both).
- `test_key_canary` (a unique key: in no stdout/stderr, `lado.db` bytes, the error journal,
  any file of `LADO_HOME` but `model-servers/<id>/key`, any secrets folder; the file 600;
  gone after remove).
- `test_key_in_argv_refused_unechoed`.
- `test_address_does_not_answer_refused`.
- `test_container_hint_on_add` (`LADO_CONTAINER=1`).

Run: `uv run pytest -m integration -n auto tests/integration/test_model_settings.py
tests/integration/test_model_server_probe.py`.

### Task 8: Docs and regression

**Files:** `docs/cli.md` (the six commands, their output and refusals, the key, `--` before
a dashed name), `docs/design/modules.md` (`model_settings.py`; `state.py`'s two tables;
`model_servers.py`'s command and warning; `project_secrets.py`'s shared writer; `doctor.py`'s
line), AGENTS.md's Layout line (`model_settings.py` saved model servers and models),
CHANGELOG.md (`### New`: **Save model servers and models under names.**).

Regression: `make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_model_settings.py tests/integration/test_model_server_probe.py
tests/integration/test_session_model.py tests/integration/test_uninstall_process.py`;
`openspec validate model-settings --strict`; `openspec validate --specs --strict`; the
trial archive in a copy of `openspec/` outside the tree (`openspec archive model-settings
--yes`, then `openspec validate --specs --strict`), the result in the pull request's
description; `tests/test_agents_md.py`.
