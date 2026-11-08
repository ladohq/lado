Build on main only after PR #256 (LAD-238) is merged into it: bring `origin/main` into the
branch first. If it is not merged yet, tell the supervisor and wait.

## 1. The core and the API

- [x] 1.1 `src/lado/model_servers.py`: `Probe.cannot()` by D1, with its docstring; the module
  docstring names it beside `refuses_server`. Unit tests: LM Studio with chat completions and
  the Responses API gives Claude Code (`it has no Anthropic Messages API`) and Codex CLI (its
  refusal), in the registry's order; a late Anthropic Messages API gives `its Anthropic
  Messages API did not answer in time` (AC-1, AC-2).
- [x] 1.2 `src/lado/server/models.py`: `CliCannot` and `ProbeInfo.cannot` (D2), docstring
  updated; `server/model_entries.probe_info` fills it. `tests/test_server_model_settings.py`:
  the probe of an open server and the Add form's check answer `cannot` (AC-1).
- [x] 1.3 `make web-types`; commit `web/openapi.json` and `web/src/api.gen.ts`.
- [x] 1.4 `lado model-server probe` and `add` print as before: the existing tests of their
  `not:` line pass unchanged (AC-6).

## 2. The page

- [ ] 2.1 `web/src/ModelSources.tsx`: the list under a server's model by D3-D6 and the mock-up
  `mockup-cli-reasons.html` (variant 1); `would be` asked only for the tickable CLIs; the
  Model id form keeps its columns. `web/src/styles.css`: the muted title of a disabled CLI.
  `web/src/modelFakes.ts`: the LM Studio fixture gets Codex CLI under `cannot`.
- [ ] 2.2 `web/src/ModelSources.test.tsx`: the order, Codex CLI's reason on LM Studio, a
  missing API, `not installed`, the server no installed CLI can use opening its models, and a
  tick and untick of a tickable CLI as before (AC-1 - AC-5). `make web` passes.
- [ ] 2.3 `tests/ui/test_models_section.py` (marker `ui`): an LM Studio fake server, a model
  opened, Codex CLI disabled with its reason (AC-1); screenshots of the open list at 1440
  light and 390 dark attached as run artifacts.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`: the Model servers ticks paragraph (every CLI in LADO's order,
  disabled with `cannot use this server: <why>` or `not installed`; a server no installed CLI
  can use opens its models) and the `Found` paragraph's last sentence ("That CLI has no
  column…") brought in line.
- [ ] 3.2 CHANGELOG.md, under the unreleased heading: a line that Model servers says why an
  agent CLI cannot be ticked for a server's model.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_models_section.py`.
- [ ] 4.2 `openspec validate server-model-cli-reasons --strict`, and the trial archive in a copy
  with `openspec validate --specs --strict`.
