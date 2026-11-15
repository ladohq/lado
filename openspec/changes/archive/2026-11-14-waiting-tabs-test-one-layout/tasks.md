## 1. The test

- [x] 1.1 `tests/ui/test_chat.py`, `test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways`:
  `check()` reads in one `row.evaluate` (or `card.evaluate`) the tabs' tops, the shown
  tab's box, the panel's box, the row's box and the expand button's box, and asserts on
  that one layout as today (one line within 1.5 px; the tab's bottom on the panel's top
  within 1.5 px; the tab inside the row's view; the row left of the expand button). It
  returns the expand button's x, which replaces the separate `expand.bounding_box()` reads
  before and after the click (AC-1). Check: `uv run pytest -m ui -n0 <node id>`.
- [x] 1.2 Same test: before each `check()`, wait until the card has settled: a
  `page.wait_for_function` (polling on animation frames) that is true once the card's,
  the shown tab's and the panel's boxes are the same in two frames in a row, its failure
  saying the waiting card did not settle (AC-2). A comment says why: after a tab click the
  card takes the new question's height over several tasks (LAD-283). Check: as 1.1.
- [x] 1.3 Prove it still catches a defect (AC-3): in the working tree only, give
  `.waiting-tabs-row` a `margin-bottom: 20px` in `web/src/styles.css`, rebuild (`make
  web`), run the test: it fails on the panel's line; then `flex-wrap: wrap` on
  `.waiting-tabs` (five tabs do not fit, so they wrap): it fails on the one-line check.
  Restore both and rebuild. Name both runs in the build report.
- [x] 1.4 Under load (AC-4): run the test 20 times in a row while the machine is loaded
  (e.g. `-n 4` over the node id repeated, or the test alone in a loop beside
  `uv run pytest -m ui -n 3 tests/ui/test_chat.py`); all green; note its time before and
  after the change. Put the commands and counts in the build report.

## 2. Backlog

- [x] 2.1 `BACKLOG.md`, the 2026-10-07 summary of flaky UI tests: the entry
  `test_layout::test_many_tabs_stay_on_one_line…` names `test_chat` and adds that its
  measurement race was fixed by LAD-283 (the click timeout there was the load). Check: read.

## 3. Checks

- [x] 3.1 `make lint`, `uv run pytest -m ui -n 2 tests/ui/test_chat.py`,
  `openspec validate waiting-tabs-test-one-layout --strict`, and the trial archive with
  `--skip-specs` (`.lado/sdlc.md`, Checks).
