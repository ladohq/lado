## Context

LADO's image (`docker/Dockerfile`) runs `ENTRYPOINT ["/usr/bin/tini", "--",
"/usr/local/bin/lado-entrypoint"]` and `CMD ["sh", "-c", "exec lado server --host 0.0.0.0
--port \"$LADO_PORT\""]`; the entrypoint and `sh` both `exec`, so `lado server` is tini's
only child. tini without `-g` sends a signal it gets to that child alone. LADO's tmux
server daemonizes (it is reparented to tini), and the agents are its panes' processes, so
no signal reaches them before Docker's SIGKILL at the end of the grace period (ten
seconds by default, `stop_grace_period` in compose, `--stop-timeout` for `docker run`).

`lado server` (`server/run.serve`) runs uvicorn with `app.Server`, whose `shutdown` already
ends the event streams (`Hub.close`) and cancels clone jobs before uvicorn's own shutdown
waits for open responses (`SHUTDOWN_GRACE`, 1 s); `serve` turns SIGTERM into `SystemExit`
after uvicorn returns. Before the command, `cli.main` runs `runtime.migrate_if_safe()`; in a
fresh container no tmux session exists, so a new image's migration always goes through
(with LAD-71's backup) before `serve` runs.

`runtime.stop_session` marks a session stopped (`state.stop_session`: agents forgotten,
unreceived messages dropped, `session_stop` event), then kills its tmux session, closes the
UI's viewers and removes the agents' config folders; the dying agents' session-end hooks
find their agents gone and tell no one. `runtime.start_session(resume=True)` resumes a
stopped session, and also one not stopped whose tmux is gone (it writes `session_gone`
and stops it first); `state.resume_session` takes it in one conditional transaction; a
launch that fails is undone by `state.fail_resume`, which leaves it stopped. `runs.resume`
queues the supervisor's `session resumed` message with each open run's next move.

Root cause: a container's sessions cannot outlive it, but nothing ties them to its end or
its start.

## Options

1. **The server stops the sessions with a mark in `lado.db`, and resumes the marked and
   the gone ones at its start** (chosen). One more column; the stop's state is exact and
   transactional; the resume is the existing `lado start` path. Long-term cost: a schema
   step and a column only the container sets now, which a later "resume after reboot" task
   outside a container can reuse.
2. **Do not stop at all: at the start resume every session not stopped whose tmux is
   gone.** No schema, one path for a clean stop and a crash. But the agents killed by the
   container end through their own session-end hooks while the session is not stopped:
   `agent_ended` would message the supervisor and the human about each, and drop their
   messages one agent at a time; and the config folders would stay until the start. To
   avoid that the session must be marked before the kill, which is option 1.
3. **A file in `LADO_HOME` listing the sessions to resume** (written at the stop, read and
   removed at the start). No schema, but a second source of truth beside `stopped_at`,
   not in the stop's transaction: a SIGKILL between the two writes loses or doubles a
   session, and `lado forget` or a hand resume would have to keep the file right too.

Held against ROADMAP.md and AGENTS.md's principles: nothing under `providers/` changes and
the resume is the provider-neutral `start_session` (every provider resumes as today:
Claude Code, Codex with its `FIRST_INPUT`, OpenCode and Kilo with `--prompt`); one source
of truth (`sessions.stopped_at` and `resume_at_start`, written together); no silent drop
(each failed resume is a `docker logs` line and the session is visibly stopped); only what
is used (no option to switch it off, no new API field; the column is read by the start).

## Decisions

- **D1. Where the stop runs.** First thing in `app.Server.shutdown`, before `Hub.close`,
  through `run_in_threadpool`, only when `update.in_container()`: uvicorn calls `shutdown`
  as soon as its main loop sees the exit flag (within 0.1 s of the signal) and only then
  waits for connections, so the open UI streams cannot eat the grace period. Not in the
  lifespan's shutdown, which runs after uvicorn waited for open responses. SIGTERM, SIGINT
  and `lado server stop` (a SIGTERM) all go this way.
- **D2. The mark is a column, schema 29.** `sessions.resume_at_start INTEGER NOT NULL
  DEFAULT 0` (`SESSIONS_RESUME_AT_START`, one `ALTER TABLE` step in `MIGRATIONS`, in
  `SCHEMA` too); `tests/agent_helpers.schema_before` undoes it (drop the column). Not in
  `state.Session`'s API model (`SessionInfo`) and not shown in the UI: only the start reads
  it. `state.Session` gets a field `resume_at_start: bool = False` read from the row.
- **D3. One transaction, then the kills.** `state.stop_for_container()` takes the write
  lock, and for every session with `stopped_at IS NULL` runs `_stop_session(db, name, "; the
  container stopped")` and sets `resume_at_start = 1`, then commits; it returns the names.
  Only after that `runtime.stop_for_container()` kills each one's tmux session
  (`tmux.kill_session`; one already gone is fine), then `terminal.close_viewers(name)` and
  `providers.base.remove_session_config_dirs(name)` for each. A SIGKILL before the commit
  leaves the sessions not stopped (the crash path of D5 resumes them); after it, the state
  is final and only processes the container's end takes anyway are left. A kill that fails
  is one stderr line and the others go on (the container ends right after).
- **D4. A tmux session per session, not `tmux kill-server`.** The same as `lado stop`, on
  this LADO's socket; it never touches another `LADO_HOME`'s session on a shared socket (a
  developer's machine running the integration test with `LADO_CONTAINER=1`).
- **D5. Which sessions resume.** `runtime.resume_at_start()` lists, in creation order, the
  sessions stopped with `resume_at_start = 1` and the sessions not stopped whose
  `session_status` is `TMUX_GONE` (in a fresh container every one not stopped). A session
  `RUNNING` or `LOOP_DOWN` (only possible outside a real container, in a test) is left
  alone. A session stopped without the mark is never resumed.
- **D6. The resume is `start_session`.** `start_session(sess.repo, sess.name, None,
  resume=True, reason="at the container's start")`: a new keyword `reason` that only
  prefixes the `session_resume` event's detail (`at the container's start; same
  settings`). `state.resume_session` clears `resume_at_start` in its taking `UPDATE` (every
  resume, the human's too, so a hand resume during a later run cannot leave a stale mark).
- **D7. A failed resume gives up in one transaction.** When `start_session` raises,
  `resume_at_start` calls `state.give_up_resume(name)`: in one transaction it clears the
  mark and, for a session still not stopped (it failed before taking it: its folder gone,
  a kit missing), writes `session_gone` and stops it as `stop_session(gone=True)` does. So
  a failure is never tried again at the next start, and a crash-path session does not stay
  "tmux gone" forever. A failure after the take is already stopped by `fail_resume` with
  the mark cleared by D6. The others go on.
- **D8. The resume runs in the background while the server serves.** `serve` starts a
  daemon thread after the socket listens and before `server.run`, only in a container; the
  thread resumes one session at a time (each launch resolves the login shell, up to
  `agent_env.TIMEOUT`), so `/api/health` answers at once and the UI shows the sessions as
  they come through the feed. A `threading.Event` on `app.state` (`stopping`) is set at the
  start of `Server.shutdown`; the thread checks it before each session. A session whose
  start is under way when the stop comes is marked by D3 if it was taken already (its
  window ends with the container), else it is still stopped with its mark.
- **D9. The lines.** On stderr, flushed, from the server's process (`docker logs`): the
  stop's one line, one per resumed session, one per failure (texts in the delta spec). The
  events' details carry the same in `lado log`.
- **D10. No LADO_HOME, no stop.** The stop does nothing when `state.home_path() /
  "lado.db"` does not exist (an uninstall deleted it), so a server's exit never makes
  `LADO_HOME` again (capability `server-stop`).
- **D11. Grace period unchanged.** The stop is a transaction and a few `tmux` calls;
  measured in the container test with three sessions, the container's exit code is 0
  under Docker's default ten seconds. No `stop_grace_period` in compose.
- **D12. Proof that the signal reaches the server.** Not inferred from the image: the
  container tests check the stop's line in `docker logs`, the exit code 0 and the marks
  in `lado.db` after `docker compose down` and after `docker stop`.

## Risks / Trade-offs

- Each resumed supervisor takes a model turn on `session resumed` at every start: a cost
  with many sessions; the headers say so (the human's decision to keep it automatic).
- Agents' conversations start anew (as after `lado stop`); work in progress in a turn is
  cut at the stop; files written stay in the worktrees.
- A session whose tmux ended inside a running container for another reason is resumed at
  the next start too (D5): acceptable in a container, said in the spec.
- A schema step: an older image refuses the upgraded `lado.db`; the way back is LAD-71's
  backup, as for any migration.
