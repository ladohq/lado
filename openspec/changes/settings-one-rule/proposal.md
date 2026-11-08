Task: LAD-243

## Why

Settings, as LAD-238 (pull request #256) rebuilds it, follows two looks for one kind of thing:

- On or off. General's Browser notifications is a switch; Statistics' "Send anonymous
  statistics and errors to LADO's maintainers" is a choice of two segments, Send / Don't send.
- Removing. Model servers removes a model in four ways: × on a model goes at once with Undo;
  × on an agent CLI's default asks first and then offers Undo as well; unticking a model under
  a server's model goes at once with no Undo, and unticking a default asks first and leaves no
  Undo; removing a server asks first and says `This cannot be undone.` (its key is deleted).

The human, checking PR #256 by hand, saw both and asked for one rule each.

Root cause: round 5's design system wrote the rule "a switch for an on/off setting that applies
at once; segments for 2-3 exclusive choices or when 'not chosen' must show", and Statistics has
a third state, not chosen (the banner still asks), so it got segments. For removing there was no
rule: each path was designed in its own round (LAD-187 Undo of ×, LAD-205 the question on a
default and the bare untick), and nothing held them together.

Options weighed for on and off:

- A (taken, question #4907): a switch for every setting that is on or off. Statistics becomes a
  switch; "not chosen" shows as off with its line `Nothing is sent until you choose.`, and the
  banner keeps asking until the human chooses. Long-term cost: Settings cannot record an
  explicit "don't send" without turning the switch on first; the banner and `lado telemetry
  off` do it.
- B: segments for every on/off setting; Browser notifications becomes On / Off. Bulkier, and
  Settings would have no switch at all.

Options weighed for removing:

- A (taken, #4907): what can be brought back goes at once and offers Undo where the human acted;
  only what cannot be brought back asks first. Every model removal, a default's too, by × or by
  its tick, goes unasked with Undo; removing a server keeps its question (its key is gone).
  Logging out of an agent CLI on Agent CLIs keeps its question for the same reason. Long-term
  cost: one Undo for the ticks besides the one of Your models.
- B: a question for every removal and no Undo anywhere. Less code (Undo's timer and its rows
  go), but a click more for the most frequent ×, and a mis-click costs a question each time.

## What Changes

- Settings → Statistics: the row's control is a switch (on: sending; off: not chosen or not
  sending), with the same state lines; disabled while the environment or a missing endpoint
  switches sending off. The banner's buttons stay.
- Model servers, Your models: × on an agent CLI's default asks nothing; its row says
  `Removed <name>. <CLI> is back on its settings.` with Undo, as today after the question.
- Model servers, a server's model: unticking an agent CLI removes that model at once, a default
  too, and leaves under that CLI's tick `Removed <name>.` (and `<CLI> is back on its
  settings.` for a default) with Undo for ten seconds; Undo saves the model again and sets the
  default again; the question on a default goes.
- `docs/design/ui.md`: the rule of a setting that is on or off and the rule of removing in
  Settings, and the sections Statistics and Model servers as built.

## Scope

- `web/src/Telemetry.tsx` (`StatisticsSetting`), `web/src/ModelSettings.tsx` (`ModelRow`,
  Undo), `web/src/ModelSources.tsx` (the ticks), `web/src/styles.css` if a rule is left
  without users or the tick's Undo line needs one.
- Their Vitest and UI tests, `docs/design/ui.md`, `CHANGELOG.md`.

## Out of scope

- Other screens' removals (projects, sessions, kits, artifacts): the human limited the rule to
  Settings (#4907, 3); a later task may carry it.
- Removing a server: it keeps its question, as its key cannot be brought back.
- Logging out of a CLI: it keeps its question (requirements "Logging out of Claude Code asks
  first", "Logging out of Codex asks first"), as a login cannot be brought back by Undo.
- The statistics banner: its Send statistics / Don't send stay; it is a question, not a
  setting.
- Theme: three exclusive values, segments by the same rule.
- An API, schema, MCP tool or CLI change: none is needed.

## Acceptance criteria

- AC-1: Settings → Statistics has one switch named by the row's name; on while the choice is
  `on`; off while not chosen or `off`, with the lines `Nothing is sent until you choose. What
  LADO collects ↗` and `Nothing is sent. What LADO collects ↗`; turning it on chooses `on`,
  turning it off chooses `off`; disabled with its line while `DO_NOT_TRACK` (or another
  variable) or a missing endpoint switches sending off; no segments Send / Don't send remain in
  Settings.
- AC-2: × on an agent CLI's default in Your models removes it without a question: the row says
  `Removed <name>. <CLI> is back on its settings.` with Undo focused, and Undo brings back the
  model and the default.
- AC-3: unticking an agent CLI under a server's model removes the model without a question, a
  default too; under that tick `Removed <name>.` (with `<CLI> is back on its settings.` for a
  default) and Undo show for ten seconds, then `Removed <name>.` stays until the next change;
  Undo saves the model again under its name and sets the default again; the focus stays on the
  tick.
- AC-4: removing a server still asks with `This cannot be undone.`; nothing else in Settings
  asks before a removal.
- AC-5: `docs/design/ui.md` states both rules; `make lint`, `make test`, `make web`, the changed
  UI tests with `-m ui`, `openspec validate settings-one-rule --strict` and the trial archive
  pass; CI's `ci-ok` is green.

## Impact

- Users: Statistics in Settings is a switch; removing a model never asks, and unticking one can
  be undone.
- Code: the web UI only, as in Scope.
- Specs: `usage-telemetry` (the Settings row), `model-settings-page` (removing a model, Undo of
  a tick).
- Version: no bump of its own; it ships under the existing `## 0.45.0 (unreleased)` with
  LAD-238. Alone it would be a patch (a change of existing UI, no feature, no API).
- Builds on PR #256 (LAD-238): the build starts once it is merged into `main`.
