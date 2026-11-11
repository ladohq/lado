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
`stop_session` and `stop_all` take `wait=False` for a caller that waits itself: `lado update`
(`self_update.py`), which must put the session among the ones it stopped before a loop that
does not end can fail it, or its resume after a failed update would leave that session stopped,
and `lado uninstall`; both keep their own wait and its error text. The UI's Stop shows
"Stopping…" for as long as its request runs, with no request timeout, so its wait of up to
about 6 s shows as that.

**D3. The loop ends without writing when lado.db is gone.** At the top of each pass, before
`why_stop`, `loop.run` checks `(state.home_path() / "lado.db").exists()`; when it is missing it
returns 0 without `log` (the line would make LADO_HOME again) and without `telemetry.kick`.
This covers a home deleted while a loop still runs (a stop that timed out, a home removed by
hand). The lock file is under the deleted home and goes with it. The same check runs before
taking the lock (which would make `LADO_HOME/loop/` again) and after a pass, before the
statistics kick (`telemetry.kick` makes LADO_HOME again). A home deleted in the middle of a
pass, not before it, was made again by that pass's own connection, its `loop.log` line or
its journal line (the review's F2, seen in the integration test under load): while the loop
runs, `state.home_not_made` keeps its process from making either, `state.home()` making no
folder and a connection opening only a `lado.db` that is there (sqlite `mode=rw`). The rest of
the pass then fails, and the loop, finding the home gone after a failed pass, ends without a
line. A folder a pass makes below the home with `mkdir(parents=True)` would still make it; no
pass of the loop does so in the deleted-home case the tests cover.

**D3a. A hook writes nothing into a deleted home** (the review's F1). The session-end hook of
an agent the stop killed may run after `lado stop` returned and the home was deleted; `stop`
does not wait for the agents' processes. `hooks.main` exits 0 at once when `lado.db` is gone,
before any connection (`state.get_agent` would make it) or `hooks.log` line.

**D4. Tests.** doctor: unit (pure logic over a folder). The loop's check: unit, `loop.run` in
the test's process with a fake tmux. The stop's wait and the deleted home: integration with
the fake agent, since they cross processes (the CLI, the hidden loop, tmux); the integration
interval is 0.25 s (`tests/integration/conftest.py`), so the test waits several intervals
(e.g. 2 s) after deleting the home before it asserts nothing is there.

**D5. Version.** A patch, into 0.46.1: fixes only, no MCP tool, CLI option or schema change.
