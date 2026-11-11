Task: LAD-202

## Why

Two defects of the model picker, found in the review of LAD-200 (F22, F24):

- **Model ids are not in the mono face.** The picker marks a built-in model's id, a model's id
  under its name and the id in the field with the class `mono`, as the mock-up of LAD-200 and
  the design ask, but `web/src/styles.css` has no rule `.mono` that sets the face: only
  `.mp-title.mono` (a size), `.mx-l2 .mono` (a size) and three inputs of Projects
  (`font: 13px var(--mono)`). Every other element marked `mono` shows in Inter.
- **The highlight moves to another row after a failed request.** The picker keeps the row the
  keyboard is on (the highlight: what Enter picks) as an index into its rows, and puts it back
  on the selected row only when a list is read (`choices` changes). A request to LADO that
  fails keeps the old list and adds the row `Read again` after the CLI's settings: every row
  below moves down one, the index stays, and the highlight stands on the row above the one the
  human chose. Enter then picks a model the human did not point at.

Options weighed for the face (the human's answer #5794: A):

- Taken (A): one rule `.mono { font-family: var(--mono) }` for the whole UI. It removes the
  cause; every element marked `mono` gets the face it was marked for. Long-term cost: none; a
  new `mono` needs no rule of its own.
- B: a rule inside the picker only. Smallest diff, but leaves the same defect in nine places
  and a second rule to keep in step.

Options weighed for the highlight:

- Taken: the highlight is the row itself (its key), and its index follows from the rows of
  each render. No change of rows can move it to another model.
- Put it back on the selected row at every change of the rows (the effect's dependencies
  gaining `problem` and `reading`): loses the row the human moved to, which F24 asks to keep.
- Move `Read again` below the models: another row's place changes the same way when the page's
  entries stand in for the core's during a read; it only moves the defect.

## What Changes

- `.mono` sets the mono face (`--mono`) in the whole UI; its size stays the element's. Model
  ids in the picker (a built-in model's row, a model's id under its name, the id in the field)
  and the elements marked `mono` elsewhere show in IBM Plex Mono: in Model servers a server's
  address in its source's head, the model ids of a server's list, `Agent CLIs that run
  <model>`, the field `Model id`; in Agent CLIs the field of `Other name…`; in Projects the
  inputs marked `mono` that no rule covered (those of `.add-repo`, `.repo-delete` and
  `.project-new` already had the face and keep it).
- The picker's highlight stays on the same row when its rows change without a new list: a
  failed read that adds `Read again`, a read that starts and takes it away. A row that is gone
  for a while leaves the highlight on the selected row (else the first) and gets it back when
  it returns; a list read anew puts it on the selected row, as before.
- A patch (0.46.1): fixes only, no MCP tool, CLI or schema change.

## Scope

- `web/src/styles.css` (the rule `.mono`), `web/src/ModelPicker.tsx` (the highlight by key).
- Tests: vitest `web/src/ModelPicker.test.tsx`; UI e2e `tests/ui/test_models_section.py`.
- `docs/design/ui.md` (Look: the mono face; Model servers, the picker: the highlight),
  CHANGELOG.md under `## 0.46.1 (unreleased)`.

## Out of scope

- The size of mono text: each place keeps its own (`.mp-title.mono` 13 px, `.mp-id`, `.mp-sub`
  12 px); the defect is the face only.
- Model names (`Рабочая Qwen`), the CLI's settings row, `Read again` and `Other name…` stay in
  Inter: they are words, not ids.
- The original mock-up `ui-design/model-picker` of LAD-200: not in this LADO (the human did not
  attach it, #5794); the check is against the spec, `docs/design/ui.md` and
  `mockup-model-picker.html` of this run.
