## Context

Three small defects of the web UI from the manual check of 0.47.0rc1 (LAD-286). Causes are in
`proposal.md`. Claude Code's modes were checked in its 2.1.295 code: `manual` is turned into
`default` before the mode is set; `auto` is its auto mode (a classifier approves low-risk tool
calls and blocks the rest).

## Decisions

### D1. The draft says whether its place was chosen

`Draft` in `web/src/Launch.tsx` gets `placeChosen: boolean`, written from `placeTouched.current`
when the window closes. `placeTouched` starts true only when the window was told where, or its
draft has `placeChosen`. A draft without it still gives Task, Name and Team; Where's fields come
from the draft as now, and the first answer of the recent places overrides them as in a window
without a draft. The focus rule stays: a late answer moves the focus only from where
`showModal()` put it (LAD-281).

Options weighed: (a) this flag, one field, the rest of the draft unchanged; (b) keep no draft when
nothing was typed: loses nothing here but still fails when a task was typed before the close; (c)
re-ask the recent places on every opening and always apply them: overrides a place the human
chose. (a) is the only one that keeps both the draft and the human's choice.

### D2. One neutral text for the CLI and the window

`kits._check_expected`'s hint becomes `add a kit that provides it to the session`; `commands_error`
says `or start the session without kit "<kit>"`. Options weighed: (a) this, two strings; (b) a
structured refusal kind that the CLI and the window each word: an API field and two texts for one
hint, against "only what is used"; (c) the server rewrites the CLI text: a second copy of the text
that drifts. The `--without` words of other `KitError` texts stay (proposal, Out of scope).

### D3. Mode aliases in the neutral provider

`base.Provider` gets `permission_mode_aliases: Mapping[str, str] = {}` (an alias to the mode it
names) and `resolve_permission_mode(mode)`, which returns the named mode for an alias and the
value otherwise. `check_permission_mode` takes aliases too. `permission_modes` and `mode_words`
hold no alias, so `lado start --help`, `ProviderInfo.permission_modes` and the window list only
the modes. `runtime` resolves the mode where it builds the session's `state.Session` (a start and
a resume), before `_check_permission_mode`, so the stored and launched value is the mode. Claude
Code: `manual` leaves `permission_modes` and goes to `permission_mode_aliases = {"manual":
"default"}`. Works for any provider; only Claude Code names one today (neutral core).

Options weighed: (a) this; (b) give `manual` the words of `default`: two rows of one behaviour;
(c) drop `manual` and refuse it: breaks a stored session and a script that passes it.

### D4. auto's words

`ModeWords("Let Claude judge the risk", "Claude judges the risk", "Checks each action for risk,
runs what it judges safe and stops the rest. Needs a plan and model with Claude Code's auto
mode.")`, not risky: it blocks what it judges risky. The comment of `permission_mode_words` names
the version whose behaviour was checked (2.1.295).

### D5. Tests by layer

- D1: a unit test in `web/src/Launch.test.tsx` (the recent places held pending, the window closed
  and opened again, then answered) and a UI e2e test in `tests/ui/test_launch.py` with the
  recent places delayed by a local HTTP proxy in front of `lado server` (the page loads through
  it; a `time.sleep` in `page.route` blocks Playwright's driver, LAD-287's note). The proxy holds
  `/api/folders/recent` until the test releases it and passes the rest through.
- D2: `tests/test_kits.py` and `tests/test_runtime.py` texts updated; a UI e2e test that a start
  refused for an expected skill shows the new text in the window.
- D3, D4: `tests/test_providers.py` (words, alias, check), `tests/test_runtime.py` (a start with
  `manual` stores `default`, a stored `manual` resumes as `default`), `tests/test_cli.py` (help
  lists no `manual`), a UI e2e test of the Permissions rows for Claude Code.
- Nothing new crosses processes: no integration test is needed beyond the existing ones.

## Risks

- The proxy test can be slow or flaky under load: it waits on an event, not a timer, and releases
  the answer only after the second opening.
