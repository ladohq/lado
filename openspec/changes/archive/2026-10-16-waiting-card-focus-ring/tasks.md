## 1. Room for the ring (D1, D2, D3)

- [x] 1.1 `web/src/styles.css`: `--ring-room: 4px` on `:root` with its comment;
  `.waiting-list` `padding: var(--ring-room) 6px var(--ring-room) var(--ring-room)` and
  `margin: calc(-1 * var(--ring-room)) 0 0 calc(-1 * var(--ring-room))`;
  `.waiting-field` and `.answer textarea` `scroll-margin: var(--ring-room)` in place
  of `scroll-margin-bottom: 4px`. Check: `make web`; the UI e2e of section 2.

## 2. UI e2e (the requirement's scenarios, D4)

- [x] 2.1 `tests/ui/test_gates.py`: a measuring function (the ring's extent from the
  computed style, the box grown by it within the list's client area on each side, 0.5 px
  tolerance), and tests: the gate's comment focused (A gate's comment with the focus);
  12 lines typed (A long gate's comment, next to LAD-70's test); a 600 px wide window (A
  narrow window); the question's and the field's left edge against the panel's, and the
  Send row's top, equal to their values with the rule switched off by a style the test
  adds (Nothing moves). Screenshots of each (`shot`). Check: `uv run pytest -m ui
  tests/ui/test_gates.py -k ring`.
- [x] 2.2 `tests/ui/test_chat.py`: Other… picked, its field focused (An own answer with
  the focus); the first question marked from its line in the feed (The first question
  marked); the same measuring function, shared with 2.1 (a helper module of `tests/ui/`
  or imported from `test_gates.py`, as `test_main_screen.log_in` is). Screenshots.
  Check: `uv run pytest -m ui tests/ui/test_chat.py -k ring`.
- [x] 2.3 The tests catch the bug: 2.1's focused-comment test, run on main's
  `styles.css` (a temporary checkout of that one file, restored after), fails on the
  left side; name the run in the build report.
- [x] 2.4 `tests/ui/test_gates.py`: on the Flows tab's run page, a gate's comment of 12
  lines grown to the page's lower edge and scrolled into view by `.list-main` keeps its
  ring whole within it (review F1: the room must hold outside the waiting card too); seen
  red with the room on `.waiting-card` (the bottom cut by 3.5 px). Check: `uv run pytest
  -m ui tests/ui/test_gates.py -k flows_tab`.

## 3. Docs

- [x] 3.1 `docs/design/ui.md` (The waiting card, Fields: the list keeps room for a ring
  on every side, LAD-78, mockup `task/lad-78/mockup-focus-ring.html`; replaces "the list
  keeping room below it for the field's focus ring"), CHANGELOG.md (a line under 0.40.0
  (unreleased)).

## 4. Regression

- [x] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_chat.py
  tests/ui/test_gates.py`, `openspec validate waiting-card-focus-ring --strict`,
  `openspec validate --specs --strict`.
