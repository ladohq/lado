## ADDED Requirements

### Requirement: The container's stop stops its sessions for a resume

When the UI server runs in a container (`update.in_container()`) and is told to end
(SIGTERM, SIGINT, `lado server stop`), it SHALL, before it waits for any open request or
event stream, mark every session not stopped as stopped, as `lado stop` marks one (its
agents forgotten, messages they never got dropped, open runs and gates kept), with the mark
`resume_at_start` set, all sessions in one transaction; and only then kill each one's tmux
session, close its UI viewers and remove its agents' config folders. The `session_stop`
event's detail SHALL end with `; the container stopped`. It SHALL print one line on stderr
(`docker logs`): `lado: the container stops: stopped sessions "<a>", "<b>"; they resume at
its start`, and none when no session ran. A session stopped already keeps its mark as it
is. The agents that end by this SHALL tell no one, as after `lado stop`. When `lado.db`
does not exist, it SHALL do nothing and make no `LADO_HOME`.

#### Scenario: compose down with a running session
- **WHEN** a session runs in a container of `docker/compose.yaml` and the human runs
  `docker compose down`
- **THEN** `docker logs` has the line naming the session, the container exits with 0 (not
  killed after the grace period), and the home volume's `lado.db` has the session stopped
  with `resume_at_start` 1

#### Scenario: Within Docker's default grace period
- **WHEN** a container with three running sessions gets `docker stop` with Docker's default
  ten seconds
- **THEN** the container's exit code is 0 and all three sessions are stopped with the mark

#### Scenario: No message about the dying agents
- **WHEN** the container's stop ends a session whose supervisor and worker run
- **THEN** no message from `lado` to the human or the supervisor is queued about their end,
  and `lado log` shows the session's stop with `the container stopped`

#### Scenario: A session the human stopped
- **WHEN** a session was stopped with `lado stop` before the container's stop
- **THEN** it stays stopped without the mark, and the stop's line does not name it

#### Scenario: Nothing ran
- **WHEN** the container stops with no session running
- **THEN** `docker logs` has no line about sessions

#### Scenario: The server's stop after an uninstall
- **WHEN** the server in a container ends after `LADO_HOME` was deleted
- **THEN** no `LADO_HOME` is made again

### Requirement: The container's start resumes its sessions after the migration

When the UI server starts in a container, after `lado.db` is migrated (the CLI migrates
before the command, as before), it SHALL resume in the background, while it already
serves, one session at a time: each stopped session with `resume_at_start` set, and each
session not stopped whose tmux session is gone (the container ended without its stop:
`docker kill`, a crash of Docker or the machine, or a tmux that ended inside the
container). It SHALL NOT resume a session stopped without the mark. Each resume SHALL be
`lado start`'s resume of that session with its stored repository and settings, its
`session_resume` event's detail starting with `at the container's start`, and SHALL clear
`resume_at_start` in the transaction that takes the session. `docker logs` SHALL get
`lado: resumed session "<name>" at the container's start` for each one resumed, and
`lado: could not resume session "<name>" at the container's start: <error>; it stays
stopped` for one that fails, which stays stopped without the mark and is not tried at the
next start; the others SHALL go on. Workers SHALL NOT be restarted by LADO: the
supervisor's `session resumed` message names the open runs and the workers to start for
them, as after `lado start`. When the server is told to end while it resumes, it SHALL
resume no further session.

#### Scenario: compose up after compose down
- **WHEN** after `docker compose down` with a running session the human runs `docker
  compose up -d`
- **THEN** the session runs again, its supervisor gets to idle, `docker logs` has the
  resumed line, `resume_at_start` is 0, and `lado doctor` warns about no agent config
  folder

#### Scenario: A container killed without SIGTERM
- **WHEN** a session runs and the container is ended with `docker kill`, then started
- **THEN** the session runs again with its supervisor idle and `lado doctor` warns about
  no agent config folder

#### Scenario: A new image on the home volume
- **WHEN** a container of a new LADO image starts on a home volume whose `lado.db` has the
  schema before and a session not stopped
- **THEN** `docker logs` has the upgrade line before the resumed line, `lado.db` has this
  LADO's schema and the session runs

#### Scenario: A session the human stopped stays stopped
- **WHEN** the container starts with a session stopped by `lado stop`
- **THEN** that session is still stopped and `docker logs` does not name it

#### Scenario: A resume that fails
- **WHEN** a session with the mark cannot be resumed at the start (its repository folder
  is gone)
- **THEN** `docker logs` has the failure line with the reason, the session is stopped with
  `resume_at_start` 0, the other sessions are resumed, and at the container's next start
  it is not named

#### Scenario: An open run's worker
- **WHEN** a session with an open run whose step is a worker's is resumed at the start
- **THEN** only its supervisor runs, and its first message from `lado` is `session
  resumed: 1 open run` naming the worker to start with `spawn_worker`

### Requirement: Outside a container the server's stop and start leave the sessions

When LADO does not run in a container, the UI server's end (`lado server stop`, SIGTERM,
Ctrl-C, `lado update`'s stop) SHALL change no session, and its start SHALL resume none.

#### Scenario: lado server stop on a machine
- **WHEN** a session runs and `lado server stop` ends the UI server without
  `LADO_CONTAINER`
- **THEN** the session still runs, and a new `lado server` resumes nothing

### Requirement: Stopping one LADO container leaves another's sessions

Stopping or starting one LADO container SHALL change no session of another LADO container
on the same machine.

#### Scenario: compose down of one of two
- **WHEN** two compose projects of `docker/compose.yaml`, each in its own folder with its
  own `.env`, each run a session, and the first runs `docker compose down`
- **THEN** the second's session still runs with its supervisor's same process, and the
  second's `lado.db` has no session stopped

### Requirement: The headers say that sessions follow the container

`docker/compose.yaml`'s header SHALL say that `docker compose down` (or stop) stops the
container's sessions and `docker compose up -d` resumes them, except those stopped by
hand, and that each resumed session's supervisor takes one model turn at the start; the
Dockerfile's header SHALL say the same for `docker stop` and `docker start`.

#### Scenario: The headers
- **WHEN** a unit test reads both headers
- **THEN** each says that the sessions stop with the container and resume at its start, and
  names the supervisor's model turn
