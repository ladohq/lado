## 1. The tab bar (web)

- [x] 1.1 `tests/ui/test_narrow_layout.py`: a failing test first,
  `test_a_late_font_leaves_the_tab_reached_clear`: the setup of
  `test_tab_brings_each_tab_clear_of_the_bars_ends` (1440 px, a running session, the bar
  300 px, `data-fit` 4), with `page.route("**/*.woff2", ...)` holding the font responses from
  before the page opens; Tab from the first tab to Artifacts, each tab `CLEAR`; then the held
  routes continue, the test waits for `document.fonts.status === 'loaded'`, asserts the row's
  `scrollWidth` changed (the test reproduces), Artifacts is `CLEAR`, › has count 0 and ‹ is
  visible (AC-1, AC-3).
- [x] 1.2 `tests/ui/test_narrow_layout.py`: `test_wider_tabs_keep_the_tab_shown_clear`: the
  same setup, Flows shown by a click (not the keyboard), then a style tag
  `.session-tabs .tab-item { letter-spacing: 1px }`; the row's `scrollWidth` grows and Flows is
  `CLEAR` (AC-2).
- [x] 1.3 `web/src/Sessions.tsx` by D1–D3: `keepTabInView(row)` (the `:focus-visible` tab of
  the row, else `aria-current="page"`; `keepInView`, then `lookAtEnds`), called by `choose`
  after the level is set and by the `[tab, fit]` effect; update the comments of `SessionTabs`
  and of the effect. `make web` green; 1.1 and 1.2 pass.

## 2. Documents and regression

- [x] 2.1 `docs/design/ui.md`, the session's tabs (`data-fit`, about line 3784): the tab
  reached by the keyboard, else the tab shown, stands clear again when the tabs or the bar
  change width (a late font, a resize) (LAD-267) (AC-4).
- [x] 2.2 CHANGELOG.md, `## 0.46.1 (unreleased)`, `### Fixed`: the session's tabs keep the tab
  in view when their width changes, e.g. as the font arrives (AC-4).
- [ ] 2.3 Repeat run under load (AC-3): `test_tab_brings_each_tab_clear_of_the_bars_ends` and
  the two new tests, each parametrized 48 times in a scratch file not committed, with
  `-m ui -n 16` while 8 CPU-bound loops run; plus `tests/ui/test_narrow_layout.py` whole with
  `-m ui -n auto` three times. Report the counts in `build-report`.
- [ ] 2.4 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_narrow_layout.py tests/ui/test_tabs.py tests/ui/test_layout.py`,
  `openspec validate tab-row-keeps-tab-in-view --strict` and the trial archive of the
  settings' Checks.
