## MODIFIED Requirements

### Requirement: The Model field looks like the window's other fields

The Model field SHALL have the height, frame, font and a chevron like the window's
Agent CLI field and take a column of the window's grid as Agent CLI does (the whole row on
a narrow window). Its note SHALL stand under it as far below as the notes of the
window's other fields, out of the reach of its focus ring.

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Permission mode is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Advanced is open
- **THEN** the Model field has Agent CLI's height and width and a chevron at its right end
