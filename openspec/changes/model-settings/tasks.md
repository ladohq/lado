The plan with each task's tests: `docs/superpowers/plans/2026-11-02-model-settings.md`.

## 1. Store

- [ ] 1.1 `state.py`: the tables `model_servers` and `models`, schema 38 and
  `MIGRATIONS[37]`, the dataclasses and their reads and writes, `NameTaken` (D1);
  `tests/agent_helpers.schema_before` undoes step 37. Check: `tests/test_state.py`.

## 2. Rules

- [ ] 2.1 `model_servers.probe(…, command=…)` in the asks-for-a-key line and the container's
  hint (D5); `plain_http_warning` (D6); `model_check.verdict(…, whose=…)` (D8). Check:
  `tests/test_model_servers.py`, `tests/test_model_check.py`.
- [ ] 2.2 `project_secrets.write_at` / `remove_at` public, callers unchanged in behaviour;
  `model_settings.py`: names, servers, the key file, `--replace`, removal and its refusal
  (D2, D3, D4, D7). Check: `tests/test_model_settings.py`, `tests/test_project_secrets_store.py`.
- [ ] 2.3 `model_settings.add_model` / `remove_model`: the checks in D8's order. Check:
  `tests/test_model_settings.py`.

## 3. Commands and doctor

- [ ] 3.1 `cli.py`: `lado model-server add|list|remove`, `lado model add|list|remove`, the
  key read as the probe's, `NOT_MIGRATING` by subcommand (D10). Check:
  `tests/test_cli_model_settings.py`, `tests/test_cli_model_server.py`.
- [ ] 3.2 `doctor.py`: the `Model servers` line (D9). Check: `tests/test_doctor.py`.

## 4. Integration

- [ ] 4.1 `tests/integration/test_model_settings.py`: add, list, remove against the fake
  server in its own process; the key canary; argv refusal; does not answer; the container's
  hint. Check: `uv run pytest -m integration -n auto tests/integration/test_model_settings.py`.

## 5. Docs and regression

- [ ] 5.1 `docs/cli.md`, `docs/design/modules.md`, AGENTS.md's Layout line, CHANGELOG's line
  under `## 0.45.0 (unreleased)`, `### New`. Check: `tests/test_agents_md.py`, reading.
- [ ] 5.2 Regression and the trial archive: `make lint`, `make test`, the integration files
  of the plan's Task 8 with their marker; `openspec validate model-settings --strict`,
  `openspec validate --specs --strict`; in a copy of `openspec/` outside the tree
  `openspec archive model-settings --yes` and `openspec validate --specs --strict`, the
  result in the pull request's description. Check: the commands' exit codes.
