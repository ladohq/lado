## MODIFIED Requirements

### Requirement: The footer says what is missing

While the start button is off, the footer SHALL show `To start: ` and the missing items as
links that focus their fields (opening Team when needed): choose a place, wait for the check,
name the folder, name the session, choose another name, shorten the name, wait for the agent
CLIs, choose an agent (also when their list failed), choose a kit, choose a smaller folder,
choose another folder, set the commit author, wait for the count, fix the model, shorten the
task, log in to `<CLI>`.

#### Scenario: The agent CLIs not known yet
- **WHEN** the folder will do and `/api/providers` has not answered
- **THEN** the start button is off and the footer reads `To start: wait for the agent CLIs`

#### Scenario: Enter beside a stopped session
- **WHEN** the place has a stopped session, Task is empty and the human presses Enter in a
  field of the window
- **THEN** the window starts the new session under the free name, as its button `Start new
  session <free name>` would; the stopped session stays stopped

#### Scenario: No agent chosen
- **WHEN** two CLIs are installed and none is suggested
- **THEN** Team shows Agent `choose…` in its summary and the footer reads `To start: choose
  an agent`; the link puts the focus on Agent

#### Scenario: No kit
- **WHEN** the human removes the last kit
- **THEN** the footer reads `To start: choose a kit`; the link opens Team with the focus on
  `+ Add kit`
