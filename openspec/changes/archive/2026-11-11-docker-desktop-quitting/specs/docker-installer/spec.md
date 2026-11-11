## MODIFIED Requirements

### Requirement: The installer starts Docker Desktop on macOS

On macOS, when `docker info` fails and Docker Desktop is installed, the installer SHALL
start it (`open -a Docker`), say that it waits for it, and wait up to 120 seconds for
`docker info` before it stops. While it waits, it SHALL ask Docker Desktop to start again
in the background (`open -g -a Docker`) every 10 seconds, so that a Docker Desktop that was
still quitting at the first ask is started once it has quit.

#### Scenario: Docker Desktop not running
- **WHEN** `docker info` fails at first on macOS and answers after `open -a Docker`
- **THEN** the script says it is waiting for Docker Desktop and goes on once it answers

#### Scenario: Docker Desktop still quitting
- **WHEN** on macOS the first `open -a Docker` starts nothing, because Docker Desktop is
  still quitting, and `docker info` answers only after a later ask
- **THEN** the script asks again with `open -g -a Docker` and goes on once `docker info`
  answers, within the same 120 seconds

#### Scenario: Docker Desktop never answers
- **WHEN** `docker info` never answers on macOS
- **THEN** the script stops after 120 seconds of waiting, naming Docker Desktop
