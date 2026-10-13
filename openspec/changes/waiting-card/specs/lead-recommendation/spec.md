## MODIFIED Requirements

### Requirement: The card shows the recommendation as part of the gate or question

The web UI SHALL show an open gate's or question's recommendation inside its card (in the
chat's waiting card, on Needs you and on a run's page in Flows), between the question's
text and the answer: under the supervisor's small avatar and "Supervisor's
recommendation", with its time, and "disagrees with <agent>" in orange when the lead
disagrees, the whole text as Markdown. On a gate, when it names an option, that option's
button SHALL be the only primary one and the others quiet, with no other label; otherwise
the first option is primary as before. On a question, in its tab of the waiting card,
whose choices are picks and whose primary button is Send, the recommended choice SHALL be
picked ahead when it is one of the question's choices, and SHALL count and be sent as any
pick; the human's own pick, also unpicking it, SHALL win, and a recommendation given later
SHALL pick its choice only in a question the human has not touched. While it is `asked`
the card SHALL say "Supervisor is preparing a recommendation…", when `missing` "The
supervisor gave no recommendation", and with none nothing. The human SHALL be able to
answer in every state. A closed card SHALL show it as one quiet line, "Supervisor
recommended: <option>" or "Supervisor's recommendation" without an option, whose text
opens on a click. The API SHALL give it as `recommendation` of `GateInfo` and of a
question's `MessageInfo` (state, text, choice, disagrees, time; none when not asked), and
the change feed SHALL bring each change of it.

#### Scenario: A recommendation that disagrees
- **WHEN** gate #7's note says "ready to merge" and the lead recommends `reject` with
  disagrees set
- **THEN** the card shows the block with "disagrees with reviewer" in orange and the text,
  and Reject is the primary button, Approve quiet

#### Scenario: The primary button moves to the recommended option
- **WHEN** approval gate #9 shows Approve as its primary button while its recommendation
  is `asked`, and the lead then recommends `reject`, agreeing or disagreeing alike
- **THEN** Reject becomes the primary button and Approve a quiet one

#### Scenario: A question's recommended choice is picked ahead
- **WHEN** w1 asks question #12 with the choices "yes" and "later", and the lead recommends
  "later"
- **THEN** w1's tab shows the block under the question and "later" picked, and Send sends
  "later" unless the human picks otherwise

#### Scenario: The human unpicks the recommended choice
- **WHEN** the human clicks the picked "later" of question #12
- **THEN** no choice of #12 is picked, and Send waits for the human's own answer

#### Scenario: A recommendation without a choice
- **WHEN** the lead recommends on question #13 with text only, or with a choice the
  question does not have
- **THEN** the tab shows the block and picks nothing

#### Scenario: Still preparing
- **WHEN** gate #8's recommendation is `asked`
- **THEN** the card says "Supervisor is preparing a recommendation…" and its buttons work

#### Scenario: Closed
- **WHEN** the human answered question #12, for which the lead recommended "later"
- **THEN** the closed card shows "Supervisor recommended: later", and a click shows the
  text
