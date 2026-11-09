## 0. Before the build

- [x] 0.1 PR #256 (LAD-238, `feature/lad-238-settings-pages`) is merged into `main`; bring
  `origin/main` into the run's branch. Not merged yet: tell the supervisor and wait; never build
  on main's old one-page Settings. After the merge, run the trial archive again (the living
  specs then hold LAD-238's requirements) and grep `openspec/specs/` for `asks first`,
  `Send / Don't send` and `no Undo`: every hit about Settings' models or Statistics agrees with
  this change.

## 1. Statistics is a switch

- [x] 1.1 `web/src/Telemetry.test.tsx` (Vitest), first red: the row has one `switch` named by
  the row's name and no radios; checked only while `choice` is `on`; unchecked while not chosen,
  with `Nothing is sent until you choose.`, and while `off`, with `Nothing is sent.`; turning it
  on posts `on`, turning it off posts `off`; disabled with its line under `off_by` and with no
  endpoint; a refused post shows the problem and the switch shows the state as read. Check:
  AC-1.
- [x] 1.2 `web/src/Telemetry.tsx`, `StatisticsSetting`: the control is the switch of
  `NotificationsSetting` (design.md D1); the row is a plain `.srow` (no `.srow-wide`); `CHOICES`
  goes. The banner (`StatisticsQuestion`) is unchanged. Check: the tests of 1.1 green.
- [x] 1.3 `tests/ui/test_statistics.py` (`-m ui`): the tests that pick Send / Don't send turn the
  switch instead; one asserts not chosen shows the switch off and the banner still asking, then
  turning it on hides the banner; a screenshot of the row at 1440 and 390. Check: AC-1.

## 2. Removing a model never asks

- [x] 2.1 `web/src/ModelCards.test.tsx` (Vitest), first red: × on a default asks nothing, the row
  says `Removed <name>. <CLI> is back on its settings.` with Undo focused, Undo brings back the
  model and the default (the old tests "× on a default asks in place…" and "a default removed
  says…" become this; "Undo of a default whose second call is refused" stays). Check: AC-2.
- [x] 2.2 `web/src/ModelSettings.tsx`, `ModelRow`: × always removes at once; `asking`, the
  `alertdialog` and `backToCross` go; `onRemoved` keeps `wasDefault` from the answer's
  `cleared`. Check: 2.1 green.
- [x] 2.3 `web/src/ModelSources.test.tsx` (or the file that tests the ticks), first red:
  unticking a default asks nothing and removes it; under that tick `Removed <name>. <CLI> is back
  on its settings.` and Undo; unticking any model the same without the CLI's sentence; the focus
  stays on the tick; Undo saves the model under its name and sets the default again, a refused
  default shown in the line; after `UNDO_MS` only Undo goes and the line stays until the next
  change; ticking again takes the line away and sets no default. Check: AC-3.
- [x] 2.4 `web/src/ModelSources.tsx`: the question on a default and `asking` go; an untick
  records what was removed and shows the line under that CLI's tick, by
  design.md D3-D5: one Undo state and component and one `UNDO_MS`, shared with Your models,
  not a copy. The module's head comment
  says the new rule. Check: 2.3 green; `make web`.
- [x] 2.5 `tests/ui/test_models_section.py` (`-m ui`):
  `test_an_external_default_removed_with_a_question_and_undo` becomes one without a question;
  a new test unticks a default in a server's open list, sees the line and Undo, presses Undo and
  finds the model and the default back; a screenshot of the line. Check: AC-2, AC-3.
- [x] 2.6 The server's removal is untouched: its Vitest and UI tests stay green as they are.
  Check: AC-4.

## 3. Documents

- [x] 3.1 `docs/design/ui.md`, Settings: "A setting that applies at once and is on or off is a
  switch, a choice not made yet shown as off with its line; two or three exclusive values are
  segments." and "Removing: what can be brought back goes at once with Undo where the human
  acted; only what cannot (a server and its key, a CLI's login) asks first." Statistics: the row
  as built (the switch, its states). Model servers' "× and Undo": no question on a default; the
  tick's Undo line. Check: AC-5.
- [x] 3.2 `CHANGELOG.md` under `## 0.45.0 (unreleased)`, `### Improved`: one item in the user's
  words, at most three lines: Statistics is a switch, removing a model never asks and an untick
  can be undone. Check: AC-5.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `make web`, the changed UI test files with `-m ui`,
  `openspec validate settings-one-rule --strict`, `openspec validate --specs --strict` and the
  trial archive green; tests reported as numbers; screenshots of the changed rows attached as
  run artifacts. Check: AC-5.
