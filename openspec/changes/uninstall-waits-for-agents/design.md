## Context

`_Uninstall._stop` (`src/lado/uninstall.py`) stops the UI server, then every session with
`runtime.stop_all` (each one marked stopped, then `tmux kill-session`), waits for each
session's loop, closes the viewers and ends LADO's tmux server when no other session is on
its socket. tmux returns from `kill-session` before the panes' processes have ended; an
agent killed by SIGHUP may run its session-end hook first (Claude Code does), which opens
`lado.db` and so makes `LADO_HOME` again if it is already deleted (proposal, Why).

Options weighed:

1. **Wait in the test only.** Cheapest; the product race stays: `~/.lado` can come back
   after a real uninstall with Claude Code agents.
2. **The uninstall waits for the panes' processes, bounded, and stops when one does not
   end** (chosen). Cost: one tmux call per session before the stop and a poll of a few
   pids; long-term, one more step of `_stop` under the rule it already has for loops.
3. **As 2, then SIGKILL what is left and go on.** Never blocks, but a killed agent leaves
   its children, and files are deleted under processes that still run.

Against AGENTS.md: neutral core (the pids come from tmux's panes, not from a provider;
works the same for every CLI); no silent drops (an agent that does not end is named with
its pid and the command, exit 1); one source of truth (the panes of the sessions being
stopped, read at that moment, not a second record of pids). ROADMAP: no coming stage
changes how sessions are stopped.

## Decisions

- **D1. The pids are taken from tmux before the stop.** A new `tmux.pane_pids(session)`
  returns the `#{pane_pid}` of every pane of the session (`list-panes -s -t =<session>`),
  none when the session or the server is gone. `_stop` takes them for every session it is
  about to stop, before `runtime.stop_all`, since afterwards the panes are gone. A UI
  viewer's session links the same windows and adds no process of its own to wait for.
- **D2. The wait comes after the loops' wait and before the viewers and the tmux server.**
  All sessions share one deadline of 10 s (`AGENTS_TIMEOUT` in `uninstall.py`, beside the
  existing timeouts), polled every 0.05 s, as `loop.wait_stopped` and `server_run.stop`
  do. Killing the tmux server is still done after; a pane process that ended is reaped by
  tmux while it runs.
- **D3. A zombie is ended.** The uninstall is not the agents' parent, so it cannot reap
  them; after the tmux server ends they are reparented and wait for init (tini in LADO's
  image, which reaps; another container's init may not). A pid counts as ended when
  `os.kill(pid, 0)` raises `ProcessLookupError` or `PermissionError` (no longer ours), or
  when its state is `Z`: `ps -o stat= -p <pid>` (POSIX, the same on Linux and macOS; when
  `ps` is missing the pid counts as running, and the 10 s bound still ends the wait).
- **D4. A process that does not end raises `runtime.LadoError`**, which `_Uninstall.run`
  already turns into exit 1 with "no repository or file was touched: run lado uninstall
  again". The text: `the agents of session "<name>" did not end in 10s (pids <a>, <b>):
  end them with kill <a> <b>`. Several sessions are named in one error.
- **D5. The wait runs with `--keep-data` too**: the requirement "Everything of this
  LADO_HOME stops" is the same for both, and the program may be removed right after.
- **D6. Tests.** Unit (`tests/test_uninstall.py`, fake tmux): the pids of the panes are
  taken before the stop; an exited child that was not reaped (a zombie) counts as ended;
  a process that does not end (a `sleep 60`, the timeout made short by monkeypatch)
  stops the uninstall with exit 1, its pid and the `kill` command in the output, and the
  repository and `LADO_HOME` untouched. Integration
  (`tests/integration/test_uninstall_process.py`, real tmux and the fake agent): the
  existing test unchanged in its checks, and a new one with `FAKE_AGENT_HANGUP_HOOK=1`
  whose agents run `lado hook` on SIGHUP: after the uninstall no pane process is alive and
  `LADO_HOME` does not exist.
