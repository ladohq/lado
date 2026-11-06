Task: LAD-222

## Why

Symptom: `tests/ui/test_narrow_layout.py::test_the_strips_badges_tell_task_sessions_apart`
fails with `AssertionError: assert False` at line 297, the check that the text of the badge
`154·2` fits its box. Seen in a local parallel run on LAD-197 and in CI on PR #232 (run
42279198936, attempt 1, job `ui (2)`), a pull request that did not touch the test; the rerun
of the failed jobs passed.

Cause, confirmed on 2026-11-06: the test measures the text while IBM Plex Mono is still
loading; the product is right. The badge's text is 5 characters of 10 px, and the font's
characters are 6 px wide, so the text is exactly 30 px in the badge's 30 px of inner width.
The fallback font is 30.109375 px, so the same check is false until the font arrives. Nothing
in the test waits for it: `expect(...).to_have_text` passes as soon as the text is in the page.

A throwaway test measured the badge at the moment the check runs, six runs:

    [30.109375, 30, 'loading']   three runs
    [30,        30, 'loaded']    three runs

It is not only a matter of load, as the task and BACKLOG.md supposed: the unchanged test,
run alone with `-n0` five times, failed once, at line 297.

The fallback's excess of 0.11 px lasts until the font arrives, and no user can see it.

Options weighed:

- A (taken): before the check, ask the browser to load the font the badge uses, with
  `document.fonts.load(getComputedStyle(e).font, e.textContent)`, and wait for its promise.
  It names no font: it follows the badge's own style. Long-term cost: a second way of waiting
  for fonts beside `test_team_head.py`'s, in one line.
- B: the line of `test_team_head.py`,
  `document.fonts.status === 'loaded' && document.fonts.size > 0`. It held in six runs with the
  font's response delayed by 0.7 s. But `status` says only that nothing is loading now: Inter
  is loaded first, and until the browser has laid out the badge IBM Plex Mono is not loading
  yet, so a narrower race stays, and this task would come back.
- C: retry the check until it is true. It needs no knowledge of fonts, but a badge that
  overflows for a moment would pass, and the check is about the text that stays.
- D: give the badge room in the product (a smaller font, a wider box), so that the fallback
  fits too. It changes the look of every long badge to spare a test, and no user sees a
  difference.

## What Changes

- The test waits for the font of the badge `154·2` before it measures the text.
- The entry "Flaky UI test: `test_the_strips_badges_tell_task_sessions_apart`" leaves
  BACKLOG.md, since its cause is fixed.

## Scope

- That one test in `tests/ui/test_narrow_layout.py`.
- That one entry of BACKLOG.md.

## Out of scope

- `web/src/styles.css`: the behaviour is right (Why, option D).
- `test_team_head.py`'s wait for fonts: it has not failed, and its checks are other ones.
- A shared helper for waiting for fonts: one test needs this wait now (AGENTS.md, Only what
  is used).
- The entry just above it in BACKLOG.md, "Flaky: an OpenCode test of `LoginSheet.test.tsx`": another
  test and another cause.
- Other tests that measure text without waiting for fonts: none is known to flake, and each
  would have to be shown to depend on the font first.

## Impact

- Tests and BACKLOG.md only. No behaviour rule changes, so there is no delta; archive with
  `--skip-specs`. `docs/design/ui.md` does not change: the screen does not.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the
  patch rule at most).
- Neutral core, one source of truth, no silent drops: untouched, as `src/` and `web/` do not
  change.
