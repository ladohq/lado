Task: LAD-283

## Why

`tests/ui/test_chat.py::test_many_tabs_stay_on_one_line_on_the_panel_and_scroll_sideways`
failed in `ui (2)` of CI run 43622855043 (pull request #302, LAD-270, which changed only a
smoke test) and passed on the rerun of the failed jobs:

```
AssertionError: ({'x': 715, 'y': 621.25, 'width': 143, 'height': 36},
                 {'x': 344, 'y': 685.75, 'width': 600, 'height': 144.25})
```

The shown tab's bottom (657.25) lay 28.5 px above the panel's top, where the test wants it
on the panel (within 1.5 px).

Cause (found by tracing the card's geometry in every frame in Chromium, the test's own
session and window): the failing check is the second one, after the click on the last tab
(x 715 is the row's right end, scrolled there). That tab's question is shorter than the
first one's, and the card, which takes its content's height at the bottom of the chat,
settles over several of the page's tasks: the panel goes from 340 to 144 px high and the
tab row from y 455 to y 650, then the card measures its parts again and `--waiting-rest`
changes from 189.25 to 180.25 px. The panel's box in the error, y 685.75 and 144.25 high,
is exactly the settled one; the tab's, 29.5 px above its settled place, is from a layout
before it. `check()` reads the tab's box and the panel's box with two separate
`bounding_box()` calls, each its own round trip to the browser, so under CI's load the two
boxes can come from two different layouts. In any one layout the tab lies on the panel: the
UI is right, the measurement is not.

LAD-266 fixed the same kind of race for the tabs' tops (read in one `evaluate`), but left
the tab-on-panel, the row's view and the expand button's place as separate calls.

## Options

1. **Read the whole check in one layout and wait for the card to settle** (chosen): one
   `evaluate` returns every box `check()` needs (the tabs' tops, the shown tab, the panel,
   the row and its visible width, the expand button), so they all come from one layout;
   before each check the test waits until the card's geometry is the same in two frames
   in a row. Long-term cost: a small helper in the test file; no product code.
2. **Only one `evaluate`, no wait**: fixes the assertion that failed, but the line
   `expand.bounding_box()["x"] == right` after the click and the dark screenshot still
   read a card that may be moving; the next flake of this test would be another line.
3. **Retry the test** (a rerun marker, or `expect.poll` around the boxes): hides the race
   instead of removing it, against the project's flake policy (no automatic retry inside
   pytest, `.lado/sdlc.md`).

## What Changes

- `tests/ui/test_chat.py`, the test above: `check()` takes all its boxes from one
  `evaluate` in the page (one layout), and before each `check()` the test waits until the
  card's box, the shown tab's and the panel's are unchanged over two animation frames; the
  comparison of the expand button's x before and after the click uses boxes from settled
  layouts too.
- `BACKLOG.md`: the 2026-10-07 summary of flaky UI tests names
  `test_layout::test_many_tabs_stay_on_one_line…`, which lives in `test_chat.py` now; its
  line gets the right file and a pointer to this fix (the click timeout there was the
  machine's load, not this race).

## Acceptance criteria

- AC-1: Every geometric assertion of the test compares boxes read in one `evaluate` (one
  layout); no assertion compares boxes from two `bounding_box()` calls.
- AC-2: Before each `check()`, the test waits for the card to settle (same geometry over
  two frames), with Playwright's default timeout and a message that says what did not
  settle.
- AC-3: The test still fails on a real defect: with the tab row given a margin below it
  (a gap between the tab and the panel), or with the row allowed to wrap, it fails; the
  developer tries both in the working tree and restores it.
- AC-4: The test passes 20 runs in a row under load (`-n 4` with three other copies of the
  UI suite's chat file, or an equivalent load), and its run time stays within a second of
  today's.

## Scope

- `tests/ui/test_chat.py` (the one test, and a helper in the same file if it needs one),
  `BACKLOG.md` (the one line).

## Out of scope

- The card's jump after a tab click (the tab row moves ~195 px down when a shorter
  question is chosen, as the card takes its content's height): a visible behaviour that
  `docs/design/ui.md` describes as intended (the card's height is the content's unless the
  human gave one); a change would be a product decision of its own, not this flake's fix.
  The reviewer may list it under "Found on the way".
- Other UI tests that pair two `bounding_box()` calls: none failed for it; each is fixed
  when it flakes, with its own cause.
- A retry of the test: against the flake policy (Option 3).
- A CHANGELOG line and a version bump: tests only, nothing LADO's users see.

## Impact

- Tests only: no product code, no schema, no MCP tool or CLI change; neither a minor nor a
  patch bump, no CHANGELOG line.
- No delta: no behaviour rule changes; archived with `--skip-specs`.
