## MODIFIED Requirements

### Requirement: Tests never send

The test suite SHALL run with `LADO_TELEMETRY=0`, set in `tests/conftest.py`, for every
layer under `tests/` (unit, integration, UI, smoke and live), and every LADO process a test
starts SHALL inherit it; a test of sending SHALL take a fixture that removes it and points
`LADO_TELEMETRY_URL` at a local server of the test. An autouse fixture of
`tests/conftest.py` SHALL fail a test when, before it, sending is not off by
`LADO_TELEMETRY=0`, or when, after it, the test's `LADO_HOME` holds `telemetry/sent.json`
or a file in `telemetry/outbox/` and the test did not take `telemetry_on`.

#### Scenario: A test session's hook fails
- **WHEN** an integration test's hook raises
- **THEN** nothing is sent anywhere outside the test

#### Scenario: The setting is dropped from the conftest
- **WHEN** a change removes `LADO_TELEMETRY=0` from `tests/conftest.py`
- **THEN** every test fails at the guard's check before it, naming `LADO_TELEMETRY=0`

#### Scenario: A test switches sending on by hand
- **WHEN** a test without `telemetry_on` stores the yes, removes `LADO_TELEMETRY` and runs
  the sender, which writes `telemetry/sent.json`
- **THEN** the test fails at the guard's check after it, which names the file and
  `telemetry_on`

#### Scenario: A LADO process of a test
- **WHEN** a test runs `lado telemetry status` as a subprocess
- **THEN** it prints that statistics are off because `LADO_TELEMETRY=0` is set

## ADDED Requirements

### Requirement: The release candidate's scratch install never sends

Each command of docs/release.md that runs LADO in a home made for the check
(`LADO_HOME=$(mktemp -d)`) SHALL set `LADO_TELEMETRY=0` in the same command, so the
scratch install neither asks the statistics question nor sends; a unit test SHALL keep
docs/release.md so.

#### Scenario: The human installs the RC in a fresh home
- **WHEN** the human runs section 4's `lado start <scratch repository>` of the RC on a
  terminal
- **THEN** LADO does not ask about statistics, and the scratch home's install id never
  reaches PostHog

#### Scenario: A checklist line loses the setting
- **WHEN** docs/release.md has a `LADO_HOME=$(mktemp -d)` without `LADO_TELEMETRY=0` in
  the same command
- **THEN** the docs test fails, naming the line
