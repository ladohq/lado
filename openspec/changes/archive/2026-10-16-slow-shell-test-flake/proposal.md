Task: LAD-81

## Why

Symptom: `tests/test_agent_env.py::test_a_slow_shell_times_out` fails now and then under
`-n auto` (pytest-xdist) on a loaded machine and passes alone with `-n0`. The developer
and the reviewer of LAD-76's run each saw it once (2026-10-15: 693 passed, 1 failed);
CI on 42ea08c was green. The failure's text was not kept.

Cause: a race between the test's 0.5 s deadline and the fake shell's first line, not a
defect of LADO. The test sets `agent_env.TIMEOUT = 0.5` and makes `$SHELL` a script whose
rc lines are `echo stuck >&2; sleep 30 & wait`; it expects an `AgentEnvError` that says
`did not finish in 0.5 s` and carries the shell's stderr, `stuck`. `agent_env.from_shell`
counts the deadline from the moment `Popen` returns. On a machine under load the script
(`/bin/sh` reading the rc lines) may not reach its `echo` within 0.5 s; the deadline then
passes, the shell's process group is killed, and the error has the right text but an
empty stderr tail, so `assert "stuck" in str(error.value)` fails. Shown by hand: a shell
that sleeps 0.3 s before `echo stuck`, with `TIMEOUT = 0.2`, gives `your shell did not
finish in 0.2 s: <command>` and no `stuck`. The error's text and the stderr tail are
right in every case: LADO reports what the shell printed by the deadline.

## What Changes

- `tests/test_agent_env.py`, `test_a_slow_shell_times_out`: the fake shell's rc lines
  touch a marker file right after `echo stuck >&2`, and the test makes
  `agent_env._read_until` (through `monkeypatch`) wait for that marker before it calls the
  original with the same arguments. The deadline stays 0.5 s and is counted as before;
  only its check waits until the shell has printed its line. When the line came later
  than 0.5 s, the original finds the deadline passed at once and the timeout path runs as
  in a real slow shell; when it came earlier, the rest of the 0.5 s runs as before. Either
  way `stuck` is in the error, so the assertions hold whatever the load. The wait for the
  marker is bounded (30 s, then the test fails naming the marker), so a shell that never
  runs fails the test rather than hangs it. A comment says why.

## Scope

The one test. Nothing in `src/`.

## Out of scope

- A longer `TIMEOUT` in the test (e.g. 5 s): it makes the race rarer, not gone, and adds
  seconds to every unit run; rejected.
- Dropping the `stuck` assertion, or moving it to a test of `_tail` alone: the test's
  point is that a timeout error shows what the shell printed, end to end through a real
  process; rejected.
- Counting the deadline in `agent_env.from_shell` from the shell's first output rather
  than from its start: a real shell that hangs before printing anything must still time
  out on time; the product's rule is right.
- `test_a_background_program_of_the_rc_files_does_not_hold_it_up` (a 2 s `TIMEOUT` the
  shell must finish within): the same kind of time bound under load, but it was not seen
  failing; no change without evidence. The BACKLOG.md P1 entry "`make check` fails on
  timeouts when the machine is under heavy load" holds such flakes.
- A rerun plugin: it hides the race rather than closes it.

## Acceptance criteria

- AC-1: `test_a_slow_shell_times_out` keeps its assertions (`did not finish in 0.5 s`,
  `stuck`) and its 0.5 s `TIMEOUT`; the rc lines write a marker after `echo stuck >&2`,
  and the test's `_read_until` wrapper waits for it (at most 30 s) before calling the
  original with the same arguments.
- AC-2: The race is shown by hand once, before the fix: with the old test and a delay put
  before `echo stuck` in its rc (e.g. `sleep 1;`), it fails on `assert "stuck" in ...`;
  with the fix and the same delay, it passes (the build report quotes both; the probe is
  not committed).
- AC-3: With the fix, the test passes 20 times in a row run alone
  (`uv run pytest -n0 tests/test_agent_env.py -k slow_shell`), and `make test` passes.
- AC-4: `make lint` passes; CI is green.

## Impact

- `tests/test_agent_env.py` only.
- No API, schema, MCP, CLI or UI change; no CHANGELOG.md line (nothing users see) and no
  version bump.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a shown cause; review by precision.
- Root cause is the test's 0.5 s deadline racing the fake shell's first line under load;
  fixed in the test, not in `agent_env` (see Out of scope).
- The seam is `agent_env._read_until`, wrapped and still called: the real shell process,
  the real deadline, the kill of the process group and the error's text all run as
  before; only the moment the deadline is checked waits for the shell's line. A marker
  file the shell writes is the exact sign that `stuck` is in the stderr file (`echo` ends
  before the next command starts).
- Test layer: unit (`make test`), the test itself; no new test.
- No delta spec: no behaviour rule changes; archived with `--skip-specs`
  (`.openspec.yaml` has `skip_specs: true`).
- No version bump and no CHANGELOG.md line: tests only.
