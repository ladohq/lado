Task: LAD-209

## Why

The design review of the New session window in LAD-180 left five findings. Since then the window
was rebuilt several times (LAD-239, 255, 259, 261, 265, 281). It was walked again on 2026-11-14 in
Chromium against a real `lado server`, with the fake agent and a fake model server, at 1440×900,
at 390×844 and by keyboard:

- **Obsolete: the Model list opening down at 1440×900 with fewer than three rows.** The list now
  opens upward when fewer than 240 px are below the field (`ModelPicker.tsx` `placeOf`). Measured:
  it opened up and showed 7 of 9 rows.
- **Obsolete: the focus falling on BODY after a change of Where's source.** The switch is gone;
  Where is one combobox. Each way picked with Enter puts the focus in its own field (Folder,
  Repository URL, Folder name), on Where (Project…) or in Task (a recent place), never on BODY.
- **Still true: the refusal's buttons under Model are 26 px on a phone.** `.chip-button` is
  26 px high everywhere. The phone rules raise only `.folder-hint .chip-button` to 44, while
  `new-session-window` asks for targets of at least 44 px at 760 px or less. The old review's
  "32 px" came from Settings' notes.
- **Still true: a short model name is cut at 390 px.** «Локальная Qwen» shows as «Локальная
  Q…» beside `default` and the server's mark. The cause: `.mp-title` does not shrink, but its
  box `.mp-value` (`flex: 1`, `overflow: hidden`) does; `.mc-default` is `flex: none`, and the
  server's mark keeps up to 35% of the field. `docs/design/ui.md` already says a picked name
  stays whole and the rest gives way first.
- **Partly true: «Not started: … See Model above.»** After a start refused for its model, a
  second red notice in the general notice look (red text, a triangle) stands above the
  buttons. It repeats the refusal panel under Model and the footer's `To start: fix the model`.
  It is left from LAD-180's spec. The living spec no longer has it (LAD-239 rewrote the
  requirement), and nothing else needs it: the panel under Model is a `role="alert"`, and the
  focus goes to the field.

The walk found more on a phone, which the human took into this task (2026-11-15):

- the fields of the window (Agent, Switch off, Folder, Repository URL, Clone into, Folder name,
  Project) stay 38 px high;
- a kit chip's × is 22×22 px and `+ Add kit` is 26 px;
- the field's mark of a server that does not answer shows ⚠, the sign of a warning, while the
  refusal under it shows the round «!».

Options weighed for the targets:

- **The window's phone rules raise every field and button to 44 px; a small × keeps its look and
  gets a 44 px hit area (taken).** The info buttons already do this. One media block, so the
  sheet's rule has one place.
- Raise `.chip-button` and `.field input`/`select` for every page at a phone's width. Rejected:
  Settings has its own sizes (32 px notes' chips, `ui.md` Your models), and this would change
  pages the task does not touch.
- Leave the 38 px fields and fix only the old review's items. Rejected by the human: the
  sheet's rule asks for 44 px, and the walk found the gaps.

## What Changes

At 760 px or less (the full-screen sheet):

- every field of the window (`input`, `select`, the Model field) is 44 px high, except Name on
  Task's label row (30 px, as LAD-265 decided);
- the buttons of a note (`.chip-button` under Model: `Check again`, `Use <CLI>'s settings`,
  `Use <server model>`, `Log in first`; Switch off's offers) are at least 44 px high;
- a kit chip is 32 px high, its × 32×32 px with a 44×44 px hit area; `+ Add kit` is 44 px high.

At every width:

- a picked model's name stays whole in the Model field: the server's mark gives way first, down
  to its icon (`default` stays whole); only a name longer than the whole field is cut (its whole name in
  the field's title, as now);
- the field's mark of a refused model whose server does not answer carries the refusal's round
  «!», not ⚠ (the list's rows and Settings keep ⚠, a warning there);
- a start refused for its model shows no `Not started: …` line: the refusal under Model, the
  focus on Model and `To start: fix the model` say it.

Docs: `docs/design/ui.md` (New session: the sheet's targets, Team's Kits, the Model field), and
CHANGELOG under Fixed. Version: the patch; it rides in `## 0.47.0 (unreleased)`.

## Scope

- `web/src/styles.css` (the launch window's phone block, the Model field's flex rules, the
  server's mark), `web/src/ModelPicker.tsx` (the field's mark of a refused server),
  `web/src/Launch.tsx` (the `Not started` line).
- Tests: vitest (`web/src/Launch.test.tsx`, `web/src/ModelPicker.test.tsx`), UI e2e
  (`tests/ui/test_launch_model.py`, `tests/ui/test_launch.py`).
- `docs/design/ui.md`, `CHANGELOG.md`.

## Out of scope

- The Model list's direction and the Where keyboard path: the walk found them right (above).
- Name's 30 px field: it stands on Task's label row by LAD-265's decision; 44 px would break
  the row.
- Settings' model pickers and notes: their own sizes, and ⚠ is right there (a warning, not a
  refusal).
- A general refusal of the start (`.launch-refused`, not about the model): it has no panel
  under a field to repeat, so its notice stays.
- Targets of other pages at a phone's width: not walked in this task.
