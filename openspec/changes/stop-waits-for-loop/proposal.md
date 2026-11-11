Task: LAD-153

## Why

Two findings of the manual check of 0.43.0rc1, still there on 0.46.0.

1. `lado doctor`'s check "Agent config folders" lists `~/.lado/agents/.DS_Store` as a folder
   left by an agent and offers `rm -rf` for it. Cause: `runtime.stray_config_dirs` takes every
   entry of `LADO_HOME/agents/` (and of a session's folder there) as a config folder, files and
   hidden names too; macOS's Finder leaves `.DS_Store` in any folder it shows.
2. `lado stop` returns before the session loop (`lado loop`) has ended. Cause: the stop marks
   the session stopped and kills its tmux session, but the loop learns of it only at its next
   pass, up to one interval (2 s) later; nothing waits for it. `lado update` and
   `lado uninstall` wait for it themselves (`loop.wait_stopped`); `lado stop`, `lado stop
   --all` and the UI's Stop do not. What follows:
   - a LADO_HOME deleted right after the stop is made again: the loop's last pass opens
     `lado.db` (made anew, `state.connect`) and writes `loop ended: the session is gone` to a new
     `loop.log`;
   - `lado stop s && lado start s` leaves the old loop alive: the new loop finds the lock held
     and exits, the old one sees the session running again and goes on. Within one version it
     is harmless; across versions (the by-hand downgrade that `lado update` prints, comment on
     0.43.0rc2) the old loop meets the other schema and ends, and the session runs with no loop
     (`lado ls`: "session loop not running").

Options weighed for 2:

- The loop writes nothing into a deleted home only: fixes the deleted home, not the stop and
  start. Cost: the race stays for every caller that expects the stop to be over.
- The stop signals the loop (a pid in the lock file, SIGTERM): returns at once, but adds a pid
  file and signal handling the loop avoids by design (agents.md: "no pid file"). Cost: a second
  way the loop ends, to keep true on every platform.
- Taken: every stop waits for the loop's end with `loop.wait_stopped`, as update and uninstall
  already do, and the loop also ends without writing when `lado.db` is gone. One rule for every
  caller (CLI, `--all`, the UI, update, uninstall); a stop takes at most one interval longer.
  Provider-neutral: the loop is LADO's own, the same for every agent CLI.

## What Changes

- `lado doctor`'s "Agent config folders" counts only folders whose name does not start with
  `.`, at both levels (`<session>` and `<session>/<agent>`); session and agent names never
  start with a dot.
- `lado stop <session>`, `lado stop --all` and the UI's Stop return only after the session's
  loop has ended. When it has not ended within `loop.wait_stopped`'s time (three intervals),
  the session stays stopped and the stop fails (exit 1) with `session "<s>" is stopped, but its
  loop did not end (LADO_HOME/loop/<s>.lock is held); see <LADO_HOME>/loop.log` (the human's
  answer #5792).
- The session loop, finding no `lado.db` in LADO_HOME before a pass, ends at once and writes
  nothing: neither `lado.db` nor `loop.log` is made again.
- A patch (0.46.1): fixes only, no MCP tool, CLI option or schema change.

## Scope

- `src/lado/runtime.py` (`stray_config_dirs`; `stop_session` and `stop_all` wait for the loop).
- `src/lado/loop.py` (`run` ends without writing when `lado.db` is gone).
- Tests: unit (`tests/test_doctor.py` or `tests/test_runtime.py`, `tests/test_loop.py`),
  integration with the fake agent (`tests/integration/test_session_loop.py`).
- `docs/cli.md` (`lado stop`), `docs/design/agents.md` (the session loop), CHANGELOG.md under
  `## 0.46.1 (unreleased)`, Fixed.

## Out of scope

- Removing the now redundant waits of `lado update` (`self_update.py`) and `lado uninstall`
  (`uninstall.py`) after their stops: they cost nothing and keep their own error texts; a
  cleanup, not a fix.
- A faster end of the loop on a stop (a signal, a wake-up): the wait is at most one interval;
  the task asks that the stop be over, not quicker.
- Other leftovers doctor does not look at (`agent-state/`, `loop/`): not in the finding.
