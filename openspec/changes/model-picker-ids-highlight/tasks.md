## 1. The face

- [ ] 1.1 UI e2e (`tests/ui/test_models_section.py`, marker `ui`), failing first: in an open
  picker of OpenCode with a saved model of a server and built-in models, the computed
  `font-family` of a built-in row's id, of the saved model's id under its name and of the id in
  the field starts with `"IBM Plex Mono"`, and that of the model's name and of
  `OpenCode's settings` with `Inter`; in Model servers, a server's address in its head too.
  Then the rule `.mono { font-family: var(--mono); }` in `web/src/styles.css` by `code`, with a
  comment (requirement "Model ids are in the mono face").
- [ ] 1.2 Screenshots of the open picker and of Model servers with an open server, attached to
  the run as artifacts; compared with `mockup-model-picker.html` section 1.

## 2. The highlight

- [ ] 2.1 Vitest (`web/src/ModelPicker.test.tsx`), failing first, by the scenarios of "The
  highlight stays on its row": (a) ↓ to a built-in model, the read fails (`problem` set,
  `choices` kept): the active option (`aria-activedescendant`) is that model and Enter picks it;
  (b) Enter on `Read again`, a read starts (`reading`), then fails: the active option is
  `Read again`; (c) the highlight moved, then new `choices`: the active option is the selected
  row; (d) a search still starts at its first row.
- [ ] 2.2 `web/src/ModelPicker.tsx`: the active row kept as its key (`Row.key`), its index
  derived from `rows` at each render (the selected row, else 0, when the key is not among
  them); moves, typing ahead, the pointer and the search set the key; the effect on
  `[open, choices]` sets the selected row's key. The comment above that effect says it.

## 3. Documents and regression

- [ ] 3.1 `docs/design/ui.md`: Look, Fonts: `.mono` is the one rule of the mono face; Model
  servers, the picker: the highlight is a row, not a place, and stays on it when rows come or go
  without a new list.
- [ ] 3.2 CHANGELOG.md, `## 0.46.1 (unreleased)`, Fixed: model ids in the mono face; the
  picker's highlight stays on its model after a failed read (LAD-202).
- [ ] 3.3 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_models_section.py tests/ui/test_settings_pages.py tests/ui/test_launch_model.py
  tests/ui/test_projects_section.py tests/ui/test_project_page.py`; `openspec validate
  model-picker-ids-highlight --strict` and the trial archive of the settings' Checks.
