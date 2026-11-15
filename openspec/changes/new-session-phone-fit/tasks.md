## 1. One refusal of the model

- [x] 1.1 `web/src/Launch.tsx`: drop the `Not started: … See Model above.` paragraph (D5); keep
  `modelRefusal`'s other effects. Check: `web/src/Launch.test.tsx`, the test that waits for
  `Not started` (~line 2136), now asserts no `Not started` text after the refused start, the
  refusal `does not answer` under Model, the focus on Model and the start button off; `make web`.

## 2. The Model field

- [x] 2.1 `web/src/styles.css`: in `.model-pick`, the name whole and the server's mark giving way
  first, down to its icon (D3); the list's rows unchanged. Check: the UI test of 4.2.
- [x] 2.2 `web/src/ModelPicker.tsx` and `styles.css`: the field's server mark of a refused model
  on a silent server draws the refusal's round `!`, one class shared with `.field-note.bad`'s
  sign; rows and Settings keep ⚠ (D4). Check: `web/src/ModelPicker.test.tsx`, a launch field
  on a silent server has the round mark and no ⚠, its list's row of the server ⚠, a Settings
  picker ⚠; `make web`.

## 3. The sheet's targets

- [x] 3.1 `web/src/styles.css`, the launch window's `@media (max-width: 760px)` block (D1): the
  window's `input`, `select` and the Model field 44 px high, Name's field left at 30 px; the
  notes' `.chip-button` and Switch off's offers at least 44 px; a kit chip 32 px, its × 32×32
  with a 44×44 hit area by `::after` (D2); `+ Add kit` 44 px. Check: the UI test of 4.1.

## 4. Browser tests

- [x] 4.1 `tests/ui/test_launch.py`: a test at 390×844, Team open, on Other folder…, then on
  Clone from URL…, New empty folder… and Project…: every visible `input`, `select` and
  `button` of the dialog's body but Name's field and the info buttons is at least 44 px high;
  a press 5 px right of the kit's drawn × removes the kit (scenario "A kit's ×"). Screenshot
  `targets`. Check: `uv run pytest -m ui tests/ui/test_launch.py`.
- [x] 4.2 `tests/ui/test_launch_model.py`: a test at 390×844 with `Локальная Qwen` the default
  on its server: `.mp-title` has `scrollWidth` ≤ `clientWidth`, `default` and the server's icon
  are inside the field (scenario "A short name on a phone"); screenshot `name-whole`.
  `test_a_start_refused_at_a_phone_s_width_comes_into_sight`: no `Not started` text, the
  refusal under Model in view, its buttons at least 44 px high, the server's mark with the
  round `!`. Check: `uv run pytest -m ui tests/ui/test_launch_model.py`.

## 5. Docs and CHANGELOG

- [x] 5.1 `docs/design/ui.md`, New session: the sheet's targets (fields 44 px but Name, notes'
  buttons 44, a kit's × 32 px with a 44 px hit area, `+ Add kit` 44); Team's Model: the name
  whole, the server's mark giving way first, its round `!` when refused; a start refused for
  its model has no second notice.
- [x] 5.2 `CHANGELOG.md` under `## 0.47.0 (unreleased)`, Fixed: on a phone New session's fields
  and buttons are easy to tap and a model's name is no longer cut; a refused model is said once.

## 6. Checks

- [x] 6.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_launch_model.py tests/ui/test_phone.py`, `openspec validate new-session-phone-fit
  --strict`, the trial archive. Screenshots of the changed screens (390 px: Team open with a
  refused model; the field with `Локальная Qwen`) as run artifacts.
