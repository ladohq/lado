## ADDED Requirements

### Requirement: A focus that a closing window gives back shows no tooltip

A tooltip SHALL NOT show when a closing modal window gives the focus back to its trigger, whether
the window closed by the keyboard or by the pointer.

#### Scenario: Esc
- **WHEN** the human closes Take control with Esc and the focus goes back to its button
- **THEN** no tooltip shows

#### Scenario: Cancel with the mouse
- **WHEN** the human clicks Cancel in Forget and moves the pointer away
- **THEN** the focus is on Forget's button and no tooltip shows
