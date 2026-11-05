## MODIFIED Requirements

### Requirement: The card shows the recommendation as part of the gate or question

The web UI SHALL show an open gate's or question's recommendation inside its card. On a run's
page in Flows it SHALL be a block between the question's text and the answer: under the
supervisor's small avatar and "Supervisor's recommendation", with its time, and "disagrees
with <agent>" in orange when the lead disagrees, the whole text as Markdown. In the waiting
card (the chat's and Needs you's) it SHALL be one line above the answer, the avatar of 20 px
then "**Supervisor recommends <option>:** <text>", or "**Supervisor's recommendation:**
<text>" without an option of the card's, cut with "…" (on a phone 2 lines); " · disagrees with
<agent>" in orange SHALL stand right after the option, so a cut never takes it. Its whole text
and time SHALL be in its tooltip, and a click SHALL open it to 3 lines of Markdown that scroll
inside; in the expanded card it SHALL show whole. The human SHALL be able to answer in every
state.

#### Scenario: A recommendation that disagrees
- **WHEN** gate #7's note says "ready to merge" and the lead recommends `reject` with
  disagrees set
- **THEN** the card shows the line "Supervisor recommends Reject · disagrees with reviewer:"
  in orange and the text, and Reject is the primary button, Approve quiet

#### Scenario: A long recommendation on a phone
- **WHEN** a recommendation of ten lines waits on a phone and the human taps it
- **THEN** it opens to 3 lines and the rest scrolls inside them, with a fade at the lower edge
  until the text is scrolled to its end

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
- **THEN** w1's tab shows the line over the choices and "✓ later" picked, and Send sends
  "later" unless the human picks otherwise

#### Scenario: The human unpicks the recommended choice
- **WHEN** the human clicks the picked "later" of question #12
- **THEN** no choice of #12 is picked, and Send waits for the human's own answer

#### Scenario: A recommendation without a choice
- **WHEN** the lead recommends on question #13 with text only, or with a choice the
  question does not have
- **THEN** the tab shows the line and picks nothing
