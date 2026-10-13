# LAD-28 waiting-card: review report

Pull request #11 `feature/lad-28-waiting-card` → `main`. Scale: full change, review depth:
breadth. Head reviewed last: `ab8cd06`; the archive commit follows it. Core
(`runtime.answer_questions`, `state.reply_to_questions`), the API (`POST
/api/sessions/{name}/answers`, the two old question endpoints removed), the web UI's
waiting card above the composer, Needs you, docs and the openspec change; no provider
code, no schema migration, no MCP change. The human chose variant B (#4211): in a
question's tab the recommended choice is picked in advance.

## Rounds

- **Round 1** (`origin/main...eaae168`): local breadth pass with the lenses Spec, Tests,
  Silent failures, Comments, Types, General, the architecture against AGENTS.md and the UI
  against docs/design/ui.md and the screenshots. Found F1, F2, F3.
- **Round 2** (`eaae168..4dbd22c`): local precision pass over the delta. F1 and F2 closed,
  F4 found in the code rewritten for F2.
- **Round 3** (`4dbd22c..ab8cd06`): local precision pass, clean. Then external round 1 by
  the Claude Code Action (request 06:46:50 UTC, "Claude finished" 06:47:42 UTC): no
  defects, four observations (E1–E4). It read only `WaitingCard.tsx` and the tab row's
  CSS; the core, API, tests and docs are covered by the local rounds alone.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: general, spec | A gate's comment was lost on a tab switch and when the card was expanded or collapsed (`WaitingCard.tsx` at `eaae168`) | confirmed | important | fixed in `2e9c69e`; vitest "a gate's comment and an own answer stay…" |
| F2 | 1 | local: UI against spec and screenshots | Tabs wrapped onto a second line and the shown tab came off the panel (`styles.css` at `eaae168`) | confirmed | important | fixed in `4dbd22c`; UI e2e `test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways`, rule in ui.md |
| F3 | 1 | local: silent failures | Send is on again for a moment after a send, until `waiting` arrives | confirmed | minor | declined: as in the old card; the core refuses a repeat, nothing lost or doubled |
| F4 | 2 | local: precision pass over F2 | The shown tab's `scrollIntoView` moved the Needs you page down to the last session | confirmed | important | fixed in `ab8cd06`: only the tab row scrolls (`scrollLeft`); UI e2e `test_needs_you.py::test_cards_taller_than_the_window_leave_the_page_at_its_top` (red before the fix), vitest in `Chat.test.tsx` |
| E1 | 3 | external (Action) | The tab row's wheel handler has no `preventDefault`: a vertical wheel over it may scroll the feed or page too | confirmed | minor | declined: the terminals' tabs do the same (`Terminals.tsx`) |
| E2 | 3 | external (Action) | A second link to the same item may not mark it again | refuted | — | `Chat.tsx` sets `at: Date.now()` on each request |
| E3 | 3 | external (Action) | `null` ("removed by the human") is unclear in `pickOf` | refuted | — | the comment on type `Picks` says it |
| E4 | 3 | external (Action) | Send on again after a send | — | — | duplicate of F3 |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 4 (F1–F4) | 0 | — |
| external, Claude Code Action | 1 (E1) | 2 (E2, E3) | — |

No blocker; the three important findings are fixed, each with a test first seen red.

## Found on the way

None.

## Checks

- Local: `make test` 2558 passed (`eaae168`; Python unchanged after it);
  `tests/integration/test_human_messages.py` 6 passed (`eaae168`); `make lint` clean;
  vitest 680 passed, UI e2e `test_chat` and `test_needs_you` 17 passed (`ab8cd06`).
- CI of PR #11 on `ab8cd06` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos ×
  claude/codex/kilo/opencode.
- Not run: live tests (release only). The change touches `runtime.py` and `state.py`;
  delivery still goes through `_deliver`.

## Design decisions left as they are

- No comment offered together with a choice.
- The expanded card mounts through a portal and remounts its subtree; everything typed is
  kept above it.
- Variant B for the recommendation is the human's choice.

## Residual risk

- F3 and E1 as behaviour.
- The external reviewer read only the card's UI file.

## Result

Converged after round 3 (1 of 2 external rounds).
