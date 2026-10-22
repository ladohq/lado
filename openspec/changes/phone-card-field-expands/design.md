## Context

The waiting card (`WaitingCard.tsx`) already has an expanded mode: the chat hides its
feed and composer by CSS (`.chat:has(> .waiting-card.expanded)`), the card fills the
chat. On a phone with the keyboard open the chat is about 250 px high (proposal, Why), and
the card gets no room. The fix reuses the expanded mode instead of adding one.

## Decisions

### D1. A field's focus expands the card through the card's own state

`WaitingCard` handles `onFocus` (React's bubbling focus) on its panel: when the card is in
a session's chat (`chat` given), `usePhone()` is not null, the card is not expanded, and
the target is one of its answer fields (`textarea.waiting-field`, the field of
`attachFiles.AnswerBox`), it sets `expanded`. One place covers the gate's comment, the own
answer and the skip's comment, including the own answer's `autoFocus` after Other….
Not on Needs you (`chat` undefined), nor on a computer. Reason: the expanded mode, its
Esc, its fold button and its self-fold when nothing waits already exist and are tested.

### D2. Expanding from a field keeps the focus in the field

Today the effect that runs when `expanded` turns true focuses the shown tab; on a phone
that would blur the field and close the keyboard. A ref (as `folded` and `toggled` are)
marks an expansion that a field's focus caused; that effect then leaves the focus where
it is and scrolls the focused field into the list's view (`scrollIntoView({ block:
"nearest" })`, after layout), since the list was laid out at the collapsed height. The
expand button's expansion keeps focusing the tab.

### D3. The phone hides the session's tabs and the Team row by CSS

In the stylesheet's section "Phone layout", under `:root[data-phone]`:
`.session:has(.waiting-card.expanded) .session-tabs` and
`.activity:has(> .chat > .waiting-card.expanded) > .team-row` get `display: none`, as the
chat already hides its feed and composer. It applies to every expansion on a phone (the
button, a field, sideways), one rule; a computer keeps its tabs and team row. Reason: on a
phone with the keyboard the tabs (≈ 45 px) and the Team row (one or two lines) are what
is left to win; checked in Chromium at 402×874 with 400 px visible: the comment field and
Approve / Reject fit.

### D4. Nothing folds on blur and no keyboard is detected

The card stays expanded when the field loses the focus (the human's decision), so there
is no blur handler and no guess of the keyboard from `visualViewport` (option B of the
proposal); `phone.ts` is not changed.

## Risks

- A field focused by a script rather than by the human on a phone (none today besides
  the own answer's `autoFocus`, which follows the human's tap on Other…) would expand the
  card too; acceptable, as it would show the field the focus went to.
