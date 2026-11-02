Task: LAD-176

## Why

The launch window's Model field (change session-model) looks and behaves unlike the
window's other fields, and three small inconsistencies of the session's model were left
after its review. The human's check of the window (Codex CLI 0.163.0, Chrome on macOS)
found:

- **The note sticks to the field.** The red refusal touches the field's frame, and the
  focus ring covers it. Cause: the field is a `<label class="field">` and `ModelNote` is
  its sibling inside `<details>`, out of the `.field` column whose 6 px gap separates a
  field from its note; the focus ring (`:focus-visible`, 2 px at a 2 px offset) reaches
  4 px past the field and lies on the note.
- **The field looks unlike Provider and Permission mode.** It is a native `<input list>`
  with a `<datalist>`: Chrome draws its own heavy ▼, and the field spans the whole row
  while Provider and Permission mode take a column of the window's grid.

And from the review of session-model (its ledger, declined there as cosmetic):

- **F4.** `lado start --model ' x '` keeps the spaces, while the window trims them.
  Cause: `cli.py` passes `args.model` as it is and `runtime.start_session` does not trim.
- **E3.** A list of models that could not be read (a list command that failed or ran over
  its time) stays in the server's cache for 60 s, so a CLI fixed meanwhile is still
  "no list" in the window. Cause: `server/launch.py` `provider_models` keeps every
  `ModelList`, read or not.
- **F3.** The window's Resume checks the session's kept model again and turns Start off
  when its CLI's list no longer has it; `lado start <session>` does not check it and
  resumes. Cause: `runtime.start_session` checks only a model given (`if model:`), and the
  window checks whatever its field holds.

Options weighed for the field:

- A (taken): a combobox of the window's own, the shape the Where and Branch fields already
  have (an input with `role="combobox"`, a `role="listbox"` list, ↑↓ Enter Esc), made a
  shared component (`SuggestField`) with a drawn arrow that opens the whole list; the
  Model field becomes a `div.field` in a column of the window's grid, its note inside.
  Long-term cost: one small component of ours; the coming model server address field of
  Advanced is built on it; Where and Branch could move onto it later.
- B: style the native `<input list>` (hide Chrome's `::-webkit-calendar-picker-indicator`,
  draw an arrow). Cheapest, but the datalist's popup stays the browser's (its look, its
  filtering, nothing in Firefox's style), and the next field would copy the same hack.
- C: a combobox library from npm. A new dependency for what the window already does
  twice; refused by the rule "a dependency only when it clearly saves work".

Options weighed for the kept model (F3), the human chose A:

- A (taken): every resume checks the session's kept model like a model given: a model
  its CLI's list lacks is refused before the start, by `lado start <session>`, the
  window and LADO's own resumes alike (the container's start, `lado update`, which leave
  the session stopped and log why); the refusal says the way out.
- B: as A for a resume by hand, a LADO resume starts with a warning; its agents would
  most likely fail at their first turn.
- C: only a warning everywhere; breaks the rule "not in the CLI's list → refused before
  the start".

## What Changes

- The Model field is a combobox of the window's own (`SuggestField`): same height, frame,
  font and a drawn chevron like the window's selects; a column of the window's grid like
  Provider (the whole row on a phone); its label bold like Provider's; the arrow, ↓ or
  typing opens the suggestions (the CLI's aliases, marked `alias`, then its list),
  filtered by what is typed; free text stays.
- The Model note stands under the field inside its `.field`, 6 px below it, where the
  focus ring does not reach.
- In Resume, a refusal of the session's own kept model adds the way out: `The session ran
  on it before. Empty the field to resume on <CLI>'s default, or pick another model.` and
  a button `Use <CLI>'s default` that empties the field.
- `runtime.start_session` trims the model (`lado start --model`, the API); only spaces is
  `''`.
- A resume checks the kept model as a given one; a refusal of the kept model names
  `--model ''` and `--model <model>`.
- The server keeps only a list of models it could read; one it could not is read again
  at the next check.

## Scope

- The Model field, its note and the three findings above.

## Out of scope

- The other fields of the window (Provider, Permission mode, Switch off, Where, Branch):
  their native arrows and labels stay; the human chose to draw the arrow only on Model,
  which keeps the step inside its frame. Moving Where and Branch onto `SuggestField` is a
  task of its own if wanted.
- A single flight for the list of models (E3's second half): the window asks 300 ms after
  the last keystroke and the list is kept once read; two concurrent first reads cost one
  extra run of the CLI's list command.
- Effort, model servers and power tables beyond one row: the coming changes.
- No schema change, no API change.

## Impact

- `web/src/Launch.tsx` (the Model field, `ModelNote`), a new `web/src/SuggestField.tsx`,
  `web/src/styles.css`; `src/lado/runtime.py` (`start_session`), `src/lado/server/launch.py`
  (`provider_models`).
- Tests: `web/src/*.test.tsx` (vitest), `tests/test_runtime.py`, `tests/test_cli.py`,
  `tests/test_server_launch.py`, `tests/ui/test_launch.py`.
- Docs: `docs/design/ui.md` (New session, Resume), `docs/cli.md` (`--model`), CHANGELOG.md
  0.45.0's line on the session's model refined, no new line.
- Version: no bump of its own; the session's model is unreleased in 0.45.0.
