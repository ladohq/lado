Task: LAD-242

## Why

Symptom: on Settings → Agent CLIs (LAD-238, PR #256), a second after the human picks a default
model in a CLI's row (`Рабочая Qwen` for OpenCode in the human's check), the default is saved
(`lado model default` shows it), yet the row says nothing of it: the field shows the new value
and nothing else, so the human cannot tell whether it was saved or something is still to press.

Cause: the requirement "Picking saves at once" asks the picker to close, save, keep the focus and
show the value; only a refusal has words of its own (under the field). The old Models cards
(LAD-187, LAD-205) behaved the same, and LAD-238 moved the picker to Agent CLIs as it was.

Options weighed (the human chose at question #4905, mockup `mockup-saved.html`):

- A (taken): a green `✓ Saved` beside the field, in a place of the row kept for it, until the
  human's next change on the page. Nothing moves; the same word and colour as `✓ Saved model
  server "<name>".` on Model servers. Long-term cost: one empty slot per row and one value of
  the page's state.
- B: a line `✓ Saved: new <CLI> agents start on <name>.` under the field. Plainer, but it adds a
  line and moves every row below, which the task asks not to do. Long-term cost: a height that
  changes under the pointer.
- C: a green tick in the field instead of its arrow for two seconds. Nothing added, but small,
  wordless and gone on a timer. Long-term cost: a timer and a mark nobody learns.

## What Changes

- Agent CLIs: after each save of a CLI's default made in its row succeeds, the row shows
  `✓ Saved` in green beside the field (on a phone, at the right of the `Default model` line
  over it). Every way of saving there counts: a row of the list (the same value again too),
  `<CLI>'s settings`, `Other name…` → Use, and `Use <CLI>'s settings` under a warning. A refusal
  shows only the refusal, as now.
- `✓ Saved` stays until the human's next change on the page: a save in any row (it then shows in
  that row only), opening a login sheet, ↻, or leaving the page. No timer.
- Screen readers hear `Saved` once, from a status region the row always has.
- `docs/design/ui.md` (Agent CLIs, Default model; Model servers' Looks) and a CHANGELOG.md line.

## Scope

- `web/src/CliDefault.tsx`, `web/src/Providers.tsx`, `web/src/styles.css`; their vitest file
  (`web/src/ModelCards.test.tsx` on PR #256) and the UI e2e test of Agent CLIs' defaults
  (`tests/ui/test_models_section.py` on PR #256).
- `docs/design/ui.md`, `CHANGELOG.md`.
- No API, schema, MCP tool or CLI change. A patch-level change: a fix of the UI; it rides under
  the `## 0.45.0 (unreleased)` heading already there, or the next patch's when 0.45.0 is out.

## Out of scope

- A CLI not installed: `Use <CLI>'s settings` there removes its whole line and moves the focus
  to the row's name; the line going is the answer, and the row has no field to stand beside.
- The New session window's Model field: picking there saves nothing, the launch does.
- Model servers (rename, ×, ticks): they show their result in the row already (the new name,
  Undo, the tick); not asked for.
- A `saving…` word while the request runs: LADO's server answers at once on the same machine;
  a request it does not answer already says `LADO's server does not answer: the value was not
  saved.`
- A default changed elsewhere (`lado model default`, another tab): the page shows the new value
  on its next read, with no `✓ Saved`, which only answers what the human did here.

## Acceptance criteria

- AC-1: on Agent CLIs at 1440, picking a model in a CLI's field shows `✓ Saved` in `--done` to
  the right of the field once the save succeeds; the field's and the next row's tops do not
  move (0 px), and `lado model default` shows the pick.
- AC-2: picking `<CLI>'s settings`, using `Other name…` → Use, and `Use <CLI>'s settings` under
  a warning each show `✓ Saved` in that row; picking the value the field already holds shows it
  too.
- AC-3: a refused save shows its refusal under the field and no `✓ Saved`; a `✓ Saved` shown
  before in that row goes.
- AC-4: a save in another row moves `✓ Saved` to that row; opening a login sheet, ↻ and leaving
  the page remove it; it never goes on a timer.
- AC-5: at 390, `✓ Saved` stands at the right of the `Default model` line over the field, the
  field keeps its full width, and nothing moves; light and dark match the mockup.
- AC-6: a screen reader hears `Saved` once per save (a `role="status"` region present before the
  save), not the ✓.
- AC-7: `make lint`, `make test`, `make web`, the changed UI test and
  `openspec validate default-model-says-saved --strict` pass; CI's `ci-ok` is green.

## Impact

- Users: a word that confirms a default model is saved; nothing else changes.
- Code: the web UI only.
- Specs: `model-settings-page` gains one requirement.
- Order: built on main only after PR #256 (LAD-238) is merged, as the field it touches lives on
  Agent CLIs only there.
