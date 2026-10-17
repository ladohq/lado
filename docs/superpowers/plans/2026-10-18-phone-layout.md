# Phone layout Implementation Plan

**Goal:** On a phone (a touch screen ≤ 600 px wide or ≤ 500 px high) the UI shows a
phone layout: the rail as a menu, a one-line top bar, the session's details in a sheet,
tabs that fit, a chat whose composer is always at hand, terminals over the screen,
tooltips on a tap. A computer is unchanged.

**Architecture:** One query in `phone.ts` and its hook; the Shell sets `<html
data-phone>`; all phone CSS in one section of `styles.css` under `:root[data-phone]`;
components branch on `usePhone()` only where the structure changes (the Shell's menu, the
session head and its sheet, the session list, the waiting card sideways, the terminal
panel, the Tooltip's tap).

**Tech Stack:** React + TypeScript (Vite), vitest, pytest-playwright (Chromium with
`is_mobile`/`has_touch`).

**Spec:** `openspec/changes/phone-layout/` (proposal AC-1…AC-13, the delta's
requirements, `design.md` D1–D9); `docs/superpowers/specs/2026-10-18-phone-layout-design.md`.
Mockup: run artifact `task/lad-95/mockup-phone.html`, navigation A.

## Global Constraints

- `PHONE_QUERY = "(pointer: coarse) and (max-width: 600px), (pointer: coarse) and
  (max-height: 500px)"`, `SHORT_QUERY = "(max-height: 500px)"`, written only in
  `web/src/phone.ts`.
- No phone rule outside `styles.css`'s section "Phone layout"; every selector there
  starts with `:root[data-phone]`.
- On a phone no remembered layout state is written: `lado.rail`, `lado.sessionsList`,
  `lado.terminals`, `lado.waitingHeight`; of `lado.waitingMinimized.*`, the layout's
  sideways fold is not written, while the human's own minimize is remembered as on a
  computer (D5).
- The UI's strings are English: "Menu", "Menu, N waiting", "Close menu", "Close terminal",
  "Copy path", "Copy link", "Rename", "All sessions", "Close".
- No server, API, schema or CLI change; `web/openapi.json` and `web/src/api.gen.ts`
  untouched.
- CHANGELOG.md: one line under a new `## 0.41.0 (unreleased)`.

## Review Focus

- A computer's window of any size gets no phone rule (the guard test with a mouse at
  390×844 too).
- The feed, not the window, scrolls on a phone; the composer stays at the bottom with a
  tall gate's card (the card's list scrolls inside).
- Turning sideways and back: the card's layout fold is not written to storage, and the
  human's own minimized state survives.
- The drawer's focus: in on open, back to Menu on close; Esc closes it but not a dialog
  above it.
- The Tooltip's tap: a button never shows one; a hint's shows and hides on a tap outside.

## Task 1: The query and the hook (D1)

**Files:** `web/src/phone.ts` (new), `web/src/phone.test.ts` (new), `web/src/Shell.tsx`.

- [ ] `PHONE_QUERY`, `SHORT_QUERY`, `usePhone()` with `matchMedia` listeners; the Shell
  sets and removes `document.documentElement.dataset.phone`.
- [ ] vitest `phone.test.ts`: a fake `matchMedia` gives `null`, `"tall"`, `"short"`, and
  the value follows a change event; the attribute follows it.
- [ ] Check: `cd web && npx vitest run src/phone.test.ts`, `make web`.

## Task 2: The app window and the section of CSS (D4)

**Files:** `web/src/styles.css`, `web/index.html`.

- [ ] Section "Phone layout" at the end: the wide-window app rules under
  `:root[data-phone]`, `.app` one column, the rail hidden; tabs without icons; the flow
  event's grid; the waiting card's `max-height: 50%`; the composer's 16 px and no
  `.composer-keys`; the Kits tabs; `short`: no Team row, no `.composer-to`.
- [ ] `index.html` viewport: `width=device-width, initial-scale=1.0,
  interactive-widget=resizes-content`.
- [ ] The artifact tab's image `max-height` by `dvh` (BACKLOG entry removed).
- [ ] Check: `make web`; the e2e of Task 8 for tabs, feed, composer, Kits.

## Task 3: The menu (D2)

**Files:** `web/src/Shell.tsx`, `web/src/icons.tsx` (`MenuIcon`), `web/src/styles.css`,
`web/src/Layout.test.tsx` or a new `Shell.test.tsx`.

- [ ] Menu in the top bar when `usePhone()`; badge with the Needs you count; the rail's
  `data-open`, the scrim "Close menu", Esc, route change; focus in and back; no
  `lado.rail` write.
- [ ] vitest: Menu absent without a phone; present with the badge and name "Menu, 2
  waiting"; opens, closes on Esc, on the scrim, on a link; focus returns to Menu.
- [ ] Check: `cd web && npx vitest run src/Shell.test.tsx`, `make web`.

## Task 4: The compact head and the details sheet (D3)

**Files:** `web/src/Sessions.tsx` (`HeadLine`), `web/src/SessionDetails.tsx` (new) and
its test, `web/src/SystemPanel.tsx` (`LiveButton`'s dot on a phone), `web/src/styles.css`.

- [ ] On a phone: dot, title button, Stop; the live mark a dot unless reconnecting.
- [ ] `SessionDetails` `<dialog>`: status, run time, folder whole with Copy path,
  `GitFact`, kits with `KitTip`, CLI with `CliTip`, Rename (`TitleEdit`), Copy link, All
  sessions, Close.
- [ ] vitest: the head's phone branch renders no facts; the sheet lists the facts, Rename
  edits the title, Close and Esc close it.
- [ ] Check: `cd web && npx vitest run src/SessionDetails.test.tsx`, `make web`.

## Task 5: Sessions and the waiting card (D5, D6)

**Files:** `web/src/Sessions.tsx`, `web/src/WaitingCard.tsx`, their tests.

- [ ] On a phone: no strip, no splitter; `/sessions` renders the list as the content; a
  session's page renders no list; no `lado.sessionsList` write.
- [ ] `short`: the card minimized by the layout (state not stored); a tab shows it
  expanded; fold goes back; upright drops the state; `NARROW` scroll-into-view off on a
  phone.
- [ ] vitest: the card's layout fold leaves `lado.waitingMinimized.<session>` untouched;
  a tab expands it.
- [ ] Check: `cd web && npx vitest run src/WaitingCard.test.tsx`, `make web`.

## Task 6: Terminals over the screen (D7)

**Files:** `web/src/Terminals.tsx`, `web/src/Terminals.test.tsx`.

- [ ] On a phone no column or strip; opening a terminal shows the panel expanded; the
  button reads Close terminal and closes it; no `lado.terminals` write.
- [ ] vitest of the phone branch.
- [ ] Check: `cd web && npx vitest run src/Terminals.test.tsx`, `make web`.

## Task 7: Tooltips on a tap (D8)

**Files:** `web/src/Tooltip.tsx`, `web/src/Tooltip.test.tsx`.

- [ ] Touch `pointerup` on a non-button, non-link trigger shows it; `pointerdown` outside
  hides it; buttons and links never.
- [ ] vitest of both.
- [ ] Check: `cd web && npx vitest run src/Tooltip.test.tsx`.

## Task 8: UI e2e (D9)

**Files:** `tests/ui/test_phone.py` (new).

Tests, each with screenshots in `<temp dir>/lado-ui-shots/`:

| Test | Requirement / AC |
|---|---|
| `test_a_computer_keeps_its_layout[1280x800, 800x900, 390x844]` (mouse) | picks by screen and pointer; AC-1 |
| `test_a_tablet_keeps_its_layout` (touch 820×1180) | picks by screen and pointer |
| `test_the_menu_opens_the_rail_and_closes` | rail as a menu; AC-2 |
| `test_the_top_bar_is_one_line_and_the_name_opens_the_details` | top bar one line; details; AC-3 |
| `test_the_sessions_page_is_the_list` | Sessions page is the list; AC-4 |
| `test_four_tabs_fit_360` | tabs fit; AC-5 |
| `test_the_composer_stays_at_the_bottom_with_a_gate_waiting` | composer at hand; AC-6 |
| `test_a_flow_events_text_wraps_whole` | event line wraps; AC-7 |
| `test_sideways_the_card_starts_minimized_and_a_tab_opens_it` (+ turning upright) | sideways card; AC-8 |
| `test_a_team_chip_opens_the_terminal_over_the_screen` | terminal fills the screen; AC-9 |
| `test_a_tap_on_a_kit_shows_its_tooltip_and_a_button_none` | tooltips on a tap; AC-10 |
| `test_the_kits_tabs_fit_360` | Kits tabs fit; AC-11 |
| `test_no_page_scrolls_sideways[360x780, 390x844, 430x932, 844x390]` (every rail page and the session's tabs) | AC-12 |

- [ ] Check: `uv run pytest -m ui tests/ui/test_phone.py`.

## Task 9: Docs

- [ ] `docs/design/ui.md` section "Phone layout (decided 2026-10-18, LAD-95)", one line
  each in Structure (the rail) and Session head; CHANGELOG.md `## 0.41.0 (unreleased)`;
  BACKLOG.md: drop "The UI scrolls sideways on a phone-wide screen" and "An image in the
  artifact's tab is sized by `vh` while the tab is `dvh`".
- [ ] Check: `openspec validate --specs --strict`.

## Task 10: Regression

- [ ] `make lint`, `make test` (no Python change expected; it must stay green), `make web`
  (vitest, tsc, stale types), the whole UI e2e suite file by file as the settings' Checks
  run it — at least `tests/ui/test_main_screen.py`, `test_layout.py`, `test_session_head.py`,
  `test_session_list.py`, `test_sessions_strip.py`, `test_chat.py`, `test_gates.py`,
  `test_terminal_panel.py`, `test_artifacts_tab.py`, `test_kits_page.py`,
  `test_needs_you.py`, `test_selection.py`, `test_phone.py` — all passing unchanged but the
  new file (AC-13). CI runs the rest.
