## Context

`web/src/useScrollAnchor.ts` holds the element the human acts on in a section (Settings →
Model servers, Settings → Git servers) at its place on the screen: after each render and each
size change of the section it scrolls the container (`.content` above 900 px, the window at or
under it) by what the anchor's distance from the section's top gained. Near the container's
end it already counts the browser's own clamp (`stopped`: the position fell from where it was
noted while the page is at its end) so as not to correct twice. Two gaps remain at the end:

1. A change below the anchor: its distance from the section's top is unchanged (`moved` is 0),
   so `settle` does nothing, though the clamp moved the whole section down by `stopped`.
2. Any correction whose target lies past the container's new end: `scrollTo` stops at the end,
   and the anchor is left short.

## Decisions

- D1. The blank room is bottom padding on the hook's section, set inline by the hook
  (`section.style.paddingBottom`). The section's CSS (`.spage`) sets no bottom padding, so the
  inline value is the room alone. Why: the hook already owns the section; no component has to
  render a spacer, so Git servers gets the rule without a change, and the room sits at the end
  of what the container scrolls whichever container it is.
- D2. In `settle`, a held anchor in view acts on `moved + stopped !== 0` (no longer only on
  `moved !== 0`): a clamp with nothing moved inside the section is a move to make up for. The
  target is computed as today (`want`); when it exceeds the container's largest scroll
  (`scrollHeight − clientHeight`, `document.documentElement`'s and `innerHeight` for the
  window), the padding first grows by the difference, then `scrollTo(0, want)` runs. With a
  target within reach nothing new happens (AC-4).
- D3. On each `scroll` event of the container (listened passively while the hook is mounted),
  a padding above 0 shrinks to the part of it in view: `pad − (scrollHeight − position −
  view height)`, never below 0. The part below the view goes; the part in view stays, so
  nothing that shows moves. Scrolled up past it, it is 0 and the page ends at its last block.
  The padding is not trimmed while it is wholly in view, since then nothing of it is out of
  view. The same event notes where the page is, so `stopped` counts only the browser's stop,
  never a scroll of the human's (review F1); a scroll event at a nearer end than the one
  noted is that stop, told before the section's resize settles, and is not noted.
- D4. The hook's cleanup sets the padding back to empty, so a section kept mounted but no longer
  using the hook leaves no room; a section that leaves the page takes it along anyway.
- D5. The padding's own size change reaches `settle` through the `ResizeObserver`; the anchor's
  distance from the section's top does not change with it, and the position is where the hook
  put it, so that round scrolls nothing. The hook's `ours` record (the exact place it wanted)
  stays as it is: the padding is what makes that place reachable.
- D6. No room is added when nothing is held (no focus or press in the section, an anchor out of
  view): the rule stays "only what the human acts on is held".
- D7 (found while building). Add server's form closing takes the pressed button with it, and
  nothing `[data-anchor]` held it, so nothing was held when the page got shorter. The list of
  servers (`ul.mx-srcs`, on Model servers and Git servers) is now `data-anchor`: its top does
  not move when the form under it closes, and a server's own elements still find their row
  first. The page may also be left too short to scroll at all: `atEnd` counts that as the end
  (a stop shows only as a position below the one noted), and a container that short reports
  its view's height as `scrollHeight`, so the room is measured again once the page scrolls.

## Root cause against the principles

- One source of truth: the room is derived each time from the container's real sizes, no
  second record of the page's height.
- Neutral core: web UI only, no provider involved.
- Only what is used: no option or prop; the hook's two users need the same rule.
- ROADMAP: no coming stage changes the settings pages' layout; the hook stays the one place of
  the rule.

## Tests

- Unit (`web/src/useScrollAnchor.test.tsx`, vitest, jsdom with the test's own geometry): the
  test's browser imitation gains a container height and a content height so that `scrollTo`
  clamps at the end and a padding change lengthens the content.
  - "at the page's end, a form below the anchor shrinking: the section gets the lost height as
    padding and the anchor keeps its place" (AC-1, AC-2 at hook level);
  - "a correction past the end above the anchor: padding makes it reachable";
  - "the human's scroll up trims the padding to what is in view; scrolled past it, none is
    left" (AC-3);
  - "with room to scroll under the anchor no padding is added" (AC-4);
  - "nothing held: a shrink at the end adds no padding" (AC-5);
  - the existing tests stay green, among them "at the page's end the browser's own stop makes up
    for what went above: no second correction".
- UI e2e (`tests/ui/test_models_section.py`, Chromium, needs real layout and scroll):
  - `test_a_server_added_ticked_renamed_unticked_refreshed_and_removed`: the injected style
    keeps `margin-top: 600px` and loses `margin-bottom: 1200px`; the window is scrolled to the
    page's very end before Add server and before the Remove confirm; `stays(...)` as now
    (AC-1);
  - a new test: a saved server's Change opened at the page's very end, Save: the server's row
    keeps its place; then the wheel up by a little and back down to the end: the page ends at
    the last block's bottom (the section's padding back to 0) (AC-2, AC-3).
- Regression run: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_models_section.py tests/ui/test_git_servers_section.py`, `openspec validate
  page-end-keeps-place --strict`, the trial archive.

## Version

A patch: a fix of the web UI, no API, CLI, MCP or schema change.
