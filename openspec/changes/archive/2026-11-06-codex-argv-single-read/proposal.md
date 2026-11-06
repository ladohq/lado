Task: LAD-214

## Why

Symptom: `tests/container/test_codex_sandbox.py::test_a_codex_supervisor_runs_without_the_sandbox_that_cannot_start`
fails at random with `ValueError: '-a' is not in list` (line 53) and turns the required
`ci-ok` red. Seen once: run 42135583465, attempt 1, container (amd64), on PR #224, which
changed only `web/`, UI tests and documents; the rerun of the job passed.

Cause, reproduced 2026-11-06: the test reads `/proc/<pid>/cmdline` twice, and the second read
can fall inside an `execve`.

- A window does not start Codex directly. The pane's process is first LADO's Python
  (`lado.agent_env`), which execs `codex`, a `#!/usr/bin/env node` script: Python, then `env`,
  then `node`, one pid. All three stages hold the whole argv, so `codex_pid` sees
  `--no-daemon` already in the Python stage, not "once it runs `codex`" as its docstring says.
- While a process execs, the kernel has given it a new address space and not yet set its
  argument area: `/proc/<pid>/cmdline` then reads empty, and `cat` exits 0. Measured with a
  reader in a tight loop on the same chain: 297 of 300 launches gave empty reads between the
  stages.
- So when `codex_pid` returns in an early stage, the test's own second read may land on an
  exec, gets `""`, and `"".split("\0").index("-a")` raises. Replaying the test's two reads
  against a child that stays alive, 30 ms apart at most: 17 of 800 launches failed, each with
  exit 0, empty output and the child alive; every first read matched in the Python stage.

The other readings do not hold. No stage lacks `-a`, so "the wrong process" is out. Codex does
not die early: run by a real `lado start` with a fake key, the pane stayed on one pid for the
40 s watched, though a process that had exited would also read empty. The failed run's own
argv cannot be seen: the test printed nothing, and the evidence of the job's artifact
`container-amd64` does not hold it. That evidence does fit the cause: `lado ls`, taken right
after the failure, shows the agent `starting` for `0s`, so the reads came in the window's first
second, while it was still going through its stages. So this cause is shown by reproduction,
not read from that run.

The product is not at fault: nothing in `src/` reads a cmdline. Only the test is.

Options weighed:

- A (taken): read once. The poll returns the argv it matched, and only a read past
  `lado.agent_env` matches. No second read, so no second chance of an exec; the poll already
  skips an empty read. Long-term cost: none; a few lines fewer.
- B: keep the pid and retry the second read until it is not empty. Same result with a second
  loop, and the pattern that caused this stays for the next reader of that pid.
- C: leave the test and let the Review trap's rerun absorb it. Costs a rerun of the job at
  each failure, and a required check that stays red for no fault of the pull request.

## What Changes

- `tests/container/test_codex_sandbox.py`: `codex_pid` becomes `codex_args`, which returns the
  argv of the one read that matched, and matches only once the window has left
  `lado.agent_env`. The test asserts on that list.
- The two asserts on `-a` and `--sandbox` look for the pair in the argv, so a failure prints
  the argv instead of a `ValueError` that hides it.

## Scope

In: that test file only. The requirements of `codex-sandbox` stay as they are, so the change
has no delta.

## Out of scope

- Any change in `src/`: the product does not read a cmdline.
- A unit test of the poll: it would test a test's helper with a fake container, and the
  container cell runs the real one on every pull request.
- A retry inside pytest: the project's rule forbids it, and it would hide the cause.

## Impact

- Tests only. No CHANGELOG line (no user sees it), no version bump, no schema change.
- Neutral core, one source of truth, no silent drops: untouched; `src/` does not change.
