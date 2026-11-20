## 1. The rollback's wording (finding B)

- [x] 1.1 docs/release.md 4.4: the paragraph after `python3 scripts/rc_check.py rollback`
  says the plan names the sessions not started again (`- not started again, not in the
  copy: <names>`) before `Roll back? [y/N]`, and `lado update <final>`'s warning names what
  the database loses; one sentence why the update's `Sessions not in that copy are not
  started again:` does not show there (D1). The user's own way back keeps that line. Check:
  read it against `scripts/rc_check.py` `print_plan` and `rollback`, and `self_update.py`
  `print_plan`.
- [x] 1.2 docs/release.md 4.7, "what going back to the last final loses": the RC's
  `rollback` item quotes the plan's line for the sessions and the update's warning for the
  data (D1). Check: read it.
- [x] 1.3 The plan's line `- not started again, not in the copy: <names>` is covered by
  `tests/test_rc_check.py` (line 840 today); add the scenario "A session started on the RC"
  of release-candidates there if that test does not already check the session started
  again beside it. Check: `uv run pytest -n0 tests/test_rc_check.py`.

## 2. The container tests' cleanup (finding E)

- [x] 2.1 The run's lock (D3): `LADO_CONTAINER_RUNS` or `/tmp/lado-container-runs-<uid>/`,
  `<PREFIX>lock` held with `flock` from the start of the fixture `image` to its end.
  In a module of `tests/container/` (e.g. `container_runs.py`) beside `container_helpers`.
- [x] 2.2 The reaping and the warning (D4): objects grouped by prefix; a free lock's are
  removed with its lock file, a held lock's kept, no lock file's named in one `UserWarning`
  with one removing command; a failed removal named in it too.
- [x] 2.3 SIGTERM and SIGHUP as Ctrl-C in the container run (D2), set at its session start
  and restored at its end. Set in the session fixture `image`, not `pytest_sessionstart`:
  pytest calls that hook only in the conftests it loads before collection, which a run
  from the root does not include for `tests/container/conftest.py`.
- [x] 2.4 The end's check (D5): containers, volumes, networks and image tags of the run's
  prefix, all empty or the run fails naming them; then the lock freed and its file deleted.
  When something is left, the lock file stays, so the next run reaps it.
- [x] 2.5 Unit tests of the grouping and the choice per prefix (2.2), `docker` replaced by a
  recorder, in `tests/test_container_runs.py` or beside the module's existing unit tests:
  a free lock, a held lock (a lock taken by a child process), no lock file, a failed
  removal. Check: `uv run pytest -n0 <that file>`.
- [x] 2.6 The container test of the cleanup (D6): `tests/container/cleanup_target.py` and
  `tests/container/test_cleanup.py`, its three cases (SIGTERM, SIGKILL then the reaping, a
  prefix without a lock file). Check: written here, run in CI's container cells (no Docker
  in LADO's container); the build report says so.
- [x] 2.7 docs/testing.md, Container tests: SIGTERM and SIGHUP end the run through the
  finalizers, the run's lock, the start's reaping of dead runs, the warning with the
  command, the end's check of the four kinds. Check: read it against the code.

## 3. The last message to an agent

- [x] 3.1 `tests/integration/test_flow_runs.py:304` (the flaky test), `:322`, `:354` and
  `read_step` (`:137`): the step by its sender and summary (D7). Check: `uv run pytest -m
  integration -n0 tests/integration/test_flow_runs.py` 5 times in a row.
- [x] 3.2 `tests/ui/test_gates.py:660` likewise. Check: `uv run pytest -m ui -n0
  tests/ui/test_gates.py`.
- [x] 3.3 `tests/integration/test_session_start.py:66`, `test_local_model_limits.py:38`,
  `test_unread_reminder.py:52`: read again; change each where a later message to the agent
  can come first, else keep it; the build report names each with its reason. Check: each
  changed file with `-m integration -n0`. All three changed: in each a reminder of LADO's
  can follow the message before the test reads it.

## 4. Regression run

- [x] 4.1 `make lint`, `make test`, `uv run pytest -m integration -n auto` on the changed
  files of `tests/integration/`, `uv run pytest -m ui -n auto tests/ui/test_gates.py`,
  `openspec validate rollback-wording-container-leftovers --strict`, the trial archive in a
  copy, and CI's container cells green on the pull request (amd64 and arm64).
