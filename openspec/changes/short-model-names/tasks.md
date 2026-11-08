## 0. The base

- [x] 0.1 PR #256 (LAD-238, `feature/lad-238-settings-pages`) is merged into main: `gh pr view 256
  --json state` says `MERGED`. Until then build nothing and tell the supervisor. Then `git fetch
  origin` and merge `origin/main` into the run's branch; `openspec/changes/archive/*-settings-pages/`
  is there and `openspec/specs/model-settings-page/spec.md` holds `Requirement: Your models fits a
  narrow window`.
- [x] 0.2 The trial archive of the settings' Checks passes for this change (it reports `not found`
  until 0.1 is done).

## 1. The default name (core)

- [ ] 1.1 `tests/test_model_settings.py` (unit): failing tests first, one per scenario of
  model-settings-page's `A default name of a server's model`: the model's id alone on a server
  several CLIs suit; a name held by another CLI's model → ` · <CLI title>`; held by the same CLI's
  model of another server → ` · <server>`; both taken → ` · <server> · <CLI title>`, then ` (2)`;
  an id with its vendor (`qwen/qwen3-coder`) kept whole; an id of 70 characters cut to 64 before
  each suffix; the clash ignoring case (`Qwen3-8B` held) (AC-1, AC-2). Replace the tests of the
  old `<model> · <server>` names.
- [ ] 1.2 `src/lado/model_settings.py`: `default_name` by the rule (design D1, D2); its docstring
  says it. `check_model` and `add_model` unchanged. The tests of 1.1 pass.
- [ ] 1.3 `git grep -n "· LM Studio\|<model> · <server>"` over `tests/` and `web/src/`: every test
  or fake that expects an old default name (the server's `POST /api/models/check` answers, the
  tick's `as <name>` / `would be <name>`) expects the new one.

## 2. The model is not shown twice (web)

- [ ] 2.1 `web/src/ModelPicker.tsx`: a configured model whose `model` equals its `name` ignoring
  case shows no `mp-id` in the field and no `mp-sub` in its row (design D3); the field's title and
  the row's `aria-label` keep the model. Vitest in its test file: the field and the row of a model
  named by its id show it once; one named otherwise shows both (AC-3).
- [ ] 2.2 `web/src/ModelSettings.tsx`: Your models' row leaves `mx-model` out at 900 px and
  narrower when the model is the name, and its `mx-from` then starts the line without ` · `; on a
  wide window the Model column keeps it (design D3). Vitest (AC-4).
- [ ] 2.3 `web/src/Agents.tsx` `ModelFact`: no `<model> · ` after the saved name when they are equal
  ignoring case. Vitest (AC-5).
- [ ] 2.4 `tests/ui/` (marker `ui`): Agent CLIs at 768 px with Kilo CLI's default named by its id
  (the fake server's model `qwen3.8-27b`): the field shows `qwen3.8-27b` once, not cut; Model
  servers at 390 px: its second line is `LM Studio · Kilo CLI · default`; a tick on a server's model
  shows `as <model id>` (AC-1, AC-3, AC-4). Screenshots of both pages at 1440, 768 and 390 px as run
  artifacts.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`: the paragraph of default names (the ticks) states the new rule; Your
  models' narrow line and the picker say the model is left out when it is the name; the agent's
  Model fact likewise.
- [ ] 3.2 `docs/design/modules.md`: `model_settings`' `default_name` line says the new rule.
- [ ] 3.3 CHANGELOG.md under `## 0.45.0 (unreleased)`, Fixed: a model ticked on Model servers is
  named by its id; the server and CLI show in their own columns (AC-6).

## 4. Checks

- [ ] 4.1 `make lint`, `make test` (unit, `-n auto`), `make web`, `uv run pytest -m ui -n auto
  <the changed files of tests/ui/>` pass; counts in the build report.
- [ ] 4.2 `openspec validate short-model-names --strict`, `openspec validate --specs --strict` and
  the trial archive pass; `grep -rn "<model> · <server>" openspec/specs docs` finds none of the old
  rule.
