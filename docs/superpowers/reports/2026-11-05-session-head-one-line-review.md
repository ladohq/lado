# LAD-192 session-head-one-line: review report

Pull request #217 `feature/lad-192-session-head-one-line` → `main`. Scale: full, review depth:
breadth first. Head reviewed: `2d8b82a3` (= the remote head). Above 600 px a session's head is
one line of 48 px: the project as a breadcrumb, the title as a button, the run time, Stop and
the link; the folder, git, kits, CLI, Rename and Copy link moved to a popover Details that
shares its content with the phone's sheet. `Skip to chat` is the first Tab stop of a session's
page. The web UI alone: no API, schema, MCP or CLI change. Delta: a new capability,
`session-head`, 13 requirements, and 12 modified in `session-title`, `phone-layout` and
`projects`.

## Rounds

- **Round 1** (local, breadth, `origin/main...32601c12`): the lenses of spec, tests, silent
  failures, comments, types and invariants, a general one, and the architecture against
  AGENTS.md. Found F1 to F5.
- **Round 2** (local, precision, `32601c12..b16468f4`, with probes of the residual risks of the
  build report), beside the design QA at `32601c12`. Found F6 to F9 and QA-F1 to QA-F11. The
  external round was put off by the supervisor.
- **Round 3** (local, precision, `b16468f4..6b3b0251`): no findings.
- **Round 4, external 1** (Claude Code GitHub Action, the whole pull request
  `8944d030..6b3b0251`): read the TSX modules, as a diff and the code around it; not
  `web/src/styles.css`, the tests or the docs; ran nothing. Found E1 to E3, all refuted.
- **Refused archive** (integrator, at `6b3b0251`): after the archive `openspec validate --specs
  --strict` gave 56 passed, 2 failed; undone before any commit. Fixed in `14fdd158`, the
  change's specs only.
- **Round 5** (local, precision, `6b3b0251..2d8b82a3`, no code): found F10. A trial archive in a
  copy validates, 58 of 58.
- **Round 6, external 2** (the delta `6b3b0251..2d8b82a3`): no new findings, the answers on
  E1 to E3 accepted.

External rounds used: 2 of 2. The external reviewer is of the same model family and saw no
stylesheet, test or document, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | Esc with Details open also folded an expanded card or the terminals | fixed in `b16468f4`, rule refined in `6b3b0251` |
| F2 = QA-F1 | important | a click in a terminal with Details open took the focus to the title | fixed in `b16468f4` |
| F3 | important | in a window 800 px wide a chip no longer showed its terminal, caused by the first-Tab fix of `32601c12` | fixed in `b16468f4` |
| F4 | important | Skip to chat did nothing with an expanded card | fixed in `b16468f4`, with a scenario in the spec |
| F5 | minor | comments still spoke of a head of two lines and 52 px | fixed in `b16468f4` |
| F6 | minor | the comment of `useDismiss` ended up above `escapeIsTaken` | fixed in `6b3b0251` |
| F7 | minor | Stop open over an expanded card, the focus outside it: Esc did nothing | fixed in `6b3b0251` |
| F8 | minor | Esc with the focus in a terminal did not close Details | fixed in `2c932bfa`: Details closes when the focus leaves it |
| F9 | important | Skip to chat put the focus on a feed under the expanded terminals | fixed in `6b3b0251` |
| F10 | minor | the entry in `BACKLOG.md` says 400 px past the window; the field's bottom was at 463.5 px in a window of 400 px, about 63 px past it | declined: an inaccurate number in a backlog entry, left to the human at the merge gate, who approved without it |
| QA-F2 | important | Details did not fit a low window (1280×420) | fixed in `2c932bfa` |
| QA-F3 | important | Tab went under an open Details | fixed in `2c932bfa` |
| QA-F4 | important | `Path copied` left its frame | fixed in `2c932bfa` |
| QA-F5 | minor | no chevron on a phone | the human's decision #3441; fixed in `2c932bfa` |
| QA-F6 | minor | few letters of the title at 601 px | the human's decision #3441; fixed in `2c932bfa` |
| QA-F7 | minor | a broken session's words were cut with the run time | the human's decision #3441; fixed in `2c932bfa` |
| QA-F8 | minor | the state line in Details | the human's decision #3441; fixed in `2c932bfa` |
| QA-F9 | — | the touch target of the title and the link | declined by the human, #3441 |
| QA-F10 | — | `All sessions` has no frame in the sheet | declined by the human, #3441 |
| QA-F11 | minor | small differences of the line from frame g1-1440 | the human's decision #3441; fixed in `2c932bfa` |
| E1 | — | external: a late `active` calls `scrollIntoView` again and breaks the first Tab | refuted: `active` starts as `SUPERVISOR`, never null, and loading the agents does not change it |
| E2 | — | external: `:focus-visible` throws in an old Safari | refuted: the selector came in Safari 15.4, as `:has()`, which `styles.css` already uses about 30 times |
| E3 | — | external: Skip to chat on a phone makes a needless `releaseAll` | refuted: with the panel closed nothing is held, and `releaseAll` on an empty set changes nothing |
| A1 | important | integrator: the delta's requirements `On a phone the session's details open from its name` and `The session's API and head show its project` were over 500 characters, so `openspec validate --specs --strict` failed after the archive | archive undone before any commit; fixed in `14fdd158`, the specs' text only |

A1 passed every round because `openspec validate <change>` does not measure the length of a
modified requirement, and `validate --specs` does not see it before the archive. It is the
second such case after F6 of LAD-199; a trial archive in a copy catches both.

## Checks

At `2d8b82a3`: `openspec validate session-head-one-line --strict` valid; `openspec validate
--specs --strict` 57 passed, 0 failed; a trial archive and the same check 58 passed, 0 failed;
`ci-ok` green, 15 checks passed, the smoke skipped as the pull request is within CI's skip list.

At `6b3b0251`, the code unchanged since, in a separate copy: `make lint` clean; `make web` exit
0, vitest 1177 of 1177; `make test` 4814 passed, 7 skipped; `pytest -m ui` over seven files 175
passed, 1 failed (below); `test_phone.py` alone 27 passed.

Not run locally: `make test-integration` and `make check` (excluded by the settings, CI ran the
integration tests), `make test-smoke`, `make test-live`, `make test-js`.

The flaky test: `tests/ui/test_phone.py::test_an_own_answer_expands_the_card_above_the_keyboard`
failed once in a parallel run, then passed three times alone with `-n0` and in the whole file;
green on CI. Its cause was not looked for. In `BACKLOG.md`, P2.

## Metrics

Rounds: 4 local, 2 external, 0 stand-in. Confirmed: 10 local (F1 to F10), 0 external, 9 by the
design QA (QA-F1 = F2), 1 at the archive (A1). Refuted: 0 local, 3 of 3 external. Findings in
code changed by the developer's clean-up: 0. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change, so no live test was needed.

## What was not checked

- The design QA was taken at `32601c12` and not repeated whole after the fixes; the new
  screenshots were looked at selectively.
- Stop or System open with the focus outside them: Esc goes to the card and the popover stays.
  Left to LAD-198 on purpose.
- The state `loop_down` was set in the DOM; no real session with a fallen loop was raised.
- `Shell.tsx`: no test of the sliding panel with `escapeIsTaken`.
- The first Tab with `?terminal=` and `#message-…`, and the other `scrollIntoView` calls
  (`Chat.tsx`, `WaitingCard.tsx`, `fieldHeight.ts`, `Providers.tsx`).
- `<summary>` and `<label>` on a click outside Details were not tried in a browser; the same
  condition in the code covers them.
- Safari and a real phone.
- The cause of the flaky UI test above.
