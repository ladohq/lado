Task: LAD-42

## Why

A session's page shows an empty strip, 16 px high, between the top bar and the session's
tab bar (Activity | Agents | Flows | Artifacts). It is `.session-main`'s top padding
(`padding: 16px var(--main-pad)` in `web/src/styles.css`), which kept the session's head
apart from the tabs while the head stood on the page. Since feature/session-head-topbar
(2026-10-08) the head is the top bar's line, and the padding was left behind: nothing is
drawn in it but, right after a start or resume with new settings, problems or warnings,
the start notice (`StartedNotice`, `.started-notice`). It also sets the session's tab
band 16 px lower than the terminal panel's, whose band starts right under the top bar.

## What Changes

- **No strip** (`web/src/styles.css`): `.session-main` has no top padding; its sides and
  bottom stay as now (`0 var(--main-pad) 16px`). The session's tab band starts right
  under the top bar, level with the terminals' band (both: 5 px of band above the tabs),
  in the wide and the narrow window alike. Approved mockup
  `mockup-session-tabs-strip.html`, screens 2 and 2a.
- **The start notice stays above the tabs** (`.started-notice`): with its own 12 px above
  it, under the top bar, and its 10 px below as now; the tabs move down while it is open,
  as now. Mockup screen 4.
- docs/design/ui.md: Look, Tabs (the session's band right under the top bar, level with
  the terminals') and Sessions (the start notice above the tabs).
- CHANGELOG.md: a line under `## 0.37.1 (unreleased)`.

## Scope

The top of a session's page in the web UI: `.session-main`'s padding and the start
notice's margin. Nothing in the core, the API, the MCP tools or the schema.

## Out of scope

- Option B, a smaller strip (8 px): the strip would stay empty and the two tab bands
  would still not line up (the human chose A).
- Option C, the strip filled with the band's ground (a taller band): the empty room
  stays, only grey.
- The start notice under the tabs (mockup screen 3): the human kept it above the tabs.
- Other pages' top padding (`.content`'s 28 px on Needs you, Kits, Settings…): they have
  no tab band under the top bar beside a terminal panel, and the task is about the
  session's page.

## Acceptance criteria

- AC-1: On a session's page (any tab), the session's tab bar starts right under the top
  bar: no gap between the top bar's bottom edge and the tab band's top edge.
- AC-2: The session's tab band and the terminal panel's band have the same top, and the
  selected session tab and the selected terminal tab the same top, in the light and the
  dark theme.
- AC-3: In a window of 900 px or less, the session's tab bar also starts right under the
  top bar.
- AC-4: The start notice, when shown, stands above the tab bar with a 12 px gap under the
  top bar and a 10 px gap above the tabs; closing it puts the tabs back right under the
  top bar.
- AC-5: The sides and the bottom of the session's column, the tabs' look (Look, Tabs) and
  every tab's content are as before.
- AC-6: docs/design/ui.md and CHANGELOG.md say so; the UI e2e tests check AC-1 to AC-4 and
  pass, and the existing tab and layout tests pass.

## Impact

- `web/src/styles.css`, `tests/ui/test_tabs.py`, `tests/ui/test_launch.py` (or the file
  that tests resuming with new settings), `docs/design/ui.md`, CHANGELOG.md.
- No API, schema or MCP change: a fix, the patch (0.37.1).

## Decisions for the record

- Scale tweak: one padding and one margin of known shape; review as a tweak.
- No delta spec: no living spec under `openspec/specs/` covers the session page's layout
  (docs/design/ui.md does); `skip_specs: true` in `.openspec.yaml`, archived with
  `--skip-specs`.
- The padding goes from `.session-main` rather than a negative margin on `.session-tabs`:
  the band's rule says no negative margins up and down (docs/design/ui.md, Look, Tabs),
  and one source for the column's top keeps the notice and any page above the tabs right.
- The notice gets its own top margin rather than the column keeping a padding for it: it
  shows rarely, and the strip should not exist for it the rest of the time.
- Tested in the UI e2e layer only: the gap is layout, which vitest's jsdom does not lay
  out; the check measures boxes (`getBoundingClientRect`) in Chromium.
