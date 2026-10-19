## 1. The recorder

Redesigned a third time: neither probe made the second Esc miss in Chromium on the code
before any fix (CI runs 39246518194, 39250165796) and the test passed 100 times in CI
(39250945744); the human chose to record the next real failure and leave the UI as it is.

- [ ] 1.1 `tests/ui/test_chat.py`: remove `test_a_second_esc_while_the_page_is_busy_folds_the_card`
  (commit f6d341c); the branch's diff of the file against its target then holds only the
  recorder.
- [ ] 1.2 `tests/ui/test_chat.py`, next to `on_top` and `asked_with_a_plan`: a helper that
  installs the recorder with `page.add_init_script` (call it before `page.goto`) and a
  context manager that, on an exception, prints the record and the card's `outerHTML`
  and re-raises (nothing printed on a pass). The page script keeps `window.__escRecord`,
  each entry with `performance.now()` rounded to 0.1 ms: `keydown` on `window` in the
  capture phase (key, `isTrusted`, target and active element described as tag, `id`,
  `class` and `aria-label`, `location.search`, the `.waiting-card`'s class or none,
  whether an `.artifact-panel` is in the page) and again in the bubble phase with
  `defaultPrevented`; a `MutationObserver` on `document` for the `.waiting-card`'s class
  changes and its mounts and unmounts; `pushState`, `replaceState` and `popstate` with
  the new query. The docstring says why: LAD-99's flake, its cause not found (AC-1,
  AC-2).
- [ ] 1.3 In `test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`:
  install the recorder before `page.goto` and wrap the test's steps from the expand click
  to its end in the context manager; the steps and checks themselves stay as they are.
- [ ] 1.4 By hand, in CI: one temporary commit, not for merge, that presses another key
  instead of the second `Escape`; read the failure's report in the ui job, quote the
  record in the build report, then revert the commit (AC-3).

## 2. The backlog

- [ ] 2.1 BACKLOG.md, P2, in its own commit: "The expanded waiting card sometimes stays
  expanded after the second Esc", `Size: S`, `Why here:` a UI flake seen once,
  100 of 100 green in a focused CI run; the run 39150756993, what the probes ruled out (the passive-effect gap in
  Chromium), that the test prints its record on failure (LAD-99), the unpushed
  `useLayoutEffect` candidate (branch `lad-99-backup`, commit 99b32ad), and what to do
  when it fails again: read the record and file a task with it. Found: 2026-10-18, CI of
  e859751.

## 3. Checks

- [ ] 3.1 `make lint` passes; `uv run pytest -m ui --collect-only tests/ui/test_chat.py`
  lists the test and not the probe; CI is green on the pull request's last commit (AC-4).
