## MODIFIED Requirements

### Requirement: On a phone the composer's text is large and shows no keys hint

In the phone layout the composer's text SHALL be at least 16 px, and its keys hint ("Enter to send ·
Shift+Enter …") SHALL not be shown on a touch screen. The line under the composer SHALL not show
`to supervisor`, and with nothing to show it SHALL take no height.

#### Scenario: No keys hint
- **WHEN** the chat is shown on a touch screen
- **THEN** the composer shows no "to supervisor", no keys hint and no empty line
