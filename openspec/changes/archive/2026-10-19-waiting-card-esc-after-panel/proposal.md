Task: LAD-99

## Why

Symptom: `tests/ui/test_chat.py::test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`
failed once at its second Esc (CI run 39150756993, attempt 1, commit e859751, job ui (2),
`uv run pytest -m ui -n 2 --shard 2/2`): the artifact panel was gone, the chip had the
focus, the card was expanded, and after the second Esc it stayed `waiting-card expanded`
for the whole 5 s (14 checks). The rerun passed. The failure's aria snapshot showed the
card's tab list with no tab and an empty tab panel, which may be a sign of an odd state or
only a shortened snapshot.

The cause is not found. Suspected first: the expanded card listens for Esc only while no
artifact panel is open, and adds that listener in a passive effect, which after the
router's transition (React Router 8 runs navigations in `startTransition`) comes in a later
task than the commit that removes the panel; an Esc in between would be lost. The gap is
real in jsdom with React's real scheduler, but not in Chromium:

- an Esc sent from a `MutationObserver` right after the panel's removal folded the card
  on the code before any fix (CI run 39246518194);
- with React's scheduler tasks (`MessagePort.prototype.postMessage`) delayed by 1000 ms
  from the first Esc on, the delay checked to take effect, the second Esc still folded
  the card (CI run 39250165796);
- the test itself, run 100 times in one CI run with a log of every Esc, passed 100 times
  (CI run 39250945744).

The flake is rarer than 1 in 100, and nothing in the code explains it. Changing the UI
for an unproven cause would also hide whether it helped. What is missing is data from a
real failure, and the test gives none: it only says the card stayed expanded.

## What Changes

- The test records, in the page, every keydown (before and after the page's listeners),
  every change of the waiting card's class, the card's mounts and unmounts, and each
  change of the address; on a failure it prints that record and the card's HTML, on a
  pass it prints nothing. The next failure in CI then carries the data for a new task.
- The probe test `test_a_second_esc_while_the_page_is_busy_folds_the_card` (pushed on the
  pull request's branch during the first builds) goes: it passes with or without the
  suspected gap, so it guards nothing.
- BACKLOG.md gets an entry for the flake that says where its record is printed.

## Scope

`tests/ui/test_chat.py` (the recorder in the one test, the probe removed) and an entry in
BACKLOG.md. Nothing in `src/` or `web/`.

## Out of scope

- `useLayoutEffect` for the card's and the panel's Esc listeners, as a fix for safety:
  no test turns red without it, and with it a later failure would not tell whether it
  helped; the human chose the recorder alone. It stays on the local branch `lad-99-backup`
  (commit 99b32ad) for the task the record may lead to.
- More CI runs under artificial load: at a rate below 1 in 100 the chance to catch it is
  small and each run costs about 6 minutes of CI.
- A wait or retry in the test before its second Esc, or a rerun plugin in pytest: the
  test waits for what the human sees, a wait would hide a real defect, and the task
  forbids retries.
- A recorder shared by all UI tests (a fixture in `tests/ui/conftest.py`): one test needs
  it now (AGENTS.md, "Only what is used").
- Logging in the UI's own code (`console.debug` in `WaitingCard.tsx`): the recorder sees
  enough from outside, through DOM events, and the shipped UI stays clean.
- A screenshot on failure: the record and the card's HTML say more about the state, and
  the CI job keeps no screenshots as artifacts.

## Acceptance criteria

- AC-1: When the test fails at its second Esc, or at any check after the recorder is set
  up, pytest's report of the failure shows the record (one line per entry, oldest first,
  each with its time) and the card's HTML; when it passes, its output has neither.
- AC-2: The record holds, for each keydown, the key, `isTrusted`, the target and the
  focused element, the address's query, the card's class and whether an artifact panel
  is in the page, both before the page's own listeners and after them, with
  `defaultPrevented` after; each change of the waiting card's class; each mount and
  unmount of the card; each `pushState`, `replaceState` and `popstate` with the new query.
- AC-3: Shown by hand once in CI, not committed: with the test's second `Escape` replaced
  by another key, the test fails and its report shows the record and the card's HTML (the
  build report quotes the record; the probe is reverted).
- AC-4: The probe test is gone; the test passes in CI with the recorder; `make lint`
  passes; CI is green on the pull request's last commit.

## Impact

- `tests/ui/test_chat.py`, BACKLOG.md. No API, schema, MCP, CLI or UI change; no
  CHANGELOG.md line (nothing users see) and no version bump.
- No delta: no behaviour rule changes; the change is archived with `--skip-specs`.
- The parallel task LAD-102 edits `tests/ui/test_chat.py`: the recorder's helper goes next
  to the test's other helpers (`on_top`, `asked_with_a_plan`), so a conflict, if any, is
  small.
- The pull request closes LAD-99 without a found cause: its description and the merge
  comment say so and point at the BACKLOG.md entry.

## Decisions for the record

- Scale stays hotfix (the branch and review depth of the earlier visits); the change is
  now test-only, reviewed by precision.
- The recorder is in the test, through `page.add_init_script`: its window `keydown`
  listener in the capture phase runs before every listener of the page, one in the bubble
  phase after all of them (the page's are on `document`), so `defaultPrevented` there
  tells whether the card's listener, which calls `preventDefault`, ran.
- A `MutationObserver` on `document` (subtree, `childList` and the `class` attribute)
  sees the card's class changes and its mounts and unmounts; wrapping
  `history.pushState`/`replaceState` and listening to `popstate` sees the address, which
  carries the panel (`?view=`).
- Printing goes through the test's own `try`/`except`: on an exception it prints the
  record with `print` and re-raises, so pytest shows it under the failure's captured
  stdout, as the test's screenshots' paths already are.
- AC-3's probe is the cheapest way to see the report in a real run without waiting for
  the flake.
- Test layer: UI e2e, the test itself; nothing at a lower layer can see the browser's
  events.
