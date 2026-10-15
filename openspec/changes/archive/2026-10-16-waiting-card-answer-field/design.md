## Context

The waiting card (`WaitingCard.tsx`, docs/design/ui.md, The waiting card) holds an agent's
questions in `.waiting-list`, which scrolls (`overflow: auto`) under the fixed Send row,
and a gate's panel (`GateCard.tsx`'s `GatePanel` with `inTab`) in the same list. Its text
fields are fixed: the own answer and the Skip comment `rows={1}`, the gate's comment
`rows={2}`, both with `resize: vertical` (`.waiting-field`, `.answer textarea`). The
composer's field sizes itself by its text (`Composer.tsx`'s `grow`, `COMPOSER_LINES = 8`,
in a `useLayoutEffect` on the text).

Options held against AGENTS.md's Design principles and ROADMAP: neutral core (UI only, no
provider involved); one source of truth (the composer's rule shared, not copied: D1); no
silent drops (a long text scrolls inside the field, nothing is cut); only what is used (no
setting, no per-view range). Stage 7's desktop app shows the same web UI.

1. **Chosen: height by text, 3 to 8 lines** (option A). Cost: one shared rule, already
   proven in the composer; a field that grows moves what is below it, which D3 handles.
2. A fixed 4-line field (option B): no code beyond CSS, but a short answer wastes room and
   a long one shows in pieces.
3. The field in the Send row: one row for several questions; refused.

## Decisions

### D1. One height rule, taken out of the composer

A module `web/src/fieldHeight.ts` with `grow(field, least, most)`: the field's height is
its `scrollHeight`, at least `least` and at most `most` lines (by the computed
`line-height`, plus padding and border), `overflow-y: auto` only above `most`, else
`hidden`. A hook `useGrow(ref, text, least, most)` runs it in a `useLayoutEffect` on the
text. The composer uses it with 1 and 8 (`COMPOSER_LINES` moves with it as the shared
most), so there is one rule, not a copy. Reason: the composer's rule is the one the human
knows and is tested.

### D2. 3 lines least, 8 most, in every view

The card's fields take 3 and 8; the expanded card and Needs you the same. Reason: 3 lines
say "write here" without the one-line look of the task; 8 is the composer's, so the two
places to write look alike; a range per view would be a setting no one asked for.

### D3. The lower edge stays in view by `scrollIntoView({ block: "nearest" })`

After `grow`, when the field is the focused element and its height grew, the hook calls
`field.scrollIntoView({ block: "nearest" })`. In the card the nearest scrolling box is
`.waiting-list`, so the list scrolls by as much as the field passed its edge; on a narrow
window, where the page scrolls, the page does. No scroll when the field shrinks or is not
focused (a text set by the code, a tab switch). Reason: the browser's own "nearest" moves
the least and finds the right scrolling box in each layout, with no knowledge of the card
in the hook.

### D4. No resize handle; a line height to count by

`.waiting-field` and `.answer textarea` get `resize: none` and `line-height: 1.5` (the
composer's), so `grow` counts lines from a defined value. `rows` goes from the fields
(the height comes from `grow`; `rows={3}` stays as the first paint's height before the
layout effect). Reason: a handle in a scrolling list is the defect; a field sized by its
text needs none.

### D5. The gate's comment grows wherever the panel shows

`GatePanel`'s field is one element for the waiting card's gate tab and the Flows tab's
gate card, so both get D1 to D4. Reason: one component, one behaviour; the Flows tab's
card does not scroll inside, so D3 there scrolls the page only when needed.

### D6. Test layers

vitest for the rule and the hook (jsdom has no layout: `scrollHeight` and
`getComputedStyle` stubbed; `scrollIntoView` spied), and for the card's fields having the
hook's height. UI e2e (Chromium, real server, fake agent) for what needs a layout: the
height in lines, the field within the list, the Send row and the window, in the card, the
expanded card and a gate's tab, with screenshots. No integration test: no process other
than the browser takes part.

### D7. Version

A fix with no API, CLI, MCP or schema change: patch level; its CHANGELOG line goes under
the open `## 0.40.0 (unreleased)` heading, as the line of a fix does in the release being
prepared.
