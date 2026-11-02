## 1. Core

- [ ] 1.1 `src/lado/runtime.py`, `start_session`: trim `model` first (`None` stays `None`;
  only spaces is `''`); the docstring says so. Check: `tests/test_runtime.py`, a model with
  spaces is kept as `gpt-5.6-sol` (fake provider's list), `'  '` on a resume drops the
  table; `tests/test_cli.py`, `lado start --model ' fake-large '` stores `fake-large`.
- [ ] 1.2 `runtime.start_session`: check the model the session will run on
  (`session_model(sess, agent_cli)`), given or kept, not only a given one; a refusal of a
  kept one (`model is None` and the table kept) appends `; the session ran on it before:
  resume it with --model '' for <CLI title>'s default or --model <model> for another`.
  Check: `tests/test_runtime.py`: a kept model the fake list no longer has is refused with
  that text, the session stays stopped with its table, no agent starts; a kept model in
  the list resumes as before (`test_a_resume_keeps_the_model`); a resume with `--model ''`
  of that session starts with no check; `resume_at_start` of that session reports `could
  not resume session … at the container's start: …` and leaves it stopped.
- [ ] 1.3 `src/lado/server/launch.py`, `provider_models`: keep a list only when it was read
  (`listed.models is not None`); the comment of `MODEL_LIST_KEPT` says so. Check:
  `tests/test_server_launch.py`: a failed list is asked again at the next check, a read one
  is still kept (`test_the_server_keeps_a_provider_s_list_a_while`).

## 2. UI

- [ ] 2.1 `web/src/SuggestField.tsx`: an input with `role="combobox"`,
  `aria-autocomplete="list"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`;
  a drawn chevron button (`aria-label` given by the caller, `tabIndex={-1}`) that opens or
  closes the whole list; typing and ↓ open it filtered by substring (case-insensitive),
  ↑↓ move, Enter picks the highlighted one (and otherwise leaves the form's Enter alone),
  Esc closes, blur closes, a click picks (mousedown keeps the focus); each option may carry
  a muted tag. The list uses `.where-list`'s look; new CSS in `styles.css` as
  `.suggest-box`, `.suggest-arrow`, `.suggest-list .tag` (the proposal's option A; the
  mockup `mockup-model-field.html`). Check: `web/src/SuggestField.test.tsx` (vitest): the
  arrow opens the whole list, typing filters, ↓/Enter picks, Esc closes, free text is
  kept, Enter with nothing highlighted is not prevented.
- [ ] 2.2 `web/src/Launch.tsx`: the Model field becomes a `div.field` inside a
  `div.launch-grid` of Advanced (left column), with `<label htmlFor>`, `SuggestField`
  (aliases tagged `alias`, then the list) and `ModelNote` inside the same `.field`; the
  `<datalist>` goes. Check: `web/src/Launch.test.tsx`: the note is inside the Model
  field's `.field`, the suggestions are the provider's aliases then models, the existing
  model tests pass.
- [ ] 2.3 `ModelNote` in Resume: when the typed model is the session's kept one
  (`resuming.model`) and the check refuses it, the note adds the line `The session ran on
  it before. Empty the field to resume on <CLI title>'s default, or pick another model.`
  and a `chip-button` `Use <CLI title>'s default` that empties the field. Check:
  `web/src/Launch.test.tsx`: Resume of a session whose model is refused shows the line,
  Resume is off, the button empties the field and Resume is on.
- [ ] 2.4 `tests/ui/test_launch.py` (marker `ui`), extend
  `test_a_session_starts_on_the_model_typed_in_advanced`: with the field focused and
  refused, the note's top is ≥ the field's bottom + 6 px and its box does not overlap the
  field's box grown by 4 px (the ring); Model's height, width and the chevron's presence
  equal Provider's height and width (window 1400 px); clicking the arrow lists
  `fake-small` and `fake-large`, typing `large` leaves `fake-large`, ↓ Enter picks it;
  free text `nope` still refused; screenshots `refused` (focused), `warned`, `empty`,
  `list`. A new test for Resume of a session whose kept model the fake list lacks
  (`FAKE_AGENT_MODELS` without it): the note's way out, `Use Fake agent's default`
  empties the field and Resume resumes on the CLI's default; screenshot `resume-refused`.
  Run: `uv run pytest -m ui tests/ui/test_launch.py`.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`, New session, Advanced: the Model field is the window's own
  combobox (`SuggestField`), not a `<datalist>`; its column, chevron, `alias` tags, keys;
  the note inside its `.field`; the server keeps a list only once read. Resume: the kept
  model is checked as in `lado start`, the way out and its button.
- [ ] 3.2 `docs/cli.md`, `--model`: trimmed; a resume checks the kept model too, its
  refusal's way out; LADO's own resumes leave the session stopped.
- [ ] 3.3 CHANGELOG.md, `## 0.45.0 (unreleased)`, the line **Choose the session's model.**:
  "a resume keeps it" becomes "a resume keeps it and checks it again"; no new line (the
  model is unreleased).

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py`,
  `openspec validate model-field-suggestions --strict`, `openspec validate --specs
  --strict`; the screenshots attached as run artifacts; CI green.
- [ ] 4.2 Regression: without `--model` and with the field empty nothing changes
  (`test_no_table_passes_no_model`, the UI test's `empty` state).
