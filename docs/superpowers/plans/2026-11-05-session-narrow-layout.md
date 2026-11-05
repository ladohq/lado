# A session's page on narrow windows Implementation Plan

**Goal:** The chat keeps 420 px above 900 px, a session's page stands still at 601 to 900 px, and a
window of 600 px or less is a phone with a mouse too.

**Architecture:** a pure rule `columns.ts` over the stored prefs, held by `useSessionColumns` in
`Sessions.tsx`; the terminal panel reads it. CSS moves 601-900 px to the wide window's model, and
LAD-194's rules for a scrolling window go. The web UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/session-narrow-layout/` (AC-1..AC-19, D1-D14),
`docs/superpowers/specs/2026-11-05-session-narrow-layout-design.md`, LAD-189 spec §2 and §9.

## Global Constraints

- Colours by tokens only. New sizes: `--chat-min`, `--strip-w`.
- UI texts word for word: `Open <agent>'s terminal`, `Terminals`, `Sessions`.
- A fold for room never writes `lado.terminals` or `lado.sessionsList`.
- Do not touch the Team row and composer hints (LAD-197), Take control's dimming (LAD-198), the
  link's states (LAD-195), Needs you's card.
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`.

## Tests per requirement (capability `session-layout` unless named)

| Requirement | vitest (`make web`) | UI e2e (`tests/ui/`) |
|---|---|---|
| the chat keeps 420 px | `columns.test.ts`: 901 to 1440, opened or not | `test_layout.py`: the chat's measured width at 901, 1024, 1101, 1280, 1440, both ways, on Activity and Artifacts |
| the other gives way | `columns.test.ts`: rail open at 901, width 640 at 1024, control | `test_terminal_panel.py`: control ends on a fold |
| comes back, no trace | `columns.test.ts`: order of return; `prefs.test.ts`: `chosen` | `test_layout.py`: resize down and up, storage unchanged, reload |
| rail and terminals start | `prefs.test.ts`; `Layout.test.tsx`: the rail follows | `test_layout.py`: 1440, 1600, the human's rail after a reload |
| list's strip | `Layout.test.tsx` | `test_sessions_strip.py`: 48 px |
| badges | `Layout.test.tsx`: the three rules, the clash | `test_sessions_strip.py`: `154`, `189` |
| tabs' levels | none (needs layout) | `test_tabs.py`: each level, ›, ‹, the shown tab in view |
| terminal strip | `Terminals.test.tsx`: names, opening, marks | `test_terminal_panel.py`: 32 px, 24×24 |
| 601-900 stands still | none (needs layout) | `test_layout.py`: 768, 880, `scrollY` 0 after the wheel, composer and gate in the window; `test_needs_you.py`: scrolls as before |
| columns start folded, list and terminals over | `Terminals.test.tsx`: nothing stored | `test_layout.py`: panels' boxes, Esc, a click beside, focus, the wide window's choice kept |
| phone-layout: the query | `phone.test.ts`: the query's text | `test_phone.py`: 390 with a mouse; touch 768, 1024, 1440; mouse 1280×400; sideways |
| phone-layout: targets | none | `test_phone.py`: 44 and 44×33, spec §9's table row by row |
| chat-question-card: footer and expanded | `Chat.test.tsx`: no `--chat-top` | `test_gates.py`: 768×700, ×500, ×1024, expanded, narrowing from 1440 |
| session-head: Details at 601 | none | `test_session_head.py` |
| projects: stacks | none | `test_projects_section.py`: 700 px |

Regression run: `make web`, `make lint`, `make test`, then `uv run pytest -m ui` on each changed file,
and the whole UI layer by CI. No test crosses a process, so no integration test is added.

## Files with a mouse in a narrow window

`tests/ui/`: `test_artifacts_tab.py`, `test_chat.py`, `test_gates.py`, `test_kits_page.py`,
`test_launch_project.py`, `test_launch.py`, `test_layout.py`, `test_project_page.py`,
`test_providers_section.py`, `test_selection.py`, `test_session_head.py`. Each keeps what it tests:
take 601 px or more when it tests a narrow computer's window, the phone's check when the layout is
what it means. Also grep `tests/ui` for 700 and 800 px: the session's page no longer scrolls there.

## Steps

The order of `tasks.md`, one commit per task, failing tests first:

1. Tests (1.1, 1.2).
2. `columns.ts`, prefs, the hook (2.1-2.3): AC-1 to AC-7 green.
3. Strips and tabs (3.1-3.3).
4. The still window (4.1-4.4): the largest diff in `styles.css`. Remove the `max-width: 900px` blocks
   of `.sessions`, `.session-page`, `.session-main` and `.terminals`, and LAD-194's block, in the same
   commit as their replacement.
5. The phone (5.1, 5.2), targets (6.1, 6.2).
6. Documents, the round, screenshots, ui-review (7.1-7.3).
