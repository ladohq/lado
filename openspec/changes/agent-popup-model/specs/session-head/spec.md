## MODIFIED Requirements

### Requirement: An agent's popup says who it is and what it does

An agent's tooltip, in the head and on the terminal strip, SHALL read in three parts: the whole
name after its status dot, then the status in words (`working`, `in the background`, `idle`,
`waits for you`, `starting`, `stopped`) and how long, in `--human` when it waits; under a line,
labelled facts `Role` (left out when it is the name), `CLI`, `Model` and `Flow` (when it has a
run); under a second line, smaller, `Click to open the terminal`.

#### Scenario: A waiting reviewer
- **WHEN** the human holds the pointer over `reviewer`, which works for run `task/x` and waits
- **THEN** the tooltip reads `reviewer`, `waits for you` with the time in `--human`, the facts
  `CLI`, `Model` and `Flow task/x`, and `Click to open the terminal`

#### Scenario: The facts under the name
- **WHEN** the human holds the pointer over `analyst-254`, role `analyst`, a Claude agent on
  `claude-opus-5-5` working for run `task/lad-254`
- **THEN** under the name and its status the tooltip reads `Role analyst`, `CLI claude`, `Model
  claude-opus-5-5` and `Flow task/lad-254`, then `Click to open the terminal`

#### Scenario: The role is the name
- **WHEN** the human holds the pointer over `supervisor`, role `supervisor`, of no run
- **THEN** the facts are `CLI` and `Model` alone
