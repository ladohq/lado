## 0. Before the build

- [x] 0.1 PR #256 (LAD-238, `feature/lad-238-settings-pages`) is merged: `git fetch origin` and
  merge `origin/main` into the branch. While it is open, build nothing and tell the
  supervisor.

## 1. The page's value and the slot

- [x] 1.1 `web/src/Providers.tsx`: `saved: string | null`, passed with `onSaving` and `onSaved`
  to each `CliDefault`; cleared when a login sheet opens, on ↻ and on unmount (design D1).
- [x] 1.2 `web/src/CliDefault.tsx`: `useSave` calls `onSaving` when a save starts and
  `onSaved` when it succeeds; `Picker` always renders the status slot `.cli-saved` with
  `✓ Saved` (✓ aria-hidden) when `saved` is its CLI; `NotInstalled` shows none (D2, D3).
- [x] 1.3 `web/src/styles.css`: `.cli-model`'s third column and `.cli-saved` on a computer;
  the label and slot on one line at 600 px and narrower and under `:root[data-phone]` (D4).

## 2. Tests

- [x] 2.1 vitest (`web/src/ModelCards.test.tsx`): `Saved` shows after a pick of the list, of
  `<CLI>'s settings`, of `Other name…` → Use, of `Use <CLI>'s settings` under a warning, and of
  the value already held (AC-2); not after a refusal or an unanswered request, and one shown
  before goes (AC-3); the status region exists before the save and its text is `Saved` (AC-6).
- [x] 2.2 vitest (`web/src/Providers.test.tsx`): a save in a second row moves it there; opening
  a login sheet and ↻ remove it; nothing removes it with fake timers advanced a minute (AC-4).
- [x] 2.3 UI e2e (`tests/ui/test_models_section.py`, marker `ui`): at 1440 a pick shows
  `✓ Saved` right of the field, the field's and the next row's tops move 0 px, and
  `lado model default` shows the pick (AC-1); at 390 the slot is on the label's line and the
  field's width is unchanged (AC-5). Screenshots of 1440 light, 390 light and 768 dark as run
  artifacts.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`: Agent CLIs, Default model: the `✓ Saved` slot, when it shows and
  goes; Model servers' Looks: green (`--done`) for `✓ Saved` of a default too.
- [ ] 3.2 `CHANGELOG.md` under `## 0.45.0 (unreleased)` (or the next heading by AGENTS.md's
  rule), `### Improved`: **A default model says it was saved.**

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_models_section.py`
  pass (AC-7).
- [ ] 4.2 `openspec validate default-model-says-saved --strict` and the trial archive pass.
