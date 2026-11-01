# The agent's model is visible Implementation Plan

**Goal:** every agent's model and effort, each with its source, are kept in `lado.db` and
shown by `list_agents`, the API, the agent's page, the Team tooltip and `lado ls`; the
model comes from the events the CLIs already send and, for Codex, from the carried config.

**Architecture:** six columns of `agents` (schema 36); neutral `Event.model`/`effort` and
`Launch.model`/`effort` (`base.Choice`); each provider fills what its CLI gives;
`hooks.handle` records a reported model with `state.report_model`; `runtime` records a
launch's choice with `state.set_model`; the words of a source in `state.source_words`.

**Tech Stack:** Python 3.10+ (stdlib, FastAPI, pydantic), pytest with the fake tmux and
the fake agent, Node's test runner for the plugin, React + TypeScript (vitest), Playwright
(`pytest -m ui`).

**Spec:** `openspec/changes/agent-model-visible/` (proposal, delta `agent-model`,
design.md D1-D9) and `docs/superpowers/specs/2026-11-01-agent-model-visible-design.md`.
Mockup: run artifact `mockup-agent-model.html` (option A).

## Global Constraints

- Source tokens: `cli`, `cli-config`. Words: `CLI default`, `your <CLI title> config`
  (`your Codex config`), with `, <detail>` when there is a detail; detail of a profile:
  `profile <name>`.
- Head line: `{role} · {provider} · {model name or "CLI default model"}`.
- Facts: `Model`, `Effort`, first in `agent-facts`; a name as `<code>` then a muted
  ` · <words>`; no name: the muted words only.
- `lado ls`: `{model or "-":<18}` after the time, before the branch.
- `SCHEMA_VERSION = 36`, `MIGRATIONS[35]`; `tests/agent_helpers.previous_schema` undoes it.
- No provider name above `providers/` except through `Provider.title`; no terminal
  reading; no new hook or event of any CLI; no network request.
- CHANGELOG.md: one line under `## 0.45.0 (unreleased)`, `### Added`: the epic ships in
  0.45.0, and 0.44.0 is released from main without it. When the target branch has no
  `## 0.45.0 (unreleased)` heading, add it on top, above the 0.44.0 section, which stays
  as it is there (main's release sets its date; the merge of main brings it).
- Unit suites with `-n auto`; integration and UI files with their markers; single node ids
  with `-n0`.

## Review Focus

- Every Codex hook names the model: no `agents` update and no journal row when nothing
  changed (Task 2 test `test_a_repeated_report_writes_nothing`).
- A reported name that differs from a `cli-config` choice turns the source to `cli` and
  clears the detail; the effort's pair stays (Task 2 test
  `test_a_different_model_is_the_clis`).
- The plugin never fails `chat.message` when `output.message` or its `model` is missing
  (Task 4 node test `chat.message without a model`).
- The migration from schema 35 and an older LADO's refusal of schema 36 (Task 1).
- A Codex launch whose profile names no model takes the top level's, with no detail
  (Task 3 test `test_carried_model_falls_back_to_the_top_level`).

---

### Task 1: The columns and their migration (D1, D2)

**Files:** `src/lado/state.py`, `tests/agent_helpers.py`, `tests/test_state.py`.

- [ ] Failing tests in `tests/test_state.py`:
  `test_a_new_agent_has_the_clis_default_model` (no names, both sources `cli`);
  `test_the_migration_gives_the_agents_there_the_clis_default` (`schema_before(36)`,
  `migrate()` gives `(35, 36)`, the old agent reads `cli`/None);
  `test_set_model_writes_the_launchs_choice`; `test_source_words` (`cli`, `cli-config`
  with and without a detail, an unknown token shown as itself). Update
  `test_...backup...` at the line that asserts `"window_at" not in columns` to the new
  column `model`.
- [ ] `uv run pytest -n0 tests/test_state.py -k "model or migration or words" -x` → FAIL.
- [ ] Implement: `AGENTS_MODEL = [six ALTER TABLE ...]`, `SCHEMA += ...`,
  `MIGRATIONS[35]`, `SCHEMA_VERSION = 36`; `Agent` fields `model`, `model_source="cli"`,
  `model_detail`, `effort`, `effort_source="cli"`, `effort_detail`; the row readers;
  `CLI_DEFAULT`, `CLI_CONFIG`, `MODEL_SOURCES`, `source_words`; `set_model(session, name,
  model: Choice | None, effort: Choice | None)` (takes plain name/source/detail triples,
  no import of providers). `previous_schema` undoes 36.
- [ ] Run the tests → PASS; `uv run pytest -n auto tests/test_state.py tests/test_cli.py
  -k "schema or migrat"` → PASS (an older LADO's `SchemaError` unchanged).
- [ ] Commit `An agent has a model and an effort with their sources in lado.db (LAD-169)`.

### Task 2: Events carry the model; hooks record it (D4, D5)

**Files:** `src/lado/providers/base.py`, `src/lado/state.py` (`report_model`),
`src/lado/hooks.py`, `tests/test_state.py`, `tests/test_read_only_hooks.py` or a new
`tests/test_hooks_model.py`.

- [ ] Failing tests: `test_a_reported_model_is_recorded` (from `cli`, no name → name);
  `test_a_repeated_report_writes_nothing` (count of `changes` rows before and after);
  `test_a_different_model_is_the_clis` (`cli-config` + `profile work` → `cli`, no detail,
  effort untouched); `test_an_event_without_a_model_changes_nothing`;
  `test_handle_records_the_model_before_the_status` (a SESSION_START with `model`).
- [ ] Run → FAIL.
- [ ] Implement `Event.model`, `Event.effort`; `state.report_model` in one transaction,
  writing only changed columns; `hooks.handle` calls it after `state.seen` when either is
  set.
- [ ] Run → PASS. Commit `Hooks record the model an agent's CLI names (LAD-169)`.

### Task 3: Providers read the model (D3, D4)

**Files:** `src/lado/providers/base.py` (`Choice`, `Launch.model`/`effort`),
`src/lado/providers/codex.py`, `src/lado/providers/claude.py`,
`src/lado/providers/opencode_family.py`, `src/lado/runtime.py`, `tests/test_codex.py`,
`tests/test_providers.py`, `tests/test_runtime.py`.

- [ ] Failing tests: Codex `parse_event` gives `model` for SessionStart, UserPromptSubmit,
  Stop, Interrupt, PermissionRequest, PostToolUse; a non-string `model` gives "";
  Claude `parse_event` gives `model` for SessionStart (startup and a switch's source) and
  none for Stop; OpenCode-family `parse_event("chat.message", {"prompt", "model":
  "anthropic/claude-sonnet-5-5", "variant": "high"})` gives both; Codex `launch`:
  `test_carried_model_of_the_chosen_profile` (detail `profile work`),
  `test_carried_model_falls_back_to_the_top_level` (no detail),
  `test_no_carried_model_leaves_none`; `tests/test_runtime.py`:
  `test_spawn_records_the_launchs_model` and the same for the supervisor's start.
- [ ] Run → FAIL.
- [ ] Implement: `base.Choice`; Codex `_carried(config, key)` sharing `_model_provider`'s
  rule, filled into `Launch` from what `_keep` kept; each `parse_event`; `runtime` calls
  `state.set_model` after `_launch_command` for the supervisor and workers.
- [ ] Run → PASS; `uv run pytest -n auto tests/test_codex.py tests/test_providers.py
  tests/test_runtime.py`. Commit `Codex, Claude Code and the OpenCode family tell LADO
  their agents' model (LAD-169)`.

### Task 4: The plugin sends the model (D4)

**Files:** `src/lado/providers/opencode_plugin.js`, `tests/js/opencode_plugin.test.mjs`.

- [ ] Failing node tests: `chat.message` with `output.message.model = {providerID:
  "anthropic", modelID: "claude-sonnet-5-5", variant: "high"}` posts `model:
  "anthropic/claude-sonnet-5-5"`, `variant: "high"`; `chat.message without a model`
  posts no `model` and does not throw.
- [ ] `make test-js` → FAIL; implement; `make test-js` → PASS. Commit `The OpenCode
  family's plugin reports the model of each prompt (LAD-169)`.

### Task 5: list_agents and the API (D6, D7)

**Files:** `src/lado/mcp_server.py`, `src/lado/server/models.py`,
`tests/test_mcp_server.py`, `tests/test_server_agents.py`, `web/openapi.json`,
`web/src/api.gen.ts`.

- [ ] Failing tests: `list_agents` entries have the six fields;
  `GET /api/sessions/{s}/agents` gives `model`/`effort` as `{name, source, detail,
  words}` with `your Codex config, profile work` and `CLI default`; the feed's agent item
  has the same shape.
- [ ] Implement `ModelInfo`, `agent_info`, `list_agents`; `make web-types`; `make web`.
- [ ] Commit `list_agents and the API give each agent's model and effort (LAD-169)`.

### Task 6: Integration with the fake agent

**Files:** `tests/integration/fake_agent.py`, `tests/integration/fake_provider.py`,
`tests/integration/test_agents.py`.

- [ ] Test `test_the_model_a_cli_names_reaches_lado_db_list_agents_and_the_api`: a session
  with the fake agent started with `FAKE_AGENT_MODEL=fake-large`, `FAKE_AGENT_EFFORT=high`;
  after its session start, `state.get_agent` has them with source `cli`, `lado mcp`'s
  `list_agents` and `models.agent_info` show them.
- [ ] Implement the fake agent's payload fields and the fake provider's `parse_event`.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_agents.py
  tests/integration/test_fake_agent.py` → PASS. Commit `The fake agent reports a model
  (LAD-169)`.

### Task 7: The UI and lado ls (D8, D9)

**Files:** `web/src/Agents.tsx`, `web/src/Team.tsx`, `web/src/Agents.test.tsx`,
`web/src/Team.test.tsx`, `src/lado/cli.py`, `tests/test_cli.py`,
`tests/ui/test_agents_tab.py`.

- [ ] Failing vitest: the head line with a model and with none; Model/Effort facts with a
  name and with words only; the tooltip with and without a model. Failing
  `tests/test_cli.py`: `lado ls` prints the model and `-`.
- [ ] Implement to the mockup's option A; `make web`.
- [ ] UI e2e in `tests/ui/test_agents_tab.py`: an agent written with a `cli-config` model
  and one with none; the page shows both cases; screenshots of each to
  `<temp>/lado-ui-shots/`, attached as run artifacts.
- [ ] `uv run pytest -m ui tests/ui/test_agents_tab.py` → PASS. Commit `The agent's page,
  the Team tooltip and lado ls show its model (LAD-169)`.

### Task 8: Docs and regression

- [ ] `docs/design/agents.md`: per CLI, which event names the model (the facts of the
  proposal's Why) and how a launch's choice is recorded; `docs/design/ui.md`: the agent's
  page head line and facts, the tooltip; `docs/cli.md`: `lado ls`'s model column;
  `docs/design/modules.md` where `state.py`/`hooks.py`/providers' lines change; CHANGELOG
  line under `## 0.45.0 (unreleased)`, `### Added` (heading added when missing); BACKLOG.md "Choose the model per
  agent" replaced by a pointer to LAD-154.
- [ ] Regression: `make lint`, `make test`, `make web`, `make test-js`, `uv run pytest -m
  integration -n auto tests/integration/test_agents.py tests/integration/test_fake_agent.py`,
  `uv run pytest -m ui tests/ui/test_agents_tab.py`, `openspec validate --specs --strict`,
  `openspec validate agent-model-visible --strict`; CI green (the smoke of each provider
  runs: the change touches `providers/`).
