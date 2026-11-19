## ADDED Requirements

### Requirement: The installer gives the container no ssh agent

A fresh install SHALL neither look for an ssh agent nor write `LADO_SSH_AGENT`. A rerun
SHALL keep a `LADO_SSH_AGENT` line of `.env` as it is, for the way back to a version
before, and SHALL print one note: `LADO_SSH_AGENT in .env is no longer used: git goes over
https through Settings → Git servers; remove the line once you no longer go back to a
version before 0.48.0.`

#### Scenario: macOS
- **WHEN** a fresh install runs on macOS
- **THEN** `.env` has no `LADO_SSH_AGENT`, and the output names no ssh agent

#### Scenario: Linux with an ssh agent
- **WHEN** a fresh install runs on Linux with `SSH_AUTH_SOCK` naming a socket
- **THEN** `.env` has no `LADO_SSH_AGENT`

#### Scenario: An update of an .env with the ssh agent
- **WHEN** `.env` has `LADO_VERSION=0.47.0` and
  `LADO_SSH_AGENT=/run/host-services/ssh-auth.sock`, and the script is `0.48.0`
- **THEN** it updates, `.env` still has that line, and the output has the note once

## REMOVED Requirements

### Requirement: The installer gives the agents the ssh agent there is

**Reason**: the container has no ssh; git servers are set up only in LADO's settings.
**Migration**: save the git server in Settings → Git servers.
