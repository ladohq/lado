# kit-expectations Specification

## Purpose
What a refusal says when a kit of the session expects a skill or a command the session lacks.

## Requirements

### Requirement: A kit's unmet expectation advises in words of the CLI and the window

When a start is refused because a kit expects a skill no kit of the session gives, the refusal
SHALL end with `add a kit that provides it to the session`; when it expects a command missing
from the agents' PATH, its line SHALL end with `install it (each launch looks again), or start
the session without kit "<kit>"` (`them` for several commands). Neither text SHALL name a CLI
option, as the same text is shown by `lado start` and in the New session window.

#### Scenario: A skill no kit gives, in the window
- **WHEN** the human starts a session in New session with the kit `sdlc` and no kit gives the
  skill `tracker`
- **THEN** the window shows `kit "sdlc" expects skill "tracker", which no kit of the session
  provides: add a kit that provides it to the session`, and no `--kit`

#### Scenario: A missing command, from the CLI
- **WHEN** `lado start <repo> --kit host` runs and the kit `host` expects the command `gh`,
  which is not on the agents' PATH
- **THEN** the refusal's line for `host` ends with `or start the session without kit "host"`
