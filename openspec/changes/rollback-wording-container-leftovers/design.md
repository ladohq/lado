## Context

Three findings, each in tooling: the release's documents (finding B), the container tests'
cleanup (finding E) and one integration test's race. The proposal names the causes and the
options; this file holds the technical choices.

## Decisions

### D1. The rollback's wording, not its script

docs/release.md 4.4, the paragraph after the `rollback` command: "Read `lado update
<final>`'s warning before you answer `y`: it names what going back loses" becomes two
facts: the plan of `rollback`, printed before `Roll back? [y/N]`, names the sessions not
started again (`- not started again, not in the copy: <names>`); `lado update <final>`'s
warning, printed before its own question, names what the database loses (its `Everything
LADO recorded since then is lost: …` line). One sentence says why the update's own line
`Sessions not in that copy are not started again:` does not show there: `rollback` has
stopped every session before the update runs. The user's own way back (the second half of
4.4) keeps that line: there `lado update` stops the sessions itself and names them.

4.7, "What goes in it", the item "what going back to the last final loses": a release's
item for the RC's `rollback` quotes the plan's line for the sessions, the update's warning
for the data. That is the "template" the finding asks for: 4.7 is the one place the next
checklists are written from.

### D2. SIGTERM and SIGHUP raise KeyboardInterrupt in the container run

`tests/container/conftest.py` sets, at the session's start, a handler for SIGTERM and
SIGHUP that raises `KeyboardInterrupt` in the main thread, so pytest ends the run as on
Ctrl-C: `pytest_sessionfinish` tears down every fixture still set up, and the finalizers
remove the test's objects. Only the container tests: their objects outlive the process in
Docker, while every other layer's leftovers are processes that `tests/leftovers.py` reaps
by `LADO_TEST_PID`. A `docker` call running at that moment gets nothing from the handler
(it is a child), and `subprocess.run` waits for it: the finalizer then removes what it
made. The handler is set in `pytest_sessionstart` of the container conftest and restored
in `pytest_sessionfinish`.

### D3. The run's lock: one file per prefix in a user's folder outside every checkout

`container_helpers` gets the folder `/tmp/lado-container-runs-<uid>/` (the same reach as
`scripts/check_lock.py`'s `/tmp/lado-check-<uid>.lock`, so every worktree and every
`LADO_HOME` of the user sees it; `LADO_CONTAINER_RUNS` overrides it for the tests). The run
opens `<PREFIX>lock` there and holds `fcntl.flock(LOCK_EX)` on it while it lives, taken
before its first `docker` object, in the session fixture `image`. The kernel frees the
lock when the process ends in any way, SIGKILL too, so a free lock is a dead run, and pid
reuse cannot make a dead run look alive. Standard library only; the container tests run on
Linux and macOS, both have `flock`. `$TMPDIR` is not used: LADO gives each agent its own,
and two agents' runs would not see each other's locks.

### D4. The start's reaping and warning

In the fixture `image`, after the lock is taken: list Docker's `lado-test-*` containers
(`ps -a`), volumes, networks and image tags (`image ls --filter reference=lado-test-*`),
group them by prefix (`lado-test-<6 hex>-`), and for each prefix other than the run's own:

- its lock file exists and `flock(LOCK_EX | LOCK_NB)` succeeds: a dead run. Remove its
  containers (`rm -f`), then volumes and networks (`rm`/`rm -f`), then tags (`image rm`, a
  tag only), then the lock file. Each removal is `check=False`, and one that fails is named
  in the warning below, so nothing is dropped silently.
- its lock file is held: a live run; nothing is touched.
- no lock file: unknown. Named in one `UserWarning` (pytest's warnings summary), each
  object by kind and name, with one command that removes them all (`docker rm -f …;
  docker volume rm …; docker network rm …; docker image rm …`), never removed.

The order containers first follows Docker: a volume or network in use cannot go.

### D5. The end's check covers networks and tags

The `image` fixture's teardown lists containers, volumes, networks and image tags of the
run's own prefix and asserts all four empty, naming what is left; then it frees and
deletes its lock file. `folder`'s teardown already removes its tags; compose's `down -v`
removes its network.

### D6. The container test of the cleanup

`tests/container/test_cleanup.py` runs a child pytest on a target test in
`tests/container/cleanup_target.py`: a name pytest does not collect by itself, so a normal
run neither runs nor skips it (the container cell makes a skip red), while a path given on
the command line is collected. The target starts one container with `start` and one
compose project with `compose` (`up -d`), prints its prefix, then waits. Cases:

1. SIGTERM to the child once the target's container runs: the child exits interrupted,
   and Docker holds nothing of the child's prefix (read from the child's output, where the
   target prints it).
2. SIGKILL to the child likewise: its objects and its lock file are left; then a call of
   the reaping function (D4) from the test itself removes them all, and the lock file.
3. A prefix the test makes with no lock file (a volume `lado-test-<hex>-x`): the reaping
   warns with its name and the command, and the volume stays; the test removes it.

The child uses the parent's `LADO_CONTAINER_RUNS` folder, a temporary one, so the
reaping in case 2 meets only the test's own objects and the parent's held lock. This is
the lowest layer that can catch it: the behaviour is Docker's objects across processes.
CI runs it on amd64 and arm64; LADO's container, where the developer works, has no Docker,
so it is first run in CI.

### D7. The last message to an agent

The flaky test takes the step as the newest message to the worker from LADO whose summary
is `flow <run>: step build` (`next(m for m in reversed(...) if ...)`). The same for the
other places of the pattern, by what each means: `read_step` (`test_flow_runs.py:137`)
the newest message from LADO whose summary starts with `flow `; lines 322 and 354 as the
flaky one; `tests/ui/test_gates.py:660` the newest to the supervisor from LADO whose summary
names the step. `test_session_start.py:66` (already by sender and the resume's summary),
`test_local_model_limits.py:38` and `test_unread_reminder.py:52` (each reads the message it
has just written, before any turn of the agent can follow) are read again and kept unless
a later message can come first; the build report says which and why.

## Risks / Trade-offs

- A run killed between taking the lock and creating its first object leaves only a lock
  file: the next run deletes it (a free lock, nothing to remove).
- Objects of a run on the Mac seen from a LADO container on the same Docker Desktop (or
  the other way) have no lock file there: they are named, not removed (the human's choice).
- The handler of D2 does not help against SIGKILL: D4 covers that at the next run.
