# usage-telemetry Specification

## Purpose
Anonymous usage statistics and LADO's own errors, sent to LADO's maintainers only after
the human said yes: one question in the UI and the CLI, a published list of fields, a
preview of exactly what goes, and a switch in Settings and `lado telemetry`.

## Requirements

### Requirement: Nothing is sent without the human's yes

LADO SHALL send statistics or errors only while all of these hold: the human chose `on`
for the current list of fields, neither `DO_NOT_TRACK` (set, not empty and not `0`) nor
`LADO_TELEMETRY=0` is in the process's environment, and this LADO has an endpoint (a
PostHog project token, or `LADO_TELEMETRY_URL`). Otherwise nothing SHALL be queued or sent, and
`lado telemetry status`, `GET /api/telemetry` and the System panel SHALL say why: not
chosen, off, off by the named variable, or no statistics endpoint. The choice SHALL be
kept in `LADO_HOME` and be the same for the CLI, the UI and every LADO process of that
home.

#### Scenario: No choice yet
- **WHEN** LADO fails in a hook and no choice was made
- **THEN** the error is in `errors.jsonl` only, nothing is queued, and nothing is sent

#### Scenario: Switched off by the environment
- **WHEN** the choice is `on` and the UI server runs with `DO_NOT_TRACK=1`
- **THEN** nothing is sent, Settings shows the switch disabled with "Off: DO_NOT_TRACK=1 is
  set in the LADO server's environment", and `lado telemetry status` run with that
  variable prints `statistics: off: DO_NOT_TRACK=1 is set (your choice: on)`

#### Scenario: No endpoint
- **WHEN** this LADO's project token is empty and `LADO_TELEMETRY_URL` is unset
- **THEN** no question is asked, nothing is sent, and `status` says this LADO has no
  statistics endpoint

### Requirement: LADO asks once, in the UI and in the CLI

While the choice is not made (D4's `not chosen`, also when the stored yes covers an older
list of fields) and nothing switches it off and there is an endpoint, the UI SHALL show a
banner under the top bar on every page: "Help improve LADO?", what is sent and never
sent, "Nothing is sent until you choose", a What is sent disclosure with the next daily
report, and the buttons Send statistics and Don't send and a link to `docs/telemetry.md`.
`lado start` and `lado ui` SHALL ask the same before their work, on stderr, ending with
`Send them? [y/N]`, only when stdin and stderr are terminals and not inside an agent
(`LADO_AGENT`); `y` is on, Enter or `n` is off, EOF or Ctrl-C stores nothing. When the
stored yes covers an older list, the question SHALL name the new fields.

#### Scenario: The human says yes in the UI
- **WHEN** the banner shows and the human presses Send statistics
- **THEN** the choice is `on` for the current fields, the banner goes, and Settings shows
  Send

#### Scenario: Enter in the CLI
- **WHEN** `lado start ~/work/app` asks in a terminal and the human presses Enter
- **THEN** the choice is `off`, `statistics: off` is printed, and the session starts

#### Scenario: No terminal
- **WHEN** `lado start` runs with stdin from a pipe and no choice made
- **THEN** nothing is asked, nothing is stored, and the session starts

#### Scenario: New fields
- **WHEN** the stored choice is `on` for fields version 1 and this LADO's is 2, adding
  `models`
- **THEN** nothing is sent, and the banner and the CLI ask again naming `models`

### Requirement: The human sees and changes the choice

Settings SHALL have a last section, Usage statistics, with Send / Don't send, a line for
its state (last sent and when, "Not chosen yet: nothing is sent", or off by the named
variable with the switch disabled) and links to the next report and to
`docs/telemetry.md`. The System panel SHALL have a row `Statistics` (`sending · last
<time>`, `off`, `not chosen`, or off by the variable) that leads to Settings, and the
copied system report SHALL have a line `- Statistics: ...`. `lado telemetry` SHALL have
`status` (the default), `on`, `off` and `show`; `on` and `off` SHALL be refused inside an
agent; `off` SHALL drop what is queued.

#### Scenario: Turned off in Settings
- **WHEN** the human picks Don't send while two errors are queued
- **THEN** the choice is `off`, the queue is empty, and nothing is sent

#### Scenario: An agent tries to switch it on
- **WHEN** an agent runs `lado telemetry on`
- **THEN** it is refused and the choice is unchanged

#### Scenario: The panel's row
- **WHEN** the choice is `on` and the last send was today at 09:12
- **THEN** the System panel shows `Statistics` `sending · last today 09:12`, and the
  copied report has `- Statistics: on`

### Requirement: What is sent is the published list and nothing else

The daily report SHALL carry only: a random install ID kept in `LADO_HOME`, LADO's and
Python's versions, the OS and architecture, the installer kind (`uv tool`, `pipx`, `dev`,
`other`), the installed agent CLIs and their versions, the built-in and official kits by
name and a count of the others, and, since the last report, the counts of sessions started
or resumed, agents spawned per provider, flow runs started, gates opened, turn errors,
LADO errors and errors dropped from a full queue. An error event SHALL carry only its
type and its causes' types, its stack as frames of LADO's own package (file relative to
the package, function, line; other frames as `<external>`), where it happened without
ids, the provider, a fingerprint, its count and its first and last time. No event SHALL
carry a path, a repository, session or agent name, a message, a prompt, a command's
argument, an environment value or an exception's text. `lado telemetry show` and
`GET /api/telemetry/preview` SHALL give exactly the JSON the next send would post, the token
left out. `docs/telemetry.md` SHALL list the same fields as the code, checked by a test.

#### Scenario: An error with a path in its message
- **WHEN** an `OSError` whose message names `/Users/ann/work/app` and whose locals hold a
  token is queued
- **THEN** the queued event has type `OSError` and LADO frames only, and neither the path,
  the user's name nor the token is anywhere in it

#### Scenario: Show before sending
- **WHEN** the human runs `lado telemetry show`
- **THEN** it prints the next daily report and the queued errors grouped by fingerprint,
  and the sender, run next, posts those same events

### Requirement: Sending never delays LADO's work

With sending on, LADO SHALL send at most one daily report per 24 hours and the queued
errors, one event per fingerprint with its count, from a detached process (`lado
telemetry send`, one at a time by a lock) that a CLI command run by the human, the session
loop or the UI server starts when something is due; a hook SHALL only queue. A failed
send SHALL keep everything for a later try, at most every 15 minutes, and keep its reason
for `status`. The queue SHALL hold at most 200 errors; further ones are counted and the
count is sent with the next report.

#### Scenario: Offline
- **WHEN** a send fails because the network is down
- **THEN** the report and the errors stay queued, `lado telemetry status` names the
  failure, and the next try comes no sooner than 15 minutes later (the requirement on an
  unreachable endpoint says the rest)

#### Scenario: The same error a hundred times
- **WHEN** the same hook error is queued 100 times in a day
- **THEN** the next send posts one error event with count 100

#### Scenario: Two senders at once
- **WHEN** the loop and a CLI command start a sender at the same moment
- **THEN** one of them sends and the other exits without sending

### Requirement: An unreachable endpoint changes nothing for the user

When the statistics endpoint cannot be reached or refuses (no network, DNS failure, a
proxy, a TLS error, a firewall or a block by region, a timeout, any non-2xx answer), and
whether it is PostHog or another endpoint set by `LADO_TELEMETRY_URL` or a later
`ENDPOINT`, nothing a user sees or runs SHALL change: no CLI command, hook, `lado mcp`
tool, session loop pass or UI request SHALL wait for the network, print or show an error
about it, or end differently. Only the detached sender talks to the endpoint, each try
SHALL give up after `SEND_TIMEOUT` (2 seconds, as the update check's
`update.CHECK_TIMEOUT`) per network operation and its whole process SHALL end within
`SEND_DEADLINE` (30 seconds) whatever the network does, DNS included; a failed try SHALL
be followed by the next one no sooner than 15 minutes later, with no retries inside a
try. What waits SHALL stay bounded while the endpoint stays unreachable: at most 200
queued errors, none older than 30 days (further and older ones only counted), and one
pending daily report whose window grows from the last report that went through, never
back more than 30 days. The failure SHALL be kept only for
`lado telemetry status` (`last try failed: <reason>`) and the Settings section's line.

#### Scenario: Offline laptop
- **WHEN** the network is down and the human runs `lado start ~/work/app` with sending on
- **THEN** the session starts as fast as without statistics, nothing about the network
  is printed, and `lado telemetry status` says `last try failed: <reason>`

#### Scenario: Blocked by region or firewall
- **WHEN** every connection to the endpoint is refused or answered 403 for a month
- **THEN** LADO works as usual, the queue holds at most 200 errors and one report, and a
  try comes at most every 15 minutes, each over within 30 seconds

#### Scenario: DNS that hangs
- **WHEN** resolving the endpoint's name never answers
- **THEN** the sender's process ends after 30 seconds, releases its lock, and no other
  LADO process waited for it

#### Scenario: The endpoint comes back
- **WHEN** a send succeeds after two days offline
- **THEN** one daily report covering the two days and the queued errors grouped by
  fingerprint are posted, and the queue is empty

### Requirement: Statistics are counted when sent, never collected

LADO SHALL NOT keep usage events of its own for statistics: the daily report SHALL be
counted from `lado.db` when it is built and not stored after it is sent. What waits to
be sent SHALL be at most 200 queued errors and the drop count; an error queued more than
30 days ago SHALL be removed and counted as dropped; a report's window SHALL start no
earlier than 30 days before it is built.

#### Scenario: A month without network
- **WHEN** LADO is used daily for 45 days with the endpoint unreachable and records 500
  errors
- **THEN** `LADO_HOME/telemetry` holds at most 200 queued errors, none older than 30 days,
  and no report file; the first send after that posts one report counting the last 30
  days and the queued errors, and `errors_dropped` counts the rest

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

### Requirement: The project token belongs to the endpoint's region

LADO's built-in PostHog project token (`telemetry.PROJECT_TOKEN`) SHALL be a token of a
project in the region of its built-in endpoint (`telemetry.ENDPOINT`), and a release SHALL
NOT be published while that endpoint's host does not accept the token. The Release
workflow SHALL run `scripts/check_telemetry.py` before it builds and publishes; the script
SHALL ask the endpoint's own host about the token with one request that stores no event,
exit 0 only on a 2xx answer, and otherwise exit 1 with one line saying whether the host
refused the token (401 or 403) or the check could not be made.

#### Scenario: A token of another region
- **WHEN** a tag `vX.Y.Z` is pushed and `eu.i.posthog.com` answers 401 to the project token
- **THEN** the Release workflow fails at the check with `telemetry: eu.i.posthog.com
  refuses the project token: it is not a token of a project in this region`, and nothing
  is built or published

#### Scenario: The region knows the token
- **WHEN** the endpoint's host answers 200 to the project token
- **THEN** the script prints `telemetry: eu.i.posthog.com accepts the project token`,
  exits 0, and the release goes on to build and publish

#### Scenario: PostHog cannot be reached
- **WHEN** the endpoint's host does not answer within 10 seconds
- **THEN** the script prints `telemetry: cannot check the project token: <reason>` and
  exits 1, and nothing is published until a rerun passes

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
