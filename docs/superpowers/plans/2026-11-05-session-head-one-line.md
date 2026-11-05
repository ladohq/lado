# Session head in one line Implementation Plan

**Goal:** Above 600 px the session's head is one line of 48 px; its facts are in a popover
Details that shares its content with the phone's sheet.

**Architecture:** `HeadLine` in `Sessions.tsx` is rewritten; `SessionDetails.tsx` splits into
`SessionFacts` and two frames (sheet, popover); `Shell.tsx` gets a slot for `Skip to chat`.
The web UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/session-head-one-line/` (AC-1..AC-13, D1-D13),
`docs/superpowers/specs/2026-11-05-session-head-one-line-design.md`, LAD-189 spec §1.

## Global Constraints

- Colours by tokens only; focus keeps the UI's `:focus-visible`.
- UI texts word for word: `Skip to chat`, `Session details`, `live · LADO server`, `Stop`,
  `Stop session…`, `permissions: <mode>`, `id <name>`, `All sessions`.
- Do not touch `LinkState`'s states (LAD-195), `PHONE_QUERY` (LAD-193), Resume and Forget
  (LAD-196), Stop's popover (LAD-198).
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`.

## Tests per requirement (capability `session-head` unless named)

| Requirement | vitest (`make web`) | UI e2e (`tests/ui/`) |
|---|---|---|
| one line of 48 px | `Layout.test.tsx`: items and order, no facts | `test_session_head.py`: height and one line at 601, 768, 1101, 1280, 1440, 1600, 1920, 4 kits, long names, and during a rename |
| cut, never wrapped | none (needs layout) | same test: project at most 16ch, Stop and link whole |
| branch | none (media query) | `test_session_head.py`: 1599 and 1600 |
| breadcrumb | `Layout.test.tsx`: with and without a project | `test_launch_project.py`, `test_project_page.py`: link, no `/` without a project |
| title is a button | `Layout.test.tsx`: roles, `aria-expanded`, double click opens no field | `test_session_head.py`: click, Enter, Space |
| Stop and link words | `SystemPanel.test.tsx`: tooltip by width | `test_session_head.py`: 900/901, 1100/1101 |
| popover, facts | `SessionDetails.test.tsx`: content, no about, kit problem, untested CLI, no remote | `test_session_head.py`: place, 470 px, narrow window, over expanded terminals, Copy path and Copy URL |
| closes, focus | `Menu.test.tsx`: event to `close` | `test_session_head.py`: Esc, empty place, composer, second click |
| Rename | `TitleEdit.test.tsx` as needed | `test_session_head.py`: rewritten pencil tests, focus on title |
| few stops | `Shell.test.tsx`: slot first; `Chat.test.tsx`: focus on arrival | `test_session_head.py`: Tab order; Skip from Activity and Flows |
| `phone-layout` deltas | `SessionDetails.test.tsx` | `test_phone.py`: 44 px, the sheet's content, phone head unchanged |
| `session-title` deltas | `TitleEdit.test.tsx` | `test_session_head.py`: name in Details, not in the line |

No integration test: nothing crosses processes.

## Task 1: The failing tests

Write the tests above; replace tests that pin the old line
(`test_in_a_narrow_window_the_facts_wrap…`, `test_long_facts_on_a_wide_window…`,
`test_the_pencil_renames…`, `.session-meta` locators, Copy link in
`test_what_drops_from_the_top_bar…`).

## Task 2: `SessionFacts` and the sheet

Split per D1, move Copy URL out of `GitFact`, restyle the sheet by the right-hand frame.

## Task 3: The line

`--head-h`, `HeadLine`, breadcrumb, title button, branch, Stop's word, status dot, the link's
tooltip, phone sizes (D6-D12). Remove the dead CSS.

## Task 4: The popover

`DetailsPopover`, `useDismiss`'s event, Rename (D2-D4).

## Task 5: Skip to chat

The Shell's slot, the link, the feed's focus (D5).

## Task 6: Docs

docs/design/ui.md as the design doc lists, CHANGELOG.md.

## Task 7: Regression run

`make lint`; `make web`; `make test`; `uv run pytest -m ui tests/ui/test_session_head.py
tests/ui/test_phone.py tests/ui/test_launch_project.py tests/ui/test_project_page.py
tests/ui/test_launch.py`; `openspec validate session-head-one-line --strict`;
`openspec validate --specs --strict`. Screenshots of each changed screen as run artifacts,
light and dark, in `build-report`.
