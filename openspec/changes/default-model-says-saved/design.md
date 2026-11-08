## Context

On PR #256 (LAD-238) a CLI's default model sits in its row on Settings → Agent CLIs:
`Providers.tsx` draws the rows and `CliDefault.tsx` the `Default model` label (`.cli-ml`,
aria-hidden, the field's name is its `aria-label`) and the picker in a grid `.cli-model`
(`104px minmax(0, 360px)`; one column at 600 px and narrower, and under `:root[data-phone]`),
with `useSave` doing every save of the row. The row is 680 px wide at most, so about 200 px
stay free right of the field. This change is built on main only after PR #256 is merged.

## Decisions

1. **One value of the page, not of the row.** `Providers.tsx` keeps `saved: string | null`, the
   CLI whose row shows `✓ Saved`, and passes it and two callbacks to each `CliDefault`:
   one called when a save starts (sets it to `null`), one when it succeeds (sets it to that CLI).
   One value makes "the next save anywhere takes it away" true by construction; a value per
   row would need rows to clear each other. Opening a login sheet (`setSheet`), ↻ and the
   page's unmount clear it as well. Why not a timer: the human chose "until the next change"
   (#4905), and the section's rule is that no row leaves on a timer.
2. **Through `useSave`.** The start and success callbacks go into `useSave`, so every way the
   picker saves (a row of the list, `<CLI>'s settings`, `Other name…` → Use, `Use <CLI>'s
   settings` under a warning) says `Saved` with no case missed; a refusal or an unanswered
   request calls only the start one. `NotInstalled` uses `useSave` too but shows no `✓ Saved`
   (its line goes; proposal, Out of scope).
3. **A slot that is always there.** `Picker` always renders `<span className="cli-saved"
   role="status">`, empty or with `<span aria-hidden="true">✓</span> Saved`. Its height is
   fixed by the grid (38 px line on a computer, 20 px on a phone), so filling it moves nothing,
   and a status region present before the change is announced reliably; the ✓ is hidden, so a
   screen reader says `Saved`.
4. **Its place in the grid.** On a computer `.cli-model` gets a third column `auto`; the slot
   sits in row 1, column 3, `line-height: 38px`, `white-space: nowrap`, `min-width: 4.5em` (the
   room of `✓ Saved` kept while empty: between 601 and about 900 px the field is narrower than
   360 px, and a slot that grew when filled would narrow it). At 600 px and narrower
   (and under `:root[data-phone]`) the grid is `minmax(0, 1fr) auto`: the label row 1 column 1,
   the slot row 1 column 2 (`line-height: 20px`, right-aligned), the field and its notes from
   row 2 across both columns, so the field keeps its full width. Colour `--done`, 13 px, no
   colour of its own (docs/design/ui.md, Looks).
5. **Same value again saves again.** Picking the row the field already holds calls `onPick` as
   any row does (only the "stay" row keeps the value without a save), so it saves and says
   `Saved`; the human then knows the value is the saved one.
6. **Tests at the lowest layers.** vitest (the file that renders `CliDefault`,
   `web/src/ModelCards.test.tsx` on PR #256, and `Providers.test.tsx` for the page's value)
   for when it shows and goes; one UI e2e test for the place (0 px move) and the screenshot. No
   integration test: nothing crosses processes beyond the existing `PUT` of a default.

## Neutral core and roadmap

Nothing above `providers/` learns of a CLI: the word is the same for every row, Claude Code,
Codex CLI, OpenCode and Kilo CLI alike. No field, API or option is added (only what is used);
the page's state is the one place that knows which row shows it (one source of truth); a
refusal still says so (no silent drop). ROADMAP's coming stages add rows, not other kinds of
save to this field; a future section with saves of its own can reuse the class `.cli-saved`
or not, as its design decides.

## Risks

- PR #256 changes before its merge: the developer builds on what is merged, and the class and
  file names above follow it.
