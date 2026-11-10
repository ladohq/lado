## 1. The list and the strip (web)

- [x] 1.1 `web/src/Layout.test.tsx` (vitest): failing tests first. A row on hover and on keyboard
  focus shows no tooltip (AC-1). An icon's tooltip holds `.tip-top` and the state line and no
  `.tip-facts` or `.tip-hint`, for a titled session that needs the human, a working one, an
  idle untitled one, a session whose loop is down, and a session in trouble with a gate (two
  lines) (AC-2,
  AC-3); Esc hides it. The tests of the row's card and of its facts ("a row's card on focus and
  hover…", "a titled row's card…", "a card names the project…", "a project's new title … in the
  open card", "a card shows six kits…", "a card says how to go on…") are removed or turned into
  icon tests of what stays; the state-line tests ("a card's state line…") check the icon only.
- [x] 1.2 `web/src/Sessions.tsx` by D1 and D2: `SessionRow` without `Tooltip`; `SessionTip` with
  the title line, `TipState` and the trouble's `Needs you` line only; `TipState` without its `stopped` branch,
  `SessionTip` without `useRanParts`; remove `HOW_TO_GO_ON`,
  `KITS_SHOWN` and what only they used; fix the comments that name the row's card.
  `web/src/styles.css` by D3. `make web` green (lint, tsc, vitest, build).

## 2. In a browser (UI e2e)

- [ ] 2.1 `tests/ui/test_session_list.py`: `test_a_row_shows_its_sessions_card_under_the_pointer`
  becomes: hovering a row at 1440×900 shows no tooltip after 500 ms and its computed `cursor` is `pointer` (AC-1); folded, hovering the
  calm session's icon shows its name and `idle`, with no `dt` and no `.tip-hint`, and the stopped
  session has no icon (AC-2); its width is at most 320 px. Screenshots of the icon's
  tooltip and of a hovered row as run artifacts.
- [ ] 2.2 `tests/ui/test_session_list.py`, the `tabs` fixture and its five tests by D4: the list
  folded, the trigger is the session's icon in the strip; each test keeps its scenario (AC-4).
- [ ] 2.3 Grep `tests/ui/` for the row's card (`.tip-facts`, `.tip-hint`, `session-tip`, a
  tooltip after hovering a session row) and fix every hit.

## 3. Documents and regression

- [ ] 3.1 `docs/design/ui.md`: the session list's paragraph says a row shows no tooltip (LAD-264)
  and drops the card's description; the strip's paragraph says an icon shows a short tooltip
  (title, name, state line; a trouble's `Needs you` line), right of it, the tooltip's width; the
  Tooltip paragraph (about line 1418) no longer names the session's card. Grep `docs/design/` for
  `SessionTip` and "session's card" and fix every hit.
- [ ] 3.2 CHANGELOG.md, `## 0.45.1 (unreleased)`, Changed: hovering a session in the list no
  longer opens a card over the chat; an icon of the folded list shows the session's name and
  state; the rest is in the details of the session's title (AC-5).
- [ ] 3.3 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_session_list.py tests/ui/test_sessions_strip.py tests/ui/test_layout.py
  tests/ui/test_narrow_layout.py`, `openspec validate short-session-tip --strict` and the trial
  archive of the settings' Checks.
