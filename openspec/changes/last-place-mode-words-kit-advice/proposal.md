Task: LAD-287

## Why

The manual check of 0.47.0rc1 (LAD-286) found three defects in the web UI.

- A. Where loses the last place. On a slow network, when the human closes New session (×, Esc,
  Cancel) before the server answers with the recent places, every later opening shows `Choose a
  place` until the page is reloaded. Seen in Firefox and Chromium with `/api/folders/recent`
  delayed by 3 s. Not a regression: `useOnce(getRecentFolders)` and `placeTouched` in
  `web/src/Launch.tsx` did not change since 0.46.2.
- C. A kit's unmet expectation advises the CLI in the window. The refusal of a start ends with
  `add a kit that provides it with --kit <kit>`, and a missing command with `leave out --kit
  <kit> when the session starts`, though the human is in the UI.
- D. Claude Code's Permissions list two rows by their raw values, `auto` and `manual`.

Causes:

- A. Closing the window keeps a draft (`Draft` in `Launch.tsx`), and a window opened with a draft
  counts its place as chosen (`placeTouched` starts true when `draft !== null`). A window closed
  before the answer keeps a draft whose place nobody chose, so the next opening never applies the
  last place; every later close keeps that draft again.
- C. Both texts are written once in `kits.py` (`_check_expected`, `commands_error`) for the CLI;
  the server passes a `KitError`'s text to the window as it is.
- D. LAD-239 named only the modes whose behaviour was checked; `claude.py` left `auto` and
  `manual` by their values. Checked now in Claude Code 2.1.295's own code: `manual` is another
  name of `default` (the CLI turns `manual` into `default` before it sets the mode), and `auto`
  is its auto mode: Claude checks each tool call for risk and prompt injection, runs the ones it
  judges low-risk and blocks the rest; it is off when the plan, the model, fast mode or an
  organisation's setting does not allow it.

## What Changes

- A. A draft remembers whether its place was chosen. A window opened with a draft whose place was
  not chosen sets Where on the last place when the recent places come, as a window without a
  draft does; Task and Team stay as the draft kept them.
- C. The two texts give the way out in words that fit the CLI and the window alike: `add a kit
  that provides it to the session`, `or start the session without kit "<kit>"`.
- D. Claude Code's `auto` gets words: title `Let Claude judge the risk`, summary `Claude judges
  the risk`, description `Checks each action for risk, runs what it judges safe and stops the
  rest. Needs a plan and model with Claude Code's auto mode.`; not risky. `manual` is no longer
  a mode of its own: a provider may name aliases of its modes; `--permission-mode manual` is still
  taken and starts (or resumes) the session as `default`, and the window lists no `manual` row.

## Scope

In: A, C and D above; UI e2e tests for A and for the texts of C and D; `docs/design/ui.md`,
`docs/cli.md` where they name these texts; CHANGELOG.md 0.48.0 (unreleased), group Fixed.

## Out of scope

- The other CLI words of `KitError` texts (`--without <item>`, `use --without …`): the window
  calls that field Switch off and offers each item as a button (`switch_off`); the task names
  only `--kit`, and a rewording of all kit refusals is a task of its own.
- Separate texts for the CLI and the window (a structured kind of the refusal that each side
  words): costs an API field and two texts to keep true for one hint; the neutral wording serves
  both.
- The session's details line `permissions: <mode>` shows the raw value (`auto`): not in the
  report; goes to the ledger under "Found on the way".
- A session stored with `manual` before this change: it resumes, and is stored as `default`
  then; until that resume its Resume window shows no chosen Permissions row. Only sessions started
  with `--permission-mode manual` from the CLI on 0.47 have it.
- The 0.47.0 CHANGELOG line "Where still shows the last place": a released version's text stays;
  the 0.48.0 Fixed line corrects it.

## Acceptance

- AC-1: with `/api/folders/recent` answering after 3 s, New session closed (×, Esc or Cancel)
  before the answer and opened again after it shows the last place in Where, and so does every
  later opening; a task typed before the close is still in Task.
- AC-2: a place the human chose before closing is still the place on the next opening, even when
  the recent places answer after the close.
- AC-3: the refusal of a start whose kit expects a skill no kit gives ends with `add a kit that
  provides it to the session`, in the window and in `lado start`; a missing command's line ends
  with `or start the session without kit "<kit>"`; no refusal of these two says `--kit`.
- AC-4: Claude Code's Permissions list `Let Claude judge the risk` with its description when
  chosen, and no row `manual` or `auto`; Team reads `Permissions Claude judges the risk` with it.
- AC-5: `lado start --permission-mode manual` with Claude Code starts the session, stored and
  launched as `default`; `lado start --help` no longer lists `manual`.

## Impact

- `web/src/Launch.tsx` (the draft's place), `src/lado/kits.py` (two texts),
  `src/lado/providers/base.py` (mode aliases), `src/lado/providers/claude.py` (auto's words,
  manual as alias), `src/lado/runtime.py` (resolves an alias before the session is stored).
- No API field, no schema migration, no MCP or CLI option change: a patch release.
- Neutral core: the alias mechanism is in `base.Provider`; only Claude Code names one today.
