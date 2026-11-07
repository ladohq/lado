# One model per session Implementation Plan

**Goal:** `lado start --model` and the launch window's Model field choose a model for the
session; it is kept as a power table, checked against the CLI's own list before the start,
passed to every agent of the session's CLI by the CLI's own way and shown on the agent's
page with the source `session`; an agent of another CLI keeps its default, loudly.

**Architecture:** `sessions.power` (JSON, schema 37) read into `state.PowerTable`;
`runtime.session_model` decides which agent gets the `normal` row and puts it into
`AgentSpec.model`; each provider applies it and returns `Choice(model, "session")`;
`model_check.check` over `Provider.model_list` gives one verdict for the CLI, the API and
the UI; `state.report_model` keeps the source for an alias's full name
(`Provider.same_model`).

**Tech Stack:** Python 3.10+ (stdlib, FastAPI, pydantic), pytest with the fake tmux and
the fake agent, React + TypeScript (vitest), Playwright (`pytest -m ui`), the smoke
scenario with the real CLIs (CI).

**Spec:** `openspec/changes/session-model/` (proposal, deltas `session-model` and
`agent-model`, design.md D1-D12) and
`docs/superpowers/specs/2026-11-02-session-model-design.md`. Mockup: run artifact
`mockup-session-model.html`.

## Global Constraints

- Levels `light`, `normal`, `heavy`; every agent takes `normal`. A row is `{"cli",
  "model"}`; no effort key.
- Source token `session`, words `chosen for the session`. Another CLI: source `cli`,
  detail `the session's model <model> is for <CLI title>`.
- Texts (exact): refusal `<model> is not in <title>'s list of models; <command> prints
  the list`; warning `<why>: LADO cannot check <model>; a wrong name stops its agents at
  their first turn`; ok `in <title>'s list of models` / `an alias of <title>`; default
  `empty: <title>'s default model; type or pick one of its models`; spawn warning
  `<agent> runs on <title>'s default model: the session's model <model> is for <row
  title>`; resume change `model: <cli> <model> -> CLI default`.
- `SCHEMA_VERSION = 37`, `MIGRATIONS[36]`; `previous_schema` undoes it; compared with
  `origin/main` at each merge of the base (D12).
- No network request by LADO for a list; no terminal reading; the user's CLI configs are
  read only. No provider name above `providers/` except through `Provider.title`.
- CHANGELOG.md: one line under the existing `## 0.45.0 (unreleased)`, `### Added`.
- Unit suites with `-n auto`; integration and UI files with their markers; single node
  ids with `-n0`.

## Review Focus

- A refused model stores no session and starts no window (Task 5
  `test_a_refused_model_stores_nothing`).
- Codex: the model goes into the carried profile too, the user's file is untouched (Task
  3 `test_session_model_wins_over_the_carried_profile`).
- `report_model`: an alias's full name keeps `session`; another name gives `cli`; a first
  name keeps the other CLI's note (Task 2).
- A resume with another provider drops the table and says so (Task 5).
- The UI never lets Start run on a refused model, nor while the check is under way (Task 8).

---

### Task 1: The power table and its migration (D1, D2)

**Files:** `src/lado/state.py`, `tests/agent_helpers.py`, `tests/test_state.py`.

- [ ] Failing tests: `test_power_table_round_trips` (`single("codex", "gpt-5.6-sol")`
  → JSON → equal, three rows, `row()` is `normal`); `test_a_session_keeps_its_power`
  (`add_session` / `get_session`, and `None`); `test_the_migration_gives_sessions_no_power`
  (`schema_before(37)`, `migrate()` gives `(36, 37)`); `test_source_words` gains
  `session` → `chosen for the session`; `Choice(None, "cli", "…")` accepted by `set_model`.
- [ ] Implement D1, D2. Run → PASS; `uv run pytest -n auto tests/test_state.py
  tests/test_cli.py -k "schema or migrat"` (an older LADO's refusal unchanged).
- [ ] Commit `A session keeps its model as a power table (LAD-174)`.

### Task 2: Reported models keep the session's source (D6)

**Files:** `src/lado/state.py`, `src/lado/providers/base.py`, `src/lado/providers/claude.py`,
`src/lado/hooks.py`, `tests/test_state.py`, `tests/test_providers.py`.

- [ ] Failing tests: `test_an_alias_s_full_name_keeps_the_source` (`opus`/`session` +
  `claude-opus-5-5` → name replaced, `session`); `test_another_model_than_the_alias_is_the_clis`;
  `test_a_first_name_keeps_the_note` (None/`cli`/detail + name → detail kept); the
  agent-model tests stay green; Claude `same_model` table (`opus`, `sonnet[1m]`,
  `default`, a non-alias).
- [ ] Implement `Provider.same_model` (default equality), Claude's, `report_model(...,
  same)`, `hooks.handle` passing the agent's provider's. Run → PASS. Commit
  `A CLI's full name of the chosen alias keeps the session's source (LAD-174)`.

### Task 3: Each provider applies the model (D3, D4, D5)

**Files:** `src/lado/providers/base.py` (`AgentSpec.model`), `claude.py`, `codex.py`,
`opencode_family.py`, `tests/integration/fake_provider.py`, `src/lado/runtime.py`
(`session_model`, `_spec`, the note), `tests/test_providers.py`, `tests/test_codex.py`,
`tests/test_runtime.py`.

- [ ] Failing tests: Claude argv has `--model opus` with `spec.model`, none without;
  `test_session_model_wins_over_the_carried_profile` (Codex: top level and
  `[profiles.work]`, `Launch.model` `session`, effort `cli-config`, user file bytes
  unchanged); Codex without a profile (top level only); OpenCode and Kilo config content
  `model`; the fake provider's `FAKE_AGENT_MODEL`; `test_runtime`:
  `test_the_supervisor_starts_on_the_session_model`,
  `test_a_worker_of_another_cli_gets_the_note` (warning text, `Choice(None, cli, note)`,
  no `--model`), `test_no_table_passes_no_model`.
- [ ] Implement. Run → PASS. Commit `Every agent of the session's CLI starts on its model (LAD-174)`.

### Task 4: The check (D7)

**Files:** `src/lado/model_check.py` (new), `src/lado/providers/*.py` (`model_list`),
`tests/test_model_check.py` (new), `tests/test_providers.py`, `tests/test_codex.py`.

- [ ] Failing tests: the four verdicts and their exact texts; Claude's aliases (each with
  `[1m]`) and no list; Codex from a recorded `codex debug models --bundled` JSON plus a
  `models_cache.json`, the union; Codex with `model_provider = "ollama"` → no list with
  why; Codex's command failing → no list; OpenCode/Kilo from recorded `models` output;
  a list command over `MODEL_LIST_TIMEOUT` → no list (the runner faked); the fake
  provider's `FAKE_AGENT_MODELS`. Check by hand the Claude aliases against `claude --help`
  of the installed version and note the version in a comment.
- [ ] Implement. Run → PASS. Commit `A model is checked against its CLI's own list (LAD-174)`.

### Task 5: Start, resume and the CLI (D8, D9)

**Files:** `src/lado/runtime.py`, `src/lado/cli.py`, `tests/test_runtime.py`,
`tests/test_cli.py`.

- [ ] Failing tests: `test_a_refused_model_stores_nothing` (LadoError text, no session,
  no tmux window); `test_a_warned_model_starts_with_the_warning` (started.warnings,
  loop.log); `test_a_resume_keeps_the_model`; `test_an_empty_model_drops_it` (change
  line); `test_another_provider_drops_the_model` (change line); `lado start --model`
  passes through, `--help` names it.
- [ ] Implement. Run → PASS. Commit `lado start --model chooses the session's model (LAD-174)`.

### Task 6: The API (D10)

**Files:** `src/lado/server/models.py`, `src/lado/server/app.py`,
`src/lado/server/launch.py`, `tests/test_server_launch.py`,
`tests/test_server_providers.py`, `web/openapi.json`, `web/src/api.gen.ts`.

- [ ] Failing tests: `POST /api/sessions` with `model` (stored; refused → 4xx with the
  text); `POST /api/sessions/{name}/resume` with `model` None / "" / a name;
  `SessionInfo.model`; `GET /api/providers/{name}/models?model=` (each verdict, the
  60 s cache: the list command runs once for two calls).
- [ ] Implement; `make web-types`. Run → PASS; `make web`. Commit
  `The API takes the session's model and checks it (LAD-174)`.

### Task 7: Integration with the fake agent

**Files:** `tests/integration/test_session_start.py` (or a new
`tests/integration/test_session_model.py`), `tests/integration/fake_provider.py`.

- [ ] Tests: a session started with `--model fake-large` (in `FAKE_AGENT_MODELS`) → the
  fake agent reports `fake-large`, `lado.db` and `list_agents` give `session`, the API's
  `model.words` `chosen for the session`; `--model nope` refused, no session; a worker
  spawned with another provider through `lado mcp` → the warning in the tool's result
  and the note on the agent.
- [ ] `uv run pytest -m integration -n auto tests/integration/<files>` → PASS. Commit
  `Integration: the session's model reaches the agent (LAD-174)`.

### Task 8: The launch window (D11)

**Files:** `web/src/Launch.tsx`, `web/src/Launch.test.tsx`, `tests/ui/test_launch.py`,
`tests/ui/test_agents_tab.py`.

- [ ] Vitest: the field before Switch off; suggestions; each note; Start off while
  refused or checking; the folded summary; provider change empties; Resume fills from
  `SessionInfo.model` and sends `model` only when changed. The Advanced summary test at
  `Launch.test.tsx` (the row list) gets the new text.
- [ ] UI e2e: type a refused and an accepted model with the fake provider's list, start,
  and the agent's page reads `fake-large · chosen for the session`; screenshots of the
  field's four notes and the page as run artifacts.
- [ ] `make web`; `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_agents_tab.py`
  → PASS. Commit `The launch window chooses the session's model (LAD-174)`.

### Task 9: Smoke per provider

**Files:** `tests/smoke/test_smoke.py`, `tests/smoke/conftest.py`.

- [ ] A smoke test per provider: a session with `--model <a model the endpoint serves or
  an alias>` → Claude's process argv has `--model`, Codex's agent config.toml has
  `model`, OpenCode's/Kilo's config content has it, and where the fake endpoint records
  requests, the request names it. Written, run in CI (`make test-smoke` needs the CLIs).
- [ ] Commit `Smoke: the session's model reaches each real CLI (LAD-174)`.

### Task 10: Docs and the regression run

- [ ] `docs/cli.md` (`lado start --model`, resume rules, the check), `docs/design/ui.md`
  (New session's and Resume's Advanced: the Model field), `docs/design/agents.md` (the
  model a launch passes, the source `session`, another CLI), `docs/design/modules.md`
  (`model_check.py`, the table in `state.py`), CHANGELOG line under `## 0.45.0
  (unreleased)` (Added).
- [ ] Regression: `make lint`, `make test`, `make web`, the changed integration and UI
  files with their markers, `openspec validate session-model --strict`, `openspec
  validate --specs --strict`; CI green (smoke included). Commit `Docs and changelog of the
  session's model (LAD-174)`.
