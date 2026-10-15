## Context

The waiting card (`WaitingCard.tsx`, docs/design/ui.md, The waiting card) holds its items
in `.waiting-list`, which scrolls (`overflow: auto`) under the fixed Send row; a gate's
panel (`GateCard.tsx`'s `GatePanel` with `inTab`) puts its question, note and comment
field in the same list. A scrolling box clips its content at its padding box, so a ring a
child draws outside its own box shows only where the list has padding: today 6 px on the
right and 4 px below (`padding: 0 6px 4px 0`), none on the left or at the top.

The rings drawn there: `:focus-visible` (the UI's default, `styles.css` top: 2 px outline,
2 px offset, 4 px out), which the gate's `.answer textarea` takes; `.waiting-field:focus`
and `.waiting-question.marked`, a 3 px `box-shadow`. The largest is 4 px.

Options held against AGENTS.md's Design principles and ROADMAP (UI only, no provider: the
neutral core is not touched; stage 7's desktop app shows the same web UI):

1. **Chosen: room on every side of the list, pulled back by a negative margin** (D1).
   Cost: one rule, no change of look or of where things stand; any ring up to 4 px inside
   the list shows whole, also for an item added later.
2. A ring drawn inside the field (inset shadow, `outline-offset: -2px`): never cut
   anywhere, but a second focus look in the UI and less room for the text; it fixes the
   fields, not the marked question.
3. Padding without the negative margin: the questions move 4 px right and down; a visible
   change of layout for no gain.

## Decisions

### D1. The list keeps 4 px of room on every side and does not move its content

`.waiting-list` gets `padding: 4px 6px 4px 4px` (the right stays 6 px, which is more than
4 px) and `margin: -4px 0 0 -4px`: the list's box reaches 4 px into the panel's padding
(14 px by 16 px, so nothing of the panel is cut), and its content starts where it starts
now. The list's top moves 4 px into what is above it, the panel's padding or the panel's
12 px gap, both empty. The bottom keeps LAD-70's 4 px and no negative margin:
the Send row stays where it is.

### D2. One value for the room: `--ring-room`

The 4 px is written once, as a custom property `--ring-room: 4px` on `:root`, with a
comment naming the rings it holds (the `:focus-visible` outline, 2 px at a 2 px offset;
the 3 px ring of `.waiting-field:focus` and `.marked`). The list's padding and margin and
the fields' scroll margin (D3) use it. On `:root`, not on `.waiting-card`: the Flows tab's
gate card has the same `.answer textarea` outside any waiting card, and its run page
(`.list-main`) scrolls the growing field into view as the card's list does, so it needs
the same room (the review's F1: with the value on the card it fell back to 0 there and
the ring's bottom was cut, where LAD-70's 4 px had kept it).

### D3. A field scrolls into view with its ring

`.waiting-field` and `.answer textarea` replace `scroll-margin-bottom: 4px` (LAD-70) with
`scroll-margin: var(--ring-room)`: the browser's own scroll on focus and LAD-70's
`scrollIntoView({block: "nearest"})` (`fieldHeight.ts`) leave room for the ring at
whichever edge they bring the field to, in the card's list and on the Flows tab's run
page alike. No change to `fieldHeight.ts`.

### D4. Tested in the browser, by geometry

The bug is layout and clipping, which vitest's jsdom does not compute: the tests are UI
e2e (AGENTS.md, Testing, layer 4). One measuring function in the test reads the ring's
extent from the element's computed style (outline width plus offset when its outline
style is not `none`, else the `box-shadow`'s spread) and checks the box grown by it lies
within the list's visible box (its client area: `getBoundingClientRect` less its borders
and scrollbar), on each of the four sides, with a 0.5 px tolerance. Each test also saves a
screenshot (`shot`).
