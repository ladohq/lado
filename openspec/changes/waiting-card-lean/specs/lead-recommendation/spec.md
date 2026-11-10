## ADDED Requirements

### Requirement: A disagreement is a frame and a sign, its words for a screen reader

A recommendation given with `disagrees` SHALL show a 1 px `--warn` frame and a ⚠ of 16 px in
`--warn` before the avatar, with no visible words about it. Its block's name SHALL be
"Supervisor's recommendation, disagrees with the step's report" on a gate and "Supervisor's
recommendation, disagrees with <agent>" on a question, and the ⚠ SHALL have the UI's tooltip
with the same words. On a gate whose note the lead wrote itself no disagreement SHALL show.

#### Scenario: A gate's recommendation that disagrees
- **WHEN** gate #7's note by reviewer says "ready to merge" and the lead recommends `reject` with
  disagrees set
- **THEN** the block has an amber frame and ⚠, reads "supervisor recommends Reject" and no
  "disagrees", and a screen reader names it "Supervisor's recommendation, disagrees with the
  step's report"

#### Scenario: The lead's own note
- **WHEN** the supervisor wrote gate #8's note and recommends on it with disagrees set
- **THEN** the block has the `--line` frame and no ⚠

### Requirement: A long recommendation scrolls in its own box in the chat

In the chat's card the recommendation's text SHALL stand in a box as high as the recommendation's
splitter sets (by default 4 lines, a phone 2), which a shorter text SHALL not fill; a longer one
SHALL scroll inside it, by the wheel, a finger or the keys with the focus on it, and SHALL fade at
its lower edge until it is scrolled to its end; the expanded card keeps the box and its splitter.
On Needs you, on a run's page and under each question of a tab of several it SHALL show whole.

#### Scenario: A long recommendation
- **WHEN** a recommendation of ten lines waits on a gate in the chat
- **THEN** 4 lines show with a fade at the lower edge, and once the human scrolls the text to its
  end the fade is gone

#### Scenario: On a phone
- **WHEN** the same gate waits on a phone 390×844
- **THEN** 2 lines show with a fade

#### Scenario: Whole on a phone's Needs you
- **WHEN** the same gate waits on Needs you on a phone 390×844
- **THEN** all its text shows, its block ending above the comment field

### Requirement: A wheel over the recommendation's block scrolls its text

In the chat's card a wheel anywhere over the recommendation's block SHALL scroll its text, as a
box of a line is hard to hit; at the text's end the wheel SHALL go on to what is around it.

#### Scenario: The wheel over its head
- **WHEN** the box is a line high and the human turns the wheel over "supervisor recommends"
- **THEN** the text scrolls; at its end the wheel scrolls what is around it

## MODIFIED Requirements

### Requirement: The card shows the recommendation as part of the gate or question

The web UI SHALL show an open gate's or question's recommendation inside its card, one block in
the chat, on Needs you and on a run's page, and the human SHALL be able to answer in every state.
The block SHALL stand over the answer, on `--panel` in a 1 px `--line` frame, no band at its left: the supervisor's small avatar and "supervisor recommends **<option>**" (as
the card's button names it; "supervisor" alone without an option of the card's), its time at the
right, then the text as Markdown.

#### Scenario: A recommendation that disagrees
- **WHEN** gate #7's note says "ready to merge" and the lead recommends `reject` with
  disagrees set
- **THEN** the card shows "supervisor recommends Reject" in a block with an amber frame and the
  text, and Reject is the primary button, Approve quiet

#### Scenario: A long recommendation on a phone
- **WHEN** a recommendation of ten lines waits on a phone
- **THEN** its text shows 2 lines and the rest scrolls inside them, with a fade at the lower edge
  until the text is scrolled to its end

#### Scenario: A recommendation without an option
- **WHEN** the lead recommends on gate #9 with text only
- **THEN** the block's head reads "supervisor" and the time, and the text under it

### Requirement: On a question the recommended choice is picked ahead

On a question, in its tab of the waiting card,
whose choices are picks and whose primary button is Send, the recommended choice SHALL be
picked ahead when it is one of the question's choices, marked ✓ while it stays picked, and
SHALL count and be sent as any
pick; the human's own pick, also unpicking it, SHALL win, and a recommendation given later
SHALL pick its choice only in a question the human has not touched.

#### Scenario: A question's recommended choice is picked ahead
- **WHEN** w1 asks question #12 with the choices "yes" and "later", and the lead recommends
  "later"
- **THEN** w1's tab shows the recommendation's block over the choices and "✓ later" picked, and
  Send sends "later" unless the human picks otherwise

#### Scenario: The human unpicks the recommended choice
- **WHEN** the human clicks the picked "later" of question #12
- **THEN** no choice of #12 is picked, and Send waits for the human's own answer

#### Scenario: A recommendation without a choice
- **WHEN** the lead recommends on question #13 with text only, or with a choice the
  question does not have
- **THEN** the tab shows the block and picks nothing

### Requirement: The card says when a recommendation is being prepared or missing

While the recommendation is `asked` the card SHALL say "Supervisor is preparing a
recommendation…" in one muted italic line, with no block and no splitter. When it is `missing`,
and when none was asked, the card SHALL show nothing of it: no block, no line and no splitter.

#### Scenario: Still preparing
- **WHEN** gate #8's recommendation is `asked`
- **THEN** the card says "Supervisor is preparing a recommendation…" and its buttons work

#### Scenario: Missing
- **WHEN** gate #8's recommendation is `missing`
- **THEN** the card shows no recommendation and no "The supervisor gave no recommendation", and
  Approve is primary

## REMOVED Requirements

### Requirement: The waiting card's recommendation is one line
**Reason**: The one-line recommendation needed a click, a tooltip and "more" to be read (LAD-266);
the block shows its text, scrolling in its own box.
**Migration**: "The card shows the recommendation as part of the gate or question" and "A long
recommendation scrolls in its own box in the chat".

### Requirement: The waiting card's line opens to its text
**Reason**: There is no line to open: the text shows in the block (LAD-266).
**Migration**: "A long recommendation scrolls in its own box in the chat"; its height is set by
the splitter of capability chat-question-card.
