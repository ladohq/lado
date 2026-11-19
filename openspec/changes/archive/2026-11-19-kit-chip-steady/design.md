## Context

`Launch.tsx` asks `getKits(root)` through `useAsked(root ?? "", …)`. `useAsked` returns `null`
whenever its key differs from the key of the answer it holds. `LaunchTeam` gets
`known={valueOf(kitList) ?? []}`, so each new key empties `known` until its answer comes. A
chip without a match in `known` shows its name alone: no version, no `invalid` class, no
title. Switching Where from `Project…` to `Other folder…` changes `root` more than once (the
project's repository, then the folder's in-between values, then the folder's root). Each change
empties `known` for 15–30 ms on a normal machine, longer under CI's load.

## Decisions

### D1. Keep the last kit list in `Launch.tsx`, not in `useAsked`

`Launch.tsx` keeps the last kit list that answered with a value (a `useState` set by an
effect on `kitList`, or a small `useLast` helper next to `useAsked`) and passes
`known={valueOf(kitList) ?? lastKits}`. `kitsError` stays tied to the current answer only.
A failed ask drops the kept list (the human's choice at merge_ok, option (a) of the review's
F1): the chips do not show another place's kits next to the error.
Reason: other users of `useAsked` (the folder check, providers, models) need "no answer while
asking" for their `Checking…` states. A change of `useAsked` itself would touch them all.

### D2. The test clicks relative to the button

`tests/ui/test_launch.py` replaces `page.mouse.click(x, y)` with
`remove.click(position={"x": drawn["width"] + 5, "y": drawn["height"] / 2})`. Checked by hand
on this branch's base: the click at 37×16 removes the kit. A click at 45×16 (past the 6 px
`::after`) times out because the button does not receive the press. So the test still proves
the 44 px hit area, and it no longer depends on when the layout was measured. Reason: raw
coordinates skip Playwright's stability and hit-target checks, which is what let the race
through.

### D3. Test layers

- Unit (`web/src/Launch.test.tsx`, vitest): the kit list of the next place held pending, the
  chip still reads `default 0.1.0` (or the version the mock gives) and is not re-rendered
  without it; the answer then replaces it. This is the lowest layer that catches the bug.
- UI e2e (`tests/ui/test_launch.py`): the phone test with the button-relative press. Nothing
  crosses processes, so no integration test is needed.

## Risks

- For a moment after Where changes, a chip can show the version or validity of the previous
  place's kit. Versions of one kit rarely differ between places, and the new answer replaces
  it within the request's time.
