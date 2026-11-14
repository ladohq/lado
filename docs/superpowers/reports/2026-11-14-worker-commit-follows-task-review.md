# LAD-173 worker-commit-follows-task: review report

Pull request #308 `fix/lad-173-worker-commit-follows-task` → `main`. Scale: tweak, depth
precision. Head reviewed: `24dba22d`. A worker told by its task "Do not commit" committed
anyway, because LADO's own instructions for every worker said "Commit your work on that
branch." with no exception. The rule now names the task as its exception, in one constant
(`COMMIT_RULE`) shared by the worker's and the flow run worker's instructions.

## Rounds

1. Local, precision, over `origin/main...d006aa88`: the diff, the spec and the architecture
   against AGENTS.md. Found F1.
2. External 1, Claude Code GitHub Action
   (https://github.com/ladohq/lado/pull/308#issuecomment-6883516468): nothing blocking; E1
   refuted. It did not read the openspec files (checked locally).
3. Local, precision, over the delta `d006aa88..24dba22d`, after the human declined the merge
   over F1: F1 resolved, nothing new, no change under `src/`.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the live test looked at the branches right after both reports; a worker that commits after its `send_message` in the same turn would pass w1's check falsely and fail w2's | fixed in `aa5c46e0` (declined in round 1, then fixed when the human declined the merge): the test waits until both workers are idle before it looks |
| E1 | — | external: `rev-list --count … != "0"` reads better on a stripped string | refuted: `runtime.git` already strips its output |

## Metrics

Rounds: 2 local, 1 external, 0 stand-ins. Findings: local 1 confirmed (minor), 0 refuted;
external 0 confirmed, 1 refuted; findings in code changed by the developer's cleanup: 0.

## Checks

- Round 1, on `d006aa88`: `make test` 6154 passed, 7 skipped; `openspec validate` of the
  change: valid; `openspec validate --specs`: 84 passed; trial archive: 85 passed.
- Round 3, on `24dba22d`: `make lint` green; the live test collects; CI of PR #308: every job
  pass, `ci-ok` pass, the smoke on Linux and macOS for every provider among them;
  mergeStateStatus `CLEAN`.

## Residual risk

- The behaviour (AC-1, AC-2) is checked only by the live test, which was written, not run
  (paid). The change touches `runtime.py` and `tests/live/`: the human asked to run `live.yml`
  on main by hand once after the merge.
- The external reviewer is a model of the same family.

Found on the way: a read-only worker gets `COMMIT_RULE` and then READ_ONLY_INSTRUCTIONS forbids
commits; recorded in BACKLOG.md (P3) in `24dba22d`.
