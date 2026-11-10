## ADDED Requirements

### Requirement: A run's page shows its gate's whole card

A run that waits at a gate SHALL show, under its steps, the gate's card as the waiting card shows
it (capability chat-question-card): a head with "Waits for you · <since>" over the question, the
note and its documents' chips, the recommendation, the comment and the buttons, whole, with no
scroll inside it, no fade and no splitter; the page SHALL scroll. No title "Gate #<id> · <run> ·
<state>" SHALL stand over it. Its History SHALL follow it.

#### Scenario: A gate on its run's page
- **WHEN** run ship/x waits at gate #4 of step check, with a note and a recommendation of ten
  lines, and the human opens it in Flows
- **THEN** the page shows "Waits for you · 4 min" and "Build it as planned?" in one head, the
  note, its chips, the whole recommendation, the comment field, Approve and Reject, and no "Gate
  #4 · ship/x · check"
