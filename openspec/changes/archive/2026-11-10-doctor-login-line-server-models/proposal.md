Task: LAD-262

## Why

Symptom: in a container without Claude Code's login, `lado doctor` prints
`[warn] Claude Code login: not logged in: new sessions and workers of it are refused, a
resumed agent waits (Settings → Agent CLIs)`. Since LAD-255 (0.45.0) a new session or
worker of such a CLI on a saved model of the human's model server starts all the same, so
the line misleads. Found in the manual check of 0.45.0rc2 (finding 4); the human chose to
fix it in 0.45.1.

Cause: the line was written with LAD-161 (refuse a start without a login), when every new
session and worker of a CLI that needs a login was refused. LAD-238 and LAD-255 let an
agent on a server that takes the CLI's whole process start without the login
(`runtime.check_login` returns early for such a start; `needs_login` is false in an
environment with `MODEL_SERVER`, so a resumed agent on a server's model does not wait
either). `doctor.login_check` was not part of those changes and kept the old words.

Options weighed:

- A (taken, the human's choice): one short line, true whatever is saved:
  `not logged in: only its agents on your model server's models start; log in in
  Settings → Agent CLIs for its own models`. That a resumed agent on the CLI's own models
  waits is shown at the agent itself in the UI. Long-term cost: none; a text.
- B: the full line naming both cases (server's models start; own models are refused and a
  resumed agent waits). Always true too, but long; the human preferred the short one.
- C: two texts, by whether a model of a server is saved. `lado doctor` would read lado.db
  for one line and repeat the rule of the New session window (`starts_on_server`): a
  second source of truth for a line that is true without it.

## What Changes

- `src/lado/doctor.py` (`login_check`): the `warn` line of a CLI whose agents need a login
  and have none becomes `not logged in: only its agents on your model server's models
  start; log in in Settings → Agent CLIs for its own models` (Settings' name from
  `logins.SETTINGS`). Level `warn`, exit code, the keyring, `none` and `unknown` lines
  unchanged. The same text for Claude Code and Codex: both take a server's whole process.
- `tests/test_doctor.py`: the three places that quote the old line.
- `docs/cli.md`: the doctor paragraph quotes the new line (and drops its stale `and
  environment` after `Settings → Agent CLIs`).
- CHANGELOG.md: a line under `## 0.45.1 (unreleased)`, group Fixed.

## Scope

- The text of `lado doctor`'s login line for a CLI without the login its agents need.

## Out of scope

- Settings → Agent CLIs' rows, the New session window, the refusals and the wait texts of
  `lado.logins`: true already (LAD-255); unchanged.
- Naming in the line whether a model of a server is saved (option C): see Why.
- OpenCode and Kilo CLI: they never need a login for a server's model; their `info none`
  line stays.

## Impact

- A user-visible text of `lado doctor`; no API, MCP, CLI option or schema change. Patch:
  0.45.1.
