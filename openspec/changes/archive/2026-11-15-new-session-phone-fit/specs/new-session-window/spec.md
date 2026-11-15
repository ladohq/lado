## MODIFIED Requirements

### Requirement: The window's frame keeps the footer in view

The window SHALL stand 40 px from the top and grow down, its body scrolling and its footer
not; at 760 px or less it SHALL be a full-screen sheet with targets of at least 44 px and the
footer above the screen's safe area. On the sheet every field SHALL be 44 px high but Name on
Task's label row, every button of a note at least 44 px high (a link within a note's sentence
excepted), and a kit chip's × SHALL keep a 32 px look with a 44×44 px hit area.

#### Scenario: A phone
- **WHEN** the window is open with Team open on a 390×844 screen
- **THEN** the start button is in view without scrolling, and the body scrolls under it

#### Scenario: The sheet's fields and buttons
- **WHEN** the window is open with Team open on a 390×844 screen and the model's server does
  not answer
- **THEN** Agent, `+ Add kit`, Model, Switch off and the place's fields are 44 px high, Name's
  field 30 px, and `Check again` and `Use <CLI>'s settings` under Model at least 44 px high

#### Scenario: A kit's ×
- **WHEN** the human taps 5 px outside the drawn × of the kit chip `default` on a 390 px screen
- **THEN** the kit `default` is removed from Kits
