## ADDED Requirements

### Requirement: Take control dims the whole page

Take control's question SHALL be a modal dialog whose backdrop is `--scrim` and covers the whole
page, the terminal it asks about too.

#### Scenario: The terminals open
- **WHEN** the human presses Take control in an open terminal
- **THEN** the dialog's backdrop computes to `--scrim`, and a click on the terminal behind it reaches
  no terminal
