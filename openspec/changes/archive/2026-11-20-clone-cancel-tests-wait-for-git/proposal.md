Task: LAD-307

## Why

Symptom: `tests/integration/test_clone_start.py::test_ctrl_c_during_the_clone_leaves_nothing`
failed in CI of PR #348 (run 44700537185, commit ffa1acfb, job 136167544008, `integration
(3.10, 3)`, `-n0 --shard 3/3`) at line 90 with `assert (True and False)`: `gone(3440)` (the fake
git) was true, `gone(3441)` (its child `sleep 60`) false. The rerun of the job (job 136170820668)
was green. The pull request did not touch the clone or the test.

Cause: a race in the test, not a defect of LADO. On a cancel `clone._stop` sends SIGTERM to git's
whole process group, waits for git itself (the group's leader, at most `STOP_WAIT`), then always
sends SIGKILL to the group and returns; `lado start` removes the temporary folder and exits.
`kill` returns before its target has died: a process killed with SIGKILL runs no more of its own
code, but it is gone only once the kernel has scheduled its exit. The test looks at the child at
once after `lado` exits, with no wait, so on a loaded runner the child sometimes still shows,
milliseconds before it is gone. Of the task's two guesses it is the first. The second (LADO does
not wait for git's children) is true as a fact, but harmless: every process of the group has had
SIGKILL, so none of them can write into the folder or outlive the kill, and the user sees
nothing.

Checked by the analyst: 60 cancels in a row of `clone.clone` with the fake git under a 16-core
busy loop, each child looked at at once: no late child. The window is narrow; the CI log is the
evidence of the race.

The same instant check `gone(call["pid"]) and gone(call["child"])` stands in 12 places: 2 in
`tests/integration/test_clone_start.py`, 1 in `tests/integration/test_project_repositories.py`,
5 in `tests/test_clone.py`, 4 in `tests/test_server_clones.py`. All of them race the same way.

Options weighed:

- A (taken): the tests wait. A helper `ended(pid, timeout=10)` in `tests/agent_helpers.py` polls
  `gone(pid)` until it is true or the timeout passes; the 12 checks use it. A process that never
  ends (a real regression: git's group not killed) still fails, after 10 seconds. Long-term
  cost: a few lines, no product code.
- B: `_stop` waits until git's process group is empty. A group whose orphaned members are
  zombies still answers `killpg(pgid, 0)`, so telling the dead from the living needs `/proc` on
  Linux and `ps` on macOS: new platform code in the product and a slower cancel, for nothing a
  user can see. Rejected.
- C: both. B's cost without its use. Rejected.

## What Changes

- `tests/agent_helpers.py`: `ended(pid, timeout=10)`, which waits for `gone(pid)`.
- The 12 checks `gone(call["pid"]) and gone(call["child"])` become
  `ended(call["pid"]) and ended(call["child"])`.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md line,
  and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/agent_helpers.py`, `tests/integration/test_clone_start.py`,
  `tests/integration/test_project_repositories.py`, `tests/test_clone.py`,
  `tests/test_server_clones.py`. Nothing in `src/` or `web/`.

## Out of scope

- `src/lado/clone.py` (option B): the cancel already kills the whole group; waiting for its
  zombies would add platform code for nothing a user sees.
- `agent_helpers.gone` itself stays instant: `tests/ui/test_launch.py` calls it inside its own
  wait, and `tests/integration/test_leftover_processes.py` checks a process already reaped.
- `tests/integration/test_server_process.py` has its own waiting `gone(pid, timeout)`; merging it
  with the new helper is not this task.
- A rerun plugin or a retry inside pytest: the settings forbid them.

## Acceptance criteria

- AC-1: `tests/agent_helpers.py` has `ended(pid, timeout=10)`, true as soon as `gone(pid)` is,
  false once the timeout passes with the process still running.
- AC-2: No test keeps the instant check `gone(call["pid"]) and gone(call["child"])`
  (`grep -rn 'gone(call\["pid"\])' tests` finds nothing); the 12 places use `ended`.
- AC-3: A unit test of `ended`: a process that ends a moment after the call gives true; one that
  runs on gives false after a short timeout.
- AC-4: `tests/integration/test_clone_start.py` passes 30 times in a row under load
  (`-m integration -n auto`, the file's node ids repeated, or a shell loop that stops on the
  first failure, while another `-n auto` run loads the machine), each run's exit status read,
  not piped; `make lint`, `make test` and
  `uv run pytest -m integration -n auto tests/integration/test_clone_start.py tests/integration/test_project_repositories.py`
  pass. The build report gives the counts.

## Impact

- Tests only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale tweak: a test-only change of known shape, as the earlier flake fixes
  `codex-model-smoke-waits-for-list` and `session-screens-test-waits-for-the-feed`; review by
  precision.
- Option A over B and C: see Why.
- All 12 checks, not the one that failed: they are the same race, and fixing one leaves the next
  flake for a later task.
- A new helper `ended` beside `gone`, not a timeout on `gone`: `gone`'s other callers want an
  instant answer (Out of scope).
- Timeout 10 seconds: far above any exit after SIGKILL, and below the tests' own 30-second waits.
- Test layer: unit for `ended` (AC-3); the fixed checks stay in their own layers.
- Branch `fix/lad-307-clone-cancel-tests-wait` to `main`; this pull request is the task's last.
