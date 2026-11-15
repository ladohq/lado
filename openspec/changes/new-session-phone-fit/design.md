## Context

The walk of 2026-11-14 (proposal) measured the New session window at 390×844 and 1440×900. All
changes are in the web UI; the server, the API and the core are untouched. The provider does not
matter: the window is the same for every agent CLI.

## Decisions

### D1. The sheet's sizes live in the launch window's phone block

The 44 px rules go into the existing `@media (max-width: 760px)` block of the launch window in
`styles.css` (beside `.folder-hint .chip-button`), with selectors under the launch dialog, so
Settings' pickers and notes keep their sizes. Name's field (`.field .name-inline input`) is left
out by name.

### D2. A small × gets its hit area from a pseudo-element

The kit chip's × keeps a 32 px look and gets `::after` with a negative inset to 44×44 px, as the
info buttons do (`.info-tip::after`). A real 44 px button would make the chip 44 px high and the
kits' box twice as tall.

### D3. The Model field gives way from the right

In the field (`.model-pick`), `.mp-value` does not grow or shrink past its content
(`flex: 0 1 auto`, `min-width` its name's), the server's mark shrinks first (`flex-shrink`
above the others, `min-width` its icon and sign), `default` stays `flex: none`, and the chevron is pushed to
the end (`margin-left: auto`). The name is cut only when the field is narrower than the name
alone; the field's `title` keeps it whole, as now. The list's rows are not changed.

### D4. The field's server mark knows a refusal

`Server` in `ModelPicker.tsx` takes whether it stands in the launch field of a refused model;
there it draws the round «!» of `.field-note.bad::before` (one CSS class shared by both, so the
two cannot drift) instead of ⚠, with the same text for a screen reader (the sign stays
`aria-hidden`). Rows and Settings keep ⚠.

### D5. The model's refusal has one place

`Launch.tsx` drops the `Not started: … See Model above.` paragraph; `modelRefusal` keeps doing
what it does (Team open, focus on Model, the start button off). The general refusal
(`generalRefusal`, `.launch-refused`) is untouched.

## Tests

| Requirement | Layer | Test |
|---|---|---|
| The window's frame keeps the footer in view (targets) | UI e2e | `tests/ui/test_launch.py`: at 390×844, Team open, every visible `input`, `select`, `button` of the dialog's body but Name and the info buttons is at least 44 px high; the kit's × removes the kit when pressed 5 px outside its drawn box |
| The Model field looks like the window's other fields (name whole) | UI e2e | `tests/ui/test_launch_model.py`: at 390, `Локальная Qwen` as the default on its server: `.mp-title`'s `scrollWidth` ≤ `clientWidth`, `default` and the server's icon in view |
| The Model field's server mark shows a refusal | vitest | `web/src/ModelPicker.test.tsx`: the launch field on a silent server shows the round mark, a row of the list ⚠ |
| A refused model in the window (one refusal) | vitest + UI e2e | `web/src/Launch.test.tsx` (the test at line ~2136): no `Not started` text, the refusal under Model; `tests/ui/test_launch_model.py::test_a_start_refused_at_a_phone_s_width_comes_into_sight`: the same, refusal's buttons ≥ 44 px |

The regression run: `make lint`, `make test`, `make web`, `uv run pytest -m ui
tests/ui/test_launch.py tests/ui/test_launch_model.py tests/ui/test_phone.py`.
