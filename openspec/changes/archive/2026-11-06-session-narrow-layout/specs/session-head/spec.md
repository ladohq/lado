## MODIFIED Requirements

### Requirement: Details shows the session's facts in a popover

Details SHALL be a non-modal `role="dialog"` named `Session details`, under the title's
button, 470 px wide and at most the window less 32 px, as high as the window allows and
scrolling inside beyond that, with no focus trap. Opening it SHALL put the focus on Copy path. Its content SHALL come from the same component as the phone's
sheet. Until the about comes, or when it fails, it SHALL show the session's settings alone.

#### Scenario: A narrow window
- **WHEN** the window is 601 px wide and the human opens Details
- **THEN** it is 470 px wide and lies inside the window
