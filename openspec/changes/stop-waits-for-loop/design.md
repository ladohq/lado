## Context

`runtime.stray_config_dirs` lists the entries of `LADO_HOME/agents/` and of each running
session's folder there; `runtime.stop_session` marks the session stopped and kills its tmux
session; the loop (`loop.run`) notices at its next pass (`why_stop`) and ends, writing why to
`loop.log`. `loop.wait_stopped(session, timeout=None)` waits up to three intervals for the
loop's lock to be free; `lado update` and `lado uninstall` already call it after their stops.

## Decisions

**D1. doctor skips files and hidden names.** In `stray_config_dirs` an entry counts only when
`entry.is_dir()` and `not entry.name.startswith(".")`, at the root and inside a session's
folder. Session names are lower-case letters, digits and `-`, agent names likewise, so no
real config folder starts with a dot. A link to a folder counts as a folder, as before.

**D2. Every stop waits for the loop.** `stop_session` waits with `loop.wait_stopped(session)`
after `_mark_stopped` (both of its paths: the migration path waits already in
`_kill_for_migration`, so only the plain path adds the wait). When it returns False, it raises
`LadoError(f'session "{session}" is stopped, but its loop did not end (LADO_HOME/loop/{session}.lock is held); see {state.home_path() / "loop.log"}')`.
`stop_all` stops (marks and kills) every session first without waiting, then waits for each
loop, so N sessions wait about one interval in all, not N; a loop that did not end is one of
its failures with the same text. The CLI (`cmd_stop`) prints nothing new on success; the
UI's `POST /api/sessions/{name}/stop` gets the wait and the error through `stop_session`
(the error shows as the stop's error, as a failed kill does today). The timeout is
`wait_stopped`'s default (three intervals, 6 s), the same as update and uninstall.

**D3. The loop ends without writing when lado.db is gone.** At the top of each pass, before
`why_stop`, `loop.run` checks `(state.home_path() / "lado.db").exists()`; when it is missing it
returns 0 without `log` (the line would make LADO_HOME again) and without `telemetry.kick`.
This covers a home deleted while a loop still runs (a stop that timed out, a home removed by
hand). The lock file is under the deleted home and goes with it.

**D4. Tests.** doctor: unit (pure logic over a folder). The loop's check: unit, `loop.run` in
the test's process with a fake tmux. The stop's wait and the deleted home: integration with
the fake agent, since they cross processes (the CLI, the hidden loop, tmux); the integration
interval is 0.25 s (`tests/integration/conftest.py`), so the test waits several intervals
(e.g. 2 s) after deleting the home before it asserts nothing is there.

**D5. Version.** A patch, into 0.46.1: fixes only, no MCP tool, CLI option or schema change.
