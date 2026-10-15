# Sessions follow LADO's container Implementation Plan

**Goal:** In a container, the UI server's end stops every running session with a mark, and
its start (after the migration) resumes the marked sessions and those whose tmux is gone;
outside a container nothing changes.

**Architecture:** `state.py` gets schema 29 (`sessions.resume_at_start`), a one-transaction
container stop (`stop_for_container`) and a give-up (`give_up_resume`); `resume_session`
clears the mark. `runtime.py` gets `stop_for_container()` (marks, then kills, viewers,
config folders) and `resume_at_start(report, stopping)` (picks and resumes one by one
through `start_session(..., reason=...)`). The UI server calls the first at the start of
`app.Server.shutdown` and starts the second in a daemon thread in `run.serve`, both only
when `update.in_container()`.

**Tech Stack:** Python (SQLite, uvicorn, pytest, pytest-xdist), tmux, Docker and Docker
Compose for the container tests.

**Spec:** `openspec/changes/container-session-restart/` (proposal, `design.md` D1-D12,
delta spec `container`) and
`docs/superpowers/specs/2026-10-15-container-session-restart-design.md` (AC-1..AC-11,
manual check).

## Global Constraints

- Texts, verbatim (stderr of the server's process, flushed):
  - stop: `lado: the container stops: stopped sessions "a", "b"; they resume at its start`
    (names quoted, in creation order, `", "` between; no line for none)
  - resumed: `lado: resumed session "a" at the container's start`
  - failed: `lado: could not resume session "a" at the container's start: <error>; it
    stays stopped` (`<error>` is `str(exception)`, its first line)
  - `session_stop` detail: `<n> messages dropped; the container stopped`
  - `session_resume` detail: `at the container's start; <changes or "same settings">`
- Only `update.in_container()` switches it on; nothing under `providers/` changes.
- Schema: `SCHEMA_VERSION = 29`, a step in `MIGRATIONS[28]`, `SCHEMA` gets the column,
  `tests/agent_helpers.schema_before` undoes it (`ALTER TABLE sessions DROP COLUMN
  resume_at_start`; SQLite ≥ 3.35, as for the step before).
- No `stop_grace_period`, no `tini -g`, no new option, API field or UI change.
- Container tests: only the run's own containers and volumes, by name; never `docker
  system prune` or `docker volume prune`.
- Don't touch `docs/research/docker-install-plan.md`.
- Commit messages: a plain English sentence ending in `(LAD-74)`.

## Review Focus

- The stop must run before `Hub.close` and uvicorn's wait (D1); a test pins the order.
- One transaction marks all sessions (D3); a kill that fails does not stop the others.
- Every path out of a resume clears the mark (D6, D7): success, `fail_resume`, a failure
  before the take; a not-stopped session that fails is stopped.
- A running server outside a container must stay inert: no stop, no resume thread.
- The dying agents' session-end hooks after the container's stop queue nothing (they find
  no agent).

---

### Task 1: Schema 29 and the state of the container's stop

**Files:**
- Modify: `src/lado/state.py` (`SESSIONS_RESUME_AT_START`, `SCHEMA_VERSION`, `MIGRATIONS`,
  `Session.resume_at_start`, `_session`, `stop_for_container`, `resume_session`,
  `give_up_resume`)
- Modify: `tests/agent_helpers.py` (`schema_before`)
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `state.stop_for_container() -> list[str]`; `state.give_up_resume(name: str)
  -> None`; `state.resumable() -> list[Session]` (marked stopped ones and not-stopped
  ones, creation order; the caller filters the latter by tmux); `Session.resume_at_start:
  bool`.

- [ ] **Step 1: Write the failing tests** (layer 1, `tests/test_state.py`):

```python
def test_stop_for_container_marks_every_running_session_in_one_go(home):
    for name in ("a", "b", "c"):
        state.add_session(state.Session(name, "/r", None, "claude"))
    state.stop_session("c")  # the human's
    assert state.stop_for_container() == ["a", "b"]
    by = {s.name: s for s in state.list_sessions()}
    assert by["a"].stopped_at and by["a"].resume_at_start
    assert by["b"].resume_at_start and not by["c"].resume_at_start
    [stop] = [e for e in state.events("a") if e.kind == state.SESSION_STOP]
    assert stop.detail.endswith("; the container stopped")


def test_any_resume_clears_the_mark(home): ...          # resume_session -> False after
def test_give_up_clears_the_mark_and_stops_a_running_one(home): ...
#   a marked stopped session: mark 0, still stopped, no new event
#   a not-stopped one: session_gone + session_stop written, stopped, mark 0
def test_resumable_lists_marked_and_not_stopped_only(home): ...
def test_migration_28_to_29_adds_the_column(home): ...   # previous_schema(), migrate()
```

- [ ] **Step 2: Run them, expect failures.** `uv run pytest tests/test_state.py -n auto`.
- [ ] **Step 3: Implement.**

```python
SESSIONS_RESUME_AT_START = (
    "ALTER TABLE sessions ADD COLUMN resume_at_start INTEGER NOT NULL DEFAULT 0"
)
SCHEMA += SESSIONS_RESUME_AT_START + ";\n"
MIGRATIONS[28] = [SESSIONS_RESUME_AT_START]


def stop_for_container() -> list[str]:
    """Mark every session not stopped as stopped, as lado stop does, to be resumed at the
    container's start; one transaction for all (design D3). The names, creation order."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        names = [r[0] for r in db.execute(
            "SELECT name FROM sessions WHERE stopped_at IS NULL ORDER BY created_at, rowid")]
        for name in names:
            _stop_session(db, name, "; the container stopped")
            db.execute("UPDATE sessions SET resume_at_start = 1 WHERE name = ?", (name,))
        db.execute("COMMIT")
    return names
```

`resume_session`'s taking `UPDATE` sets `resume_at_start = 0` too. `give_up_resume`: one
`BEGIN IMMEDIATE`; `_session_gone(db, name)` and `_stop_session(db, name, "")` only when
`stopped_at IS NULL`; then `resume_at_start = 0`. `schema_before`: assert
`MIGRATIONS[28] == [state.SESSIONS_RESUME_AT_START]` and drop the column when undoing 29.

- [ ] **Step 4: Run** `uv run pytest tests/test_state.py tests/test_usage.py -n auto` and
  the migration tests (`tests/test_schema_migration*.py` or where `previous_schema` is
  used): green. `make lint`.
- [ ] **Step 5: Commit** `lado.db remembers which sessions the container's stop stopped
  (LAD-74)`.

### Task 2: runtime's stop for the container and resume at start

**Files:**
- Modify: `src/lado/runtime.py` (`stop_for_container`, `resume_at_start`,
  `start_session(..., reason=None)`)
- Test: `tests/test_runtime.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `runtime.stop_for_container() -> list[str]` (prints nothing; returns the
  names); `runtime.resume_at_start(report: Callable[[str], object], stopping:
  threading.Event | None = None) -> None` (calls `report` with each line of the spec).

- [ ] **Step 1: Failing tests** (layer 1, tmux replaced by the recorder as the other
  `stop_session` tests do):
  - `stop_for_container` kills each marked session's tmux session after the commit (the
    recorder sees `kill-session` only after `stopped_at` is set), closes viewers and
    removes `LADO_HOME/agents/<session>/`; a `TmuxError` on one still handles the next;
    no `lado.db` (`state.home_path()` empty) → returns `[]` and makes no folder.
  - `resume_at_start` resumes a marked stopped session and a not-stopped one whose tmux
    is gone (`start_session` monkeypatched to record its arguments: `resume=True`,
    `reason="at the container's start"`), skips a session stopped without the mark and a
    running one, reports the resumed line; a `start_session` that raises reports the
    failed line, calls `state.give_up_resume`, goes on with the next; a set `stopping`
    resumes nothing more.
  - `start_session(..., reason=...)` writes `at the container's start; same settings` as
    the `session_resume` detail (use the existing resume test's setup).
- [ ] **Step 2: Run, expect failures.** `uv run pytest tests/test_runtime.py -n auto`.
- [ ] **Step 3: Implement.** `stop_for_container`: guard on `(state.home_path() /
  "lado.db").exists()`, then `names = state.stop_for_container()`, then per name: `try:
  tmux.kill_session(name) except tmux.TmuxError` (a gone one is fine; another is one line
  on stderr), `terminal.close_viewers(name)`, `providers.base.remove_session_config_dirs(
  name)`. `resume_at_start`: `for sess in state.resumable()`: skip a not-stopped one whose
  `session_status` is not `TMUX_GONE`; stop when `stopping` is set; `try:
  start_session(sess.repo, sess.name, None, resume=True, reason=AT_START)`, `report(...)`;
  `except Exception as error: state.give_up_resume(sess.name); report(...)` (a
  `LadoError`'s text, else `Type: text`, and `telemetry.record("server:resume", error)` for
  a non-`LadoError`).
- [ ] **Step 4: Run** the tests: green; `make lint`.
- [ ] **Step 5: Commit** `A container's stop stops its sessions and its start resumes them
  (LAD-74)`.

### Task 3: The UI server calls them, only in a container

**Files:**
- Modify: `src/lado/server/app.py` (`Server.shutdown`, `app.state.stopping`)
- Modify: `src/lado/server/run.py` (`serve`: the resume thread)
- Test: `tests/test_server.py` (or a new `tests/test_server_container.py`)

- [ ] **Step 1: Failing tests** (layer 1, in process):
  - With `LADO_CONTAINER=1`, `Server.shutdown` calls `runtime.stop_for_container` before
    `hub.close` (both monkeypatched to append to one list), sets `app.state.stopping`, and
    prints the stop's line with the names; with no names, no line.
  - Without it, `Server.shutdown` calls neither.
  - `serve`'s thread: a helper `run.resume_thread(app, report)` started only in a
    container (monkeypatch `update.in_container` and `runtime.resume_at_start`).
- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement.**

```python
async def shutdown(self, sockets=None) -> None:
    app = self.config.app
    app.state.stopping.set()
    if update.in_container():
        names = await run_in_threadpool(runtime.stop_for_container)
        if names:
            listed = ", ".join(f'"{n}"' for n in names)
            print(f"lado: the container stops: stopped sessions {listed}; they resume at "
                  "its start", file=sys.stderr, flush=True)
    app.state.hub.close()
    await run_in_threadpool(app.state.clones.close)
    await super().shutdown(sockets)
```

`serve`: after `sock.listen` and the server's lines, when `update.in_container()`:
`threading.Thread(target=runtime.resume_at_start, args=(say, app.state.stopping),
daemon=True).start()`, `say` printing to stderr with `flush=True`.
- [ ] **Step 4: Run** `uv run pytest tests/test_server*.py -n auto`: green; `make lint`.
- [ ] **Step 5: Commit** `The UI server in a container stops and resumes its sessions
  (LAD-74)`.

### Task 4: Integration: a real server with LADO_CONTAINER=1

**Files:**
- Create: `tests/integration/test_container_sessions.py`

Real tmux, git, hooks, `lado mcp` and SQLite with the fake agent (layer 2): the server is
`lado server --port <free>` started as a process with `LADO_CONTAINER=1` in its
environment (the test's own `LADO_HOME` and tmux socket, as `test_server_process.py`
starts one), the sessions started with `runtime.start_session` / `lado start` of the fake
provider.

- [ ] **Step 1: Tests:**
  - SIGTERM to the server with a running session (supervisor and a worker of an open run):
    the server exits 0; its output has the stop's line; the session is stopped with the
    mark; `tmux has-session` fails; `LADO_HOME/agents/<session>` is gone; no message from
    `lado` to `human` or `supervisor` was queued after the stop (`state.list_messages`).
  - A new server with `LADO_CONTAINER=1`: the session runs again, the supervisor gets to
    idle (`agent_helpers` polling), its first message from `lado` is `session resumed: 1
    open runs` with the `spawn_worker` line, the mark is 0, the output has the resumed
    line; `runtime.stray_config_dirs()` is empty.
  - Crash path: the tmux session killed directly (`tmux kill-session`) and the server
    killed with SIGKILL; a new server resumes it.
  - A session stopped with `lado stop` before: still stopped after the restart, not named.
  - A failure: the marked session's repository folder removed before the restart: the
    failed line, stopped, mark 0; a third server start names it nowhere.
  - Without `LADO_CONTAINER`: SIGTERM leaves the session running (tmux there, not
    stopped), and a new server resumes nothing (AC-8).
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto
  tests/integration/test_container_sessions.py`: green (fix Tasks 1-3 when not).
- [ ] **Step 3: Commit** `Integration tests of a container server's stop and start
  (LAD-74)`.

### Task 5: Container tests and the headers

**Files:**
- Modify: `docker/compose.yaml`, `docker/Dockerfile` (headers)
- Modify: `tests/test_docker.py` (headers)
- Modify: `tests/container/container_helpers.py` (`fake_endpoint(container)`: start the
  fake model API again in a started container, split out of `claude_session`; `session_row`
  / a `lado.db` query helper through `c.python`)
- Create: `tests/container/test_sessions.py`
- Modify: `tests/container/test_two_lados.py`, `tests/container/conftest.py`
  (`old_home(running=True)`: the seeded session left not stopped)

- [ ] **Step 1: Headers first** (layer 1, `tests/test_docker.py`): each header says the
  sessions stop with the container and resume at its start, but those stopped by hand, and
  names the supervisor's model turn. Then the header lines in `docker/compose.yaml` (after
  the update paragraph) and `docker/Dockerfile`. `uv run pytest tests/test_docker.py -n0`.
- [ ] **Step 2: Container tests** (layer 7, `make docker && make test-container`):
  - `test_compose_down_and_up_resume_the_session` (AC-1, AC-2, AC-5): compose project, a
    Claude session (`claude_session`) plus a second one stopped by hand; `docker compose
    down`; the container's exit code 0 (`docker inspect` before `down` removes it: run
    `stop` first, check `State.ExitCode`, then `down`); logs have the stop's line naming
    only the first; `up -d`; `fake_endpoint` again; the resumed line, the first's
    supervisor idle, the second stopped; `lado doctor` has no `Agent config folders`
    warning.
  - `test_docker_kill_then_start_resumes` (AC-3).
  - `test_three_sessions_stop_within_the_default_grace` (AC-10): three sessions, `docker
    stop` without `-t`, exit code 0, all three marked.
  - `test_a_new_image_migrates_then_resumes` (AC-4): `old_home(running=True)` on a
    volume; the image starts; `docker logs` has the upgrade line before the resumed line
    (by index); `lado ls` shows `old` running. The seeded session's repo must exist in
    the container (`/home/lado/repo`, made with `git init` and a commit before the start
    through the volume, or by the fixture).
  - `test_two_lados.py`: `test_stopping_one_lado_leaves_the_others_sessions` (AC-9): a
    session in each; `docker compose down` in the first; the second's supervisor pid
    (`agent_pid`) the same and its status idle, its `lado.db` has no stopped session.
- [ ] **Step 3: Run** `make docker && make test-container`: green.
- [ ] **Step 4: Commit** `Container tests: sessions stop and resume with the container
  (LAD-74)`.

### Task 6: AGENTS.md, CHANGELOG.md, regression

- [ ] **Step 1:** AGENTS.md: Layout `state.py` (schema 29: `sessions.resume_at_start`,
  `stop_for_container`, `give_up_resume`), `runtime.py` (`stop_for_container`,
  `resume_at_start`), `server/` (`Server.shutdown` in a container, `serve`'s resume
  thread), `docker/` (the sessions follow the container); Commands' container tests
  paragraph (the new tests). CHANGELOG.md under the version open in main: one item (what
  the user sees, the model turn per resumed session, outside Docker unchanged).
- [ ] **Step 2: Regression:** `make lint`, `make test`, `uv run pytest -m integration
  -n auto tests/integration/test_container_sessions.py tests/integration/test_server_process.py
  tests/integration/test_session_start.py`, `openspec validate --specs --strict`,
  `make docker && make test-container`; CI on the pull request (`ci-ok`, including the
  `container (amd64)` and `container (arm64)` jobs).
- [ ] **Step 3:** The pull request's description carries the manual check of the design
  doc verbatim (branch, folder, commands, expected lines, `env | grep LADO` and `unset`).
- [ ] **Step 4: Commit** `AGENTS.md and the changelog for sessions that follow the
  container (LAD-74)`.

## Tests per requirement

| Requirement | Layer | Tests |
|---|---|---|
| The container's stop stops its sessions for a resume | 1, 2, 7 | `test_state.py` (one transaction, mark, detail); `test_runtime.py` (kill after mark, viewers, folders, no lado.db); `test_server*.py` (before `Hub.close`, line); integration SIGTERM test (no messages, folders gone); container: compose down, three sessions within ten seconds |
| The container's start resumes its sessions after the migration | 1, 2, 7 | `test_runtime.py` (which, order, failure, `stopping`); `test_state.py` (clear on resume, give up); integration restart, crash, hand-stopped, failure, open run's message; container: compose up, `docker kill`, new image after migration |
| Outside a container the server's stop and start leave the sessions | 1, 2 | `test_server*.py` (no calls without `LADO_CONTAINER`); integration SIGTERM without it |
| Stopping one LADO container leaves another's sessions | 7 | `test_two_lados.py::test_stopping_one_lado_leaves_the_others_sessions` |
| The headers say that sessions follow the container | 1 | `test_docker.py` |

End to end: the container tests (layer 7) on amd64 and arm64 in CI, and the human's manual
check on a Mac. Regression: `make test`, the changed integration files, `make
test-container`, CI's `ci-ok`.
