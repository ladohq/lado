# The team in a session's head Implementation Plan

**Goal:** The team moves to the head of a session, in levels, and the feed gets 742 px of 900.

**Architecture:** pure rules in `teamFit.ts`; a level trial before the paint in the head's view of
`Team`; `Yours | All` in the tab bar on one small store; the composer's line out of the flow. The web
UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/session-head-team/` (AC-1..AC-15 of the artifact `design`, D1-D12),
`docs/superpowers/specs/2026-11-06-session-head-team-design.md`, run artifact `mockup-team-head.html`.

## Global Constraints

- Colours by tokens only; no new token. CSS from the artifact `design-system` of run
  `ui-design/lad-197-team-head`.
- UI texts word for word from the design doc.
- Do not touch: a phone's Team row, chips and tabs (LAD-193), the link's states (LAD-195), a stopped
  session's team (LAD-196). Keep edits of `Composer.tsx` and `Sessions.tsx` narrow.
- The designer's numbers for 1920, 1024 and 768 are replaced by design.md, D5.
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`.

## Tests per requirement

No requirement crosses processes: the integration layer has nothing to add. Rules go to vitest; what
needs a real layout goes to UI e2e. New e2e tests are in `tests/ui/test_team_head.py`.

| Requirement | vitest (`make web`) | UI e2e (`tests/ui/`) |
|---|---|---|
| session-head: the team stands in the head | `Team.test.tsx`: null, error, empty | on every tab; a click opens the terminal; no team row at 1024 |
| the team gives way in four levels | `teamFit.test.ts`: `chooseLevel`'s order, last step | D5's table with a fake team at 1920, 1440, 1280, 1024, 768, 601; no horizontal scroll |
| the title's first 24 characters | `teamFit.test.ts`: the limit fails at names only | long and short titles at 1920, 1024, 768; title edited at 1024 |
| a shortened name | `teamFit.test.ts`: tail, clash, `·2` | |
| an agent's mark | `teamFit.test.ts`: `S`, `D2`, `042`, `FL`, `AB2` | strip and head show one mark |
| an avatar's status | | `test_status_marks.py`: no pulse in the head, session's dot pulses |
| the team's list | `Team.test.tsx`: names of the button | open, row, Esc, second click, click away, focus |
| an agent's popup | `Team.test.tsx`: lines, role left out, waits | hover on head and strip |
| one stop of the keyboard | `Team.test.tsx`: roving `tabindex`, names | Tab through the head, arrows, Home, End |
| Above 600 px, cut, branch, stops | | `test_layout.py`: existing tests with `toolbar`; the branch goes at level 1 |
| session-layout: the feed starts under the tabs | | y = 88, height 742 at 1440×900, terminals open and folded; gap on Artifacts |
| the keys hint | `Chat.test.tsx`: words, with and without files | the field does not move on focus, in both themes; narrow column; problem's line |
| the composer names an agent | `Chat.test.tsx`: no `to supervisor`, files line | agent's page |
| the tabs' levels | | `test_tabs.py`: the word goes first |
| the terminal strip | `Terminals.test.tsx`: mark | `test_narrow_layout.py`: ring in place |
| 601 to 900 px | | `test_narrow_layout.py`: no team row; `test_gates.py`: the expanded card |
| activity-agent-messages | `prefs.test.ts`: the store notifies; `Agents.test.tsx`, `Chat.test.tsx` | `test_chat.py`: radios, arrows, tooltip, All in Activity, reload; Find on Flows |
| phone-layout | `Chat.test.tsx` | `test_phone.py`: no `to supervisor`, no empty line, icon stays |

## Regression run

Existing tests that look for `group "Team"` on a computer take `toolbar`: `test_layout.py`,
`test_chat.py`, `test_launch.py`, `test_status_marks.py`, `test_narrow_layout.py`, `Layout.test.tsx`.
The phone's stay `group`. Then the settings' Checks: `make lint`, `make test`, `make web`, each
changed UI file with `-m ui`, `openspec validate session-head-team --strict`, the trial archive. CI
runs the rest.

## Steps

1. Failing tests (tasks 1).
2. `teamFit.ts` and `useAgentMessages` (tasks 2): green vitest.
3. The head's view with level 0, then the trial and limit, the list, the popup, marks, keyboard
   (tasks 3): one commit each.
4. `Yours | All`, then the feed's gap and the team row's removal (tasks 4).
5. The composer (tasks 5).
6. Documents and regression (tasks 6, 7). After build, `ui-review` as design QA against the mockup
   and the dark theme.
