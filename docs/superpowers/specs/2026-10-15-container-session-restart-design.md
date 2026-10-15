# Sessions stop and resume with LADO's container (LAD-74)

Change: `openspec/changes/container-session-restart/` (proposal, delta spec of `container`,
`design.md` with the decisions D1-D12). This document is the human's view: what a user of
the image gets, what is accepted, and how the human checks it.

## What a user gets

Today, after `docker compose down` and `up`, a restart of Docker or the Mac, or an update
to a new image, every session of the container shows "tmux session is gone" and has to be
resumed by hand in the UI, and `lado doctor` warns about agent config folders left behind.

After this change:

- **Stopping the container stops its sessions.** `docker compose down`, `docker compose
  stop`, `docker stop`, Docker Desktop's quit or a machine's shutdown: LADO marks every
  running session stopped, as `lado stop` would, remembering to resume it, then ends its
  agents and removes their config folders. `docker logs` says:
  `lado: the container stops: stopped sessions "app", "docs"; they resume at its start`.
- **Starting the container resumes them.** After the database is migrated (a new image),
  LADO resumes them one by one while the UI already answers:
  `lado: resumed session "app" at the container's start`. Each supervisor starts anew,
  gets `session resumed` with the open flow runs and starts the workers those runs need.
- **A container killed without warning** (`docker kill`, Docker's crash, a power cut):
  its sessions were never stopped, and their tmux is gone at the start, so they are
  resumed too.
- **Sessions you stopped yourself stay stopped.**
- **A resume that fails** (its folder gone, a kit removed) leaves the session stopped,
  with `lado: could not resume session "app" at the container's start: <why>; it stays
  stopped` in `docker logs`; it is not tried again at the next start. Resume it from the
  UI once fixed.
- **Each container is on its own**: stopping or starting one LADO container changes no
  session of another.
- `lado log <session>` shows the stop as `the container stopped` and the resume as `at the
  container's start`.

What it costs: each resumed session's supervisor takes one model turn at the start (it
reads `session resumed`). Workers outside flow runs are not restarted; their worktrees and
branches stay. Every agent starts a new conversation, as after `lado stop` and `lado
start`.

Outside Docker nothing changes: stopping the UI server leaves the sessions running, and
after a reboot sessions are resumed by hand, as today.

## Acceptance criteria

- **AC-1.** In a container, `docker compose down` with a running session prints the stop's
  line, the container exits with 0, and the session is stopped with the mark.
- **AC-2.** `docker compose up -d` after AC-1: the session runs again, its supervisor gets
  to idle, `docker logs` has the resumed line, and `lado doctor` has no warning about agent
  config folders.
- **AC-3.** `docker kill` of a container with a running session, then `docker start`: the
  session runs again with its supervisor idle; no config-folder warning.
- **AC-4.** A new image on a home volume with the schema before and a session not stopped:
  the upgrade line comes before the resumed line, and the session runs.
- **AC-5.** A session stopped by hand before the container's stop stays stopped after its
  start and is named in neither line.
- **AC-6.** A resume that fails: the failure line with its reason, the session stopped
  without the mark, the other sessions resumed, and nothing tried at the next start.
- **AC-7.** No message from `lado` to the human or the supervisor about agents ending at
  the container's stop.
- **AC-8.** Outside a container `lado server stop` leaves a running session running, and a
  new `lado server` resumes nothing.
- **AC-9.** Two LADO containers: `docker compose down` of one leaves the other's session
  running, with the same supervisor process.
- **AC-10.** Three running sessions stop within Docker's default ten seconds (exit code 0).
- **AC-11.** The compose and Dockerfile headers say that sessions stop and resume with the
  container and name the supervisor's model turn at each start.

## Manual check on a Mac (for the pull request)

Branch: the pull request's, `feature/lad-74-container-session-restart`.

1. In a checkout of the branch: `git fetch origin && git checkout
   feature/lad-74-container-session-restart && git pull`, then `make docker` (builds
   `lado:local`).
2. `env | grep LADO` in the same terminal. If it prints `LADO_PORT`, `LADO_PROJECTS`,
   `LADO_IMAGE`, `LADO_VERSION` (or any other `LADO_` variable left from an earlier
   check), `unset` each of them: a shell variable beats `.env`.
3. A folder for the check:
   `mkdir -p ~/lado-check-74 && cp docker/compose.yaml ~/lado-check-74/ && cd
   ~/lado-check-74`, and an `.env` there:

   ```
   COMPOSE_PROJECT_NAME=lado-check-74
   LADO_IMAGE=lado:local
   LADO_VERSION=test
   LADO_PORT=8799
   LADO_PROJECTS=/Users/<you>/projects
   ```

4. `docker compose up -d`, then log Claude Code in once in the new home volume:
   `docker compose exec -it lado claude` (`/login`, then exit). Open the UI:
   `docker compose exec lado lado ui --no-open` and open the printed link.
5. In the UI start two sessions on two repositories under your projects folder; wait until
   both supervisors are idle. Stop the second one by hand (Stop in its head).
6. `docker compose stop && docker compose logs lado | tail -5`: expected the line
   `lado: the container stops: stopped sessions "<first>"; they resume at its start`
   (not the second one).
7. `docker compose start`, then `docker compose logs lado | tail -5`: expected
   `lado: resumed session "<first>" at the container's start`. In the UI the first session
   runs and its supervisor gets to idle after one turn; the second is still stopped.
   `docker compose exec lado lado doctor`: no `Agent config folders` warning.
8. `docker compose down`, then `docker compose up -d` (a new container on the same home
   volume): the same as step 7.
9. `docker compose kill`, then `docker compose start`: the first session runs again
   (`docker compose logs lado` has the resumed line; no stop line before it).
10. Clean up only this check's own things: `docker compose down -v` in
    `~/lado-check-74` (its container and its own home volume), then `rm -rf
    ~/lado-check-74`. No `docker system prune` or `docker volume prune`.
