# Usage statistics and LADO's errors

LADO can send its maintainers anonymous usage statistics and its own errors, so they see
how many people use it, which versions run and which errors to fix first. **Nothing is sent
until you say yes**, and you can switch it off at any time.

## The question

While you have not chosen, the web UI shows a banner under its top bar ("Help improve
LADO?"), and `lado start` and `lado ui` ask once in a terminal (`Send them? [y/N]`; Enter
is no). Nothing is asked without a terminal, inside an agent, or when the environment
switches it off. Your choice is kept in `LADO_HOME/telemetry/consent.json` and is the same
for the CLI and the UI.

When a later LADO sends a new kind of data, it asks again and names what is new.

## What is sent

Two kinds of events. The field list is LADO's `telemetry.FIELDS`; "since" is the version of
that list a field came in. A test keeps this table and the code the same.

A daily report, at most once a day while LADO is used:

| field | since | what |
|---|---|---|
| `install` | 1 | a random ID made on this machine (`LADO_HOME/telemetry/id`), never linked to you |
| `lado` | 1 | LADO's version (also in each error) |
| `python` | 1 | Python's version |
| `os` | 1 | `darwin` or `linux` |
| `arch` | 1 | the machine's architecture, e.g. `arm64` |
| `installer` | 1 | `uv tool`, `pipx`, `dev` (a working copy) or `other` |
| `providers` | 1 | the installed agent CLIs and their versions |
| `kits` | 1 | the built-in kits and those from the official marketplace by name; the others only counted |
| `since` | 1 | the start of the counted time: the last report, at most 30 days back |
| `db` | 1 | `unreadable` when LADO's database could not be read; the counts are then left out |
| `sessions` | 1 | sessions started or resumed |
| `agents` | 1 | agents started, per agent CLI |
| `runs` | 1 | flow runs started |
| `gates` | 1 | flow gates opened |
| `turn_errors` | 1 | agent turns that ended on an API error |
| `lado_errors` | 1 | LADO's own unexpected errors |
| `errors_dropped` | 1 | errors not sent because too many waited |

The counts come from LADO's database when the report is sent: a session you forgot
(`lado forget`) before that is missing from them. Nothing is collected for the report in
the meantime.

An error, one event per kind of error since the last send:

| field | since | what |
|---|---|---|
| `type` | 1 | the exception's type, e.g. `KeyError` |
| `chain` | 1 | the types of the exceptions that caused it |
| `stack` | 1 | where in LADO's own code: file, function and line; other code only as `<external>` |
| `where` | 1 | the command, hook event, MCP tool, `loop`, or API route that failed, with no names or ids |
| `provider` | 1 | the agent CLI of a failing hook |
| `fingerprint` | 1 | a hash of the type and LADO's functions, to group the same error |
| `count` | 1 | how often it happened since the last send |
| `first_at` | 1 | when it happened first |
| `last_at` | 1 | when it happened last |

**Never sent:** paths, repository, session or agent names, messages, prompts, a command's
arguments, environment values, keys, or an error's text.

See exactly what the next send would post with `lado telemetry show`, or with "What is
sent" in the UI's banner and Settings.

## Where it goes

To [PostHog](https://posthog.com) Cloud EU (`eu.i.posthog.com`), over HTTPS, from LADO
itself with Python's standard library. Events create no person profiles and are not looked
up by IP address (no GeoIP), and the project discards the client's IP address.

Only a background process of LADO's (`lado telemetry send`) talks to the network: at most
once a day for the report, and when errors wait, at most every 15 minutes, giving up after
2 seconds per network operation and 30 seconds in all. When it cannot reach PostHog
(offline, a firewall, a proxy), you notice nothing: `lado telemetry status` and the
Settings section say `last try failed: <reason>`, and what waits stays bounded (at most 200
errors, none older than 30 days).

## Switching it off

Any of:

- Settings → Usage statistics → Don't send
- `lado telemetry off` (it also drops what waits)
- `DO_NOT_TRACK=1` or `LADO_TELEMETRY=0` in the environment of LADO (the UI server's for the
  UI): nothing is sent, whatever the choice

`lado telemetry status` says whether LADO sends and why not.

LADO's own tests and release checks never send: every test, the live and smoke tests
included, runs with `LADO_TELEMETRY=0`, which a guard checks for each of them (the tests of
sending post only to a local port), and the release candidate's scratch install in a fresh
home is run with it too.

## The local error journal

Whatever you choose, LADO keeps each of its unexpected errors, with its full traceback, in
`LADO_HOME/errors.jsonl` on your machine, readable by you only. It never leaves the machine
by itself. It and LADO's logs (`hooks.log`, `loop.log`, `server.log`) stay under 1 MiB each
plus one older `.1` file.
