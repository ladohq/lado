## 1. The strip goes

- [x] 1.1 `web/src/styles.css`: `.session-main` padding `0 var(--main-pad) 16px` (no top
  padding), its comment saying the tab band starts right under the top bar, level with
  the terminals' band; check the narrow window's `.session-main` rule (900 px or less)
  adds none. Check: `make web`; the mockup's screens 2 and 2a.
- [x] 1.2 `web/src/styles.css`: `.started-notice` margin `12px 0 10px` (12 px above it
  under the top bar, 10 px above the tabs as now). Check: mockup screen 4.

## 2. Docs

- [x] 2.1 `docs/design/ui.md`: Look, Tabs: the session's band starts right under the top
  bar, level with the terminals' band (no top padding in `.session-main`, LAD-42,
  2026-10-14); Sessions: the start notice stands above the tabs with 12 px under the top
  bar. Check: read through.
- [x] 2.2 `CHANGELOG.md`: under `## 0.37.1 (unreleased)`, a line: the empty strip above a
  session's tabs is gone; the tabs start right under the top bar, level with the
  terminals' tabs.

## 3. Tests

- [x] 3.1 `tests/ui/test_tabs.py`: in the session test, for each theme, the session tab
  band's top equals the top bar's bottom and the terminals band's top, and the selected
  session tab's top equals the selected terminal tab's top (AC-1, AC-2); a narrow window
  (e.g. 800 px wide) where the band's top equals the top bar's bottom (AC-3), with a
  screenshot. Check: `uv run pytest -m ui tests/ui/test_tabs.py`. Done so in the wide
  window; in a narrow one the session list (or its strip) stacks between the top bar and
  the session, so there the band's top equals the column's top and the list's bottom,
  with the list open and collapsed.
- [x] 3.2 A UI test of the start notice (`tests/ui/test_launch.py`): resume a stopped
  session with a changed setting in the Resume window (e.g. the permission mode), so
  "Resumed with new settings" shows; the notice's top is 12 px under the top bar's bottom,
  the tab band's top 10 px under the notice's bottom; after Close the band's top equals
  the top bar's bottom (AC-4); a screenshot. Check: `uv run pytest -m ui
  tests/ui/test_launch.py`.
- [x] 3.3 Regression: `uv run pytest -m ui tests/ui/test_tabs.py tests/ui/test_layout.py
  tests/ui/test_session_head.py tests/ui/test_launch.py tests/ui/test_chat.py`, `make web`,
  `make lint` (AC-5, AC-6).
