Task: LAD-50

## Why

LADO's usage statistics and error reports go to PostHog (openspec change usage-telemetry).
They are only worth reading when they count real use: a test run, a live test or the
human's own check of a release candidate must add no install, no session and no error.

What holds today (main, 1b19e4c):

- Every test of the suite, the live and smoke tests included (they live under `tests/`),
  runs under the root `tests/conftest.py`, which sets `LADO_TELEMETRY=0` and drops
  `DO_NOT_TRACK` and `LADO_TELEMETRY_URL` for the whole run. Every LADO process a test
  starts (hooks, `lado mcp`, the session loop, the UI server, the detached sender) inherits
  it; agents in tests take the test's environment (`LADO_AGENT_ENV=inherit`), not the
  login shell's.
- Sending also needs the human's yes in `LADO_HOME/telemetry/consent.json`, and every test
  has a temporary `LADO_HOME` without one.
- The tests of sending (`telemetry_on`, `telemetry_endpoint`) post only to a local port
  with the test token. CI calls pytest, so the same conftest. The Windows probe runs
  `lado doctor` outside pytest on a fresh runner with no yes, and `lado doctor` never asks.
  The Release workflow's token check (`scripts/check_telemetry.py`) makes one `/flags`
  request, which stores no event.

Two gaps:

1. **Nothing checks it.** The suite's guarantee is one line of `tests/conftest.py`. A
   change that drops it, or a test that switches sending on without the fixtures, fails
   nothing; only the missing yes in the temporary home would still hold.
2. **The release candidate's manual checklist can count.** docs/release.md section 4 has
   the human install the RC in a fresh home (`LADO_HOME=$(mktemp -d) ... uvx --from
   lado==X.Y.ZrcN lado start <scratch repository>`). `lado start` on a terminal asks the
   statistics question (`telemetry.ask_if_needed`); a yes there makes a new install id
   with one scratch session, which PostHog counts as a new user, each RC again.

## What Changes

- **A guard of the suite** (`tests/conftest.py`): an autouse fixture that, for every test
  (unit, integration, UI, smoke, live), checks before the test that sending is off by
  `LADO_TELEMETRY=0` in the test's process, and after it that the test's `LADO_HOME` holds
  nothing sent or queued (`telemetry/sent.json`, `telemetry/outbox/*`), unless the test
  took `telemetry_on` (directly or through `telemetry_endpoint` or a fixture built on it),
  which points sending at a local port.
- **A unit test of the inheritance** (`tests/test_isolation.py`): a `lado telemetry status`
  run as a subprocess of the test says statistics are off by `LADO_TELEMETRY=0`, so the
  setting reaches LADO's own processes.
- **The RC's scratch install never asks** (docs/release.md, section 4): its commands start
  with `LADO_TELEMETRY=0`, with one sentence why (a fresh home is a new install to
  PostHog); a unit test keeps every `LADO_HOME=$(mktemp -d)` of docs/release.md with
  `LADO_TELEMETRY=0` in the same command. The upgrade of the human's own LADO to the RC
  stays as it is: it is the human's own install, counted once as before.
- docs/telemetry.md: one paragraph, LADO's own tests and release checks never send.
- AGENTS.md (Commands, the tests' environment): the guard named next to `LADO_TELEMETRY=0`.

## Scope

The test suite's fixtures, two unit tests, docs/release.md section 4, docs/telemetry.md
and AGENTS.md. No change to `lado.telemetry`, the CLI, the UI, the API or the schema.
A patch release (tests and docs only); no CHANGELOG.md line, as users see nothing.

## Out of scope

- A default `LADO_TELEMETRY_URL` at a closed local port for the whole suite (a third
  barrier): it would change what every test's telemetry state shows (an endpoint, the test
  token) and gives nothing the guard and the two barriers do not.
- Not sending from a LADO installed from a folder (`installer: dev`): it would change
  behaviour for people who install LADO so; their reports are already marked `dev` and can
  be filtered in PostHog (the human agreed).
- A clearer RC checklist and a script that runs it: LAD-51, derived from this task; that
  script must run its LADO with `LADO_TELEMETRY=0`, which the docs test of this change
  holds for docs/release.md.
- PostHog's own filters (internal users, test accounts): PostHog's settings, not LADO's.

## Impact

- `tests/conftest.py`, `tests/test_isolation.py`, a docs test (`tests/test_telemetry.py`).
- `docs/release.md`, `docs/telemetry.md`, `AGENTS.md`.
- Spec `usage-telemetry`: the requirement "Tests never send" is widened to the guard and
  the release candidate's checklist.
