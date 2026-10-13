## Purpose

Anonymous usage statistics and LADO's own errors, sent to LADO's maintainers only after
the human said yes: one question in the UI and the CLI, a published list of fields, a
preview of exactly what goes, and a switch in Settings and `lado telemetry`.

## ADDED Requirements

### Requirement: Nothing is sent without the human's yes

LADO SHALL send statistics or errors only while all of these hold: the human chose `on`
for the current list of fields, neither `DO_NOT_TRACK` (set, not empty and not `0`) nor
`LADO_TELEMETRY=0` is in the process's environment, and this LADO has an endpoint (a
project key, or `LADO_TELEMETRY_URL`). Otherwise nothing SHALL be queued or sent, and
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
- **WHEN** this LADO's project key is empty and `LADO_TELEMETRY_URL` is unset
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
`GET /api/telemetry/preview` SHALL give exactly the JSON the next send would post, the key
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
  failure, and the next try comes no sooner than 15 minutes later

#### Scenario: The same error a hundred times
- **WHEN** the same hook error is queued 100 times in a day
- **THEN** the next send posts one error event with count 100

#### Scenario: Two senders at once
- **WHEN** the loop and a CLI command start a sender at the same moment
- **THEN** one of them sends and the other exits without sending

### Requirement: Tests never send

The test suite SHALL run with `LADO_TELEMETRY=0`, set in `tests/conftest.py`; a test of
sending SHALL take a fixture that removes it and points `LADO_TELEMETRY_URL` at a local
server of the test.

#### Scenario: A test session's hook fails
- **WHEN** an integration test's hook raises
- **THEN** nothing is sent anywhere outside the test
