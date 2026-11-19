Task: LAD-298

## Why

The UI test `test_on_a_phone_every_field_and_button_of_the_window_is_a_44_px_target` fails at
random in CI: a press 5 px right of the drawn × of the kit chip `default` does not remove the
kit. Recorded frame by frame on a 390×844 screen, after Where goes from `Project…` back to
`Other folder…`, the chip loses its version `0.1.0` and gets it back twice within about
350 ms, and its × jumps 30 px left and right with it (x 119 → 89 → 119 → 89 → 119).

The cause is in the window, not the test. The window asks for the kit list once per place
(`getKits(root)` through `useAsked`), and the place passes through several values while Where
settles. `useAsked` gives no answer while a new key's request is out, so the chips lose their
versions (and an invalid kit its strike-through) until it comes. The test measures the × once
and presses raw page coordinates later. When the version has gone between the two, the press
falls 30 px past the narrower chip's 44 px hit area. A person sees the same blink, and a
finger aimed at the × can miss it in the same way.

The human chose to fix the window and the test together (#7562).

## What Changes

- **A kit chip keeps its look while the kit list is asked again.** Until the answer for the
  new place comes, Kits shows the chips by the last kit list the window has: version,
  strike-through of an invalid kit, its problem as the title, and the kits `+ Add kit` offers.
  The new answer then replaces it. A failed ask still shows its error at once.
- **The test presses the × through the button.** It clicks the button at a position 5 px past
  its drawn right edge, relative to the button at the moment of the press, instead of page
  coordinates measured earlier. Playwright waits for the button to stand still and checks
  that the press lands on it (its 44 px `::after`). A miss now fails with "intercepts
  pointer events" rather than an unexplained count of 1.
- **A unit test of the window** proves that the chip keeps its version while the next place's
  kit list is pending.
- CHANGELOG: a line under 0.48.0's Fixed.

## Scope

In: `web/src/Launch.tsx` (the kit list kept until the next answer), `web/src/Launch.test.tsx`,
`tests/ui/test_launch.py`, `docs/design/ui.md` (Kits' line), CHANGELOG.md.

## Out of scope

- **Fewer asks of the kit list while Where settles** (no in-between place): with the chips
  steady the extra asks are invisible, and `root`'s in-between values come from the folder
  check and the project pick, which other features depend on. Reason: a wider change for no
  visible gain.
- **The very first kit list of an opened window**: before any answer the chip has no version
  to keep, so it still grows once when the first answer comes. It happens once, before the
  human usually reaches Kits, and is no regression.
- **`useAsked` keeping the last answer for every caller**: the folder check, the providers
  and the models rely on "no answer while asking" to show `Checking…` and similar states.
  Reason: changing them all is a risk outside this defect.
- **Other flaky UI tests**: each is its own task.

## Impact

- Users see no blink of a kit chip's version, and its × stays put, when they change Where.
- Version: patch (a fix); it goes under 0.48.0 (unreleased), already a minor.
- No API, MCP, CLI or schema change; `web/openapi.json` is unchanged.
