## ADDED Requirements

### Requirement: A kit chip keeps its look while Where changes

While the window asks for the kit list of a new place, Kits SHALL show the chips, and
`+ Add kit` its kits, by the last kit list the window got: each chip's version, the
strike-through and problem of an invalid kit. The answer for the new place SHALL then replace
it. A failed ask SHALL show its error at once and drop the last kit list: the chips then show
their names alone until a later ask answers.

#### Scenario: Back to Other folder…
- **WHEN** the window shows the kit chip `default 0.1.0` and the human picks `Project…` and then
  `Other folder…` in Where on a 390×844 screen
- **THEN** the chip keeps reading `default 0.1.0`, and a tap 5 px outside the drawn × removes
  the kit

#### Scenario: The next place's answer is late
- **WHEN** the kit list of the new place has not answered yet
- **THEN** the chip still reads `default 0.1.0`, and once the answer comes the chip follows it

#### Scenario: The next place's ask fails
- **WHEN** the kit list of the new place fails
- **THEN** its error shows in Team, the chip reads `default` without a version, and `+ Add kit`
  offers no kit until a later ask answers
