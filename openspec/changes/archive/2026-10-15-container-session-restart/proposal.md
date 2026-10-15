Task: LAD-74

## Why

In LADO's image (`docker/`) tini is PID 1 and `lado server` its child; LADO's tmux server
and the agents in it are orphans tini adopted. `docker stop`, `docker compose down`, a
restart of Docker or the machine, Docker Desktop's quit and an update to a new image send
SIGTERM to tini, which passes it to the server alone (no `-g`); ten seconds later (Docker's
default) everything left is killed. The server ends without touching its sessions, so
after the container's next start each session is "tmux session is gone", resumed by hand
in the UI one by one, and every agent's config folder under `LADO_HOME/agents/` is left
behind for `lado doctor` to warn about. This is step T6b of the Docker install plan
(docs/research/docker-install-plan.md).

Root cause: a container's sessions live exactly as long as the container, but LADO ties
them to nothing of the container: the server, the one process told of its end, neither
stops them nor, at the next start, resumes them.

## What Changes

- **The container's stop stops its sessions.** The UI server in a container
  (`update.in_container()`), when it is told to end (SIGTERM, SIGINT, `lado server stop`),
  first, before it waits for any open request or event stream, marks every session not
  stopped as stopped, as `lado stop` does, with a new mark "resume at start", all in one
  transaction; then kills each one's tmux session, closes its UI viewers and removes its
  agents' config folders. The dying agents tell no one (they find their session stopped,
  as after `lado stop`). `docker logs` gets one line naming the sessions. All of it takes
  well under a second: Docker's default ten seconds stay.
- **The container's start resumes them.** After `lado.db` is migrated (as today, before
  the server starts), the server, while it already serves, resumes one by one in the
  background: each session with the mark, and each session not stopped whose tmux session
  is gone (the container ended without the stop: `docker kill`, Docker's or the machine's
  crash, or a tmux that ended inside the container). A session the human stopped stays
  stopped. Each resume is `lado start`'s resume: the supervisor starts anew with LADO's
  `session resumed` message listing the open runs and the workers to start for them;
  workers are not restarted by LADO. A resume that fails leaves the session stopped
  without the mark, named in `docker logs` with why, and is not tried again at the next
  start. `docker logs` names each session resumed.
- **The session's journal says why.** `lado log` shows the stop as the container's and the
  resume as at the container's start.
- **Schema 29.** `sessions.resume_at_start` (0 or 1): set only by the container's stop,
  cleared by every resume in the transaction that takes the session (also one that fails
  later).
- **Outside a container nothing changes.** `lado server stop`, Ctrl-C and `lado update`'s
  stop of the server leave the sessions running, and the server's start resumes none.
- **The headers say it.** `docker/compose.yaml`'s and `docker/Dockerfile`'s headers say
  that stopping the container stops its sessions and starting it resumes them, and that
  each resumed session's supervisor takes one model turn (a cost at every start with many
  sessions).
- **Tests.** Unit (state, runtime, server), integration (a real `lado server` with
  `LADO_CONTAINER=1`, real tmux and the fake agent), and container: `compose down`/`up`,
  `docker kill`/`start`, a new image on an old home volume with a running session
  (migrated, then resumed), and two LADO containers where `compose down` of one leaves the
  other's session running.

## Scope

Changed: `src/lado/state.py` (schema 29, the mark, the container's stop in one
transaction), `src/lado/runtime.py` (the container's stop and the start's resume),
`src/lado/server/app.py` (`Server.shutdown`), `src/lado/server/run.py` (`serve` starts the
resume); `docker/compose.yaml` and `docker/Dockerfile` (headers only); tests:
`tests/test_state*.py`, `tests/test_runtime*.py` (or the files that test stop and resume),
`tests/test_server*.py`, `tests/agent_helpers.py` (`previous_schema`),
`tests/integration/` (a new file), `tests/container/` (new tests, a helper to start the
fake endpoint again); AGENTS.md (Layout: `state.py` schema 29, `runtime.py`, `server/`,
`docker/`; Commands: the container tests), CHANGELOG.md. Capability: `container` gains
requirements. No MCP tool, no CLI option, no API field, no UI change.

Version: a minor bump (behaviour of the image and a schema migration), under the version
open in main when this merges (0.39.0 now; if the 0.39.0 release candidate freezes main
first, the pull request waits for the final and goes into 0.40.0).

## Out of scope

- **Resuming sessions outside a container** (after a machine's reboot, a tmux server
  killed): the human's decision. Outside a container the server starts often (`lado ui`)
  and a gone tmux may be the human's own doing; the core's functions are general, so a
  later task can offer it (e.g. "Resume all" in the UI or `lado start --all`).
- **Restarting workers by LADO**: the human's decision. The resume is `lado start`'s: the
  supervisor gets the open runs and starts their workers (in the runs' worktrees); a worker
  outside a run is not restarted, its worktree and branch stay on disk. Every agent's
  conversation starts anew, as after `lado stop` and `lado start` today.
- **Retrying a failed resume at each start**: the human's decision; the session waits,
  stopped, for the human's resume in the UI.
- **A message to the human in the session's chat** about the stop or the resume: the
  human's decision; `docker logs` and `lado log` say it.
- **A longer `stop_grace_period`**: the stop is one transaction and a kill per session,
  well within Docker's ten seconds; a SIGKILL before it is the crash path, which resumes
  too.
- **Continuing the agents' conversations** (a CLI's own resume of its last conversation):
  LADO has none for any provider today.
- `docs/research/docker-install-plan.md`: another session's supervisor updates it.

## Impact

- Users of the image: `docker compose down`/`up`, `docker stop`/`start`, an update to a
  new version and a restart of Docker bring the sessions back by themselves; each resumed
  supervisor takes one model turn at the start. Sessions stopped by hand stay stopped.
- `lado.db`: schema 29 (one column); an older LADO refuses it as usual; the backup of
  LAD-71 is taken before the migration.
- Usage statistics: each resume at start counts as a `resume`, as any resume does.
- Spec: `container` gains five requirements.
