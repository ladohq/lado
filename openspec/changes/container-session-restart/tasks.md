Tests first in each section; each task is one commit. The plan with the code is
`docs/superpowers/plans/2026-10-15-container-session-restart.md`.

## 1. Schema 29 and the container's stop in lado.db

- [ ] 1.1 Unit tests (layer 1), `tests/test_state.py`: `stop_for_container` marks every
  running session stopped with `resume_at_start` in one transaction, the human's stopped
  one untouched, the stop's detail ends with `; the container stopped`; any resume clears
  the mark; `give_up_resume` clears it and stops a not-stopped session with `session_gone`;
  `resumable`; the migration 28 → 29. Plan, Task 1.
- [ ] 1.2 `state.py` (D2, D3, D6, D7) and `agent_helpers.schema_before`. `uv run pytest
  tests/test_state.py tests/test_usage.py -n auto`, `make lint`.

## 2. runtime: stop for the container, resume at start

- [ ] 2.1 Unit tests, `tests/test_runtime.py`: kills after the mark, viewers and config
  folders, a failing kill does not stop the rest, no `lado.db` makes nothing; which
  sessions resume, the lines, a failure gives up and goes on, `stopping`; the resume's
  event detail with `reason`. Plan, Task 2.
- [ ] 2.2 `runtime.stop_for_container`, `runtime.resume_at_start`, `start_session(reason=)`
  (D3-D7, D10). `uv run pytest tests/test_runtime.py -n auto`.

## 3. The UI server, only in a container

- [ ] 3.1 Unit tests, `tests/test_server*.py`: in a container `Server.shutdown` stops the
  sessions before `Hub.close` and prints the stop's line; outside one it calls nothing;
  `serve` starts the resume thread only in a container. Plan, Task 3.
- [ ] 3.2 `server/app.py`, `server/run.py` (D1, D8, D9). `uv run pytest
  tests/test_server*.py -n auto`.

## 4. Integration (layer 2)

- [ ] 4.1 `tests/integration/test_container_sessions.py`: a real `lado server` with
  `LADO_CONTAINER=1` and the fake agent: SIGTERM stops with the mark, no messages, folders
  gone; a new server resumes (supervisor idle, `session resumed: 1 open runs`); the crash
  path; a hand-stopped session stays; a failure is not retried; without `LADO_CONTAINER`
  nothing changes. `uv run pytest -m integration -n auto
  tests/integration/test_container_sessions.py`.

## 5. The headers and the container tests (layer 7)

- [ ] 5.1 `tests/test_docker.py`, then the headers of `docker/compose.yaml` and
  `docker/Dockerfile` (sessions follow the container, the model turn). `uv run pytest
  tests/test_docker.py -n0`.
- [ ] 5.2 `tests/container/test_sessions.py`: compose down/up with a hand-stopped session
  beside, `docker kill`/start, three sessions within ten seconds, a new image migrates then
  resumes (`old_home(running=True)`); `test_two_lados.py`: down of one leaves the other's
  session (D11, D12). `make docker && make test-container`.

## 6. Documents and regression

- [ ] 6.1 AGENTS.md (Layout, Commands) and CHANGELOG.md under the version open in main.
- [ ] 6.2 Regression: `make lint`, `make test`, the changed integration files with `-m
  integration`, `openspec validate --specs --strict`, `make docker && make
  test-container`; CI's `ci-ok` on the pull request.
- [ ] 6.3 The pull request's description has the design doc's manual check verbatim.
