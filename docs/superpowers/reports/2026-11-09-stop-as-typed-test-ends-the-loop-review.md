# LAD-236 stop-as-typed-test-ends-the-loop: review report

Pull request #265 `hotfix/lad-236-stop-test-loop-race` → `main`. Scale: hotfix, depth precision.
Head reviewed: `b9a045e1`. The two stop-as-typed integration tests end the session loop before
they write, so the loop process can no longer hand the human's message over past the test's
patched typing (`DID NOT RAISE LadoError`). Tests only: `tests/agent_helpers.py`,
`tests/integration/test_human_messages.py`. No delta.

## Rounds

1. Local, precision, `958dede7..b9a045e1`: the whole diff against the proposal and tasks, the
   architecture against AGENTS.md. Found F1.
2. External 1, Claude Code GitHub Action: no blockers, F2 and F3. It read both code files,
   `conftest.py`, `loop.py` and the relevant parts of `runtime.py` and `hooks.py`; not the three
   openspec files.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | `end_loop` reads `loop.log` once and fails the test when the loop has not yet written `loop started` | declined: the line was there on all 14 probed calls, under `-n auto` and CPU load; a miss fails loudly |
| F2 | minor | external: `os.kill` raises `ProcessLookupError` when the loop is already gone | declined: unreachable in a running session, and loud |
| F3 | minor | external: the comment could name the hook process, which is not ended | declined: see Not checked |

## Found on the way

None.

## Checks

On `b9a045e1`:
- The probe of the task (the test process's `runtime._sweep_sent` slowed by 0.6 s): with the fix
  2 passed, 10/10 repeats; with `end_loop` switched off 2 failed, `DID NOT RAISE LadoError`.
- `tests/integration/test_human_messages.py` under `-m integration -n auto`: 9 runs, 10 passed
  each; a failure in mid-test after `end_loop` leaves no loop, process or lock behind.
- The developer: each test 20/20 alone (`-n0`), the file 3× under `-n auto`, `make test` 6070
  passed / 7 skipped.
- `make lint` green; `openspec validate stop-as-typed-test-ends-the-loop --strict` valid.
- CI: 27/27 green, all integration shards, smoke and container included.

## Not checked

- The hand-over in the hook process (`hooks.py:283`) is not covered: a late status event of the
  fake agent after idle would take the message the way the loop did. None was found.
- No 50× run; live tests not run (`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py`, `tests/live/` unchanged).
