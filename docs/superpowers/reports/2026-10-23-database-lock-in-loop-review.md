# LAD-129 database-lock-in-loop: review report

Pull request #145 `hotfix/lad-129-database-lock` → `main`. Scale: hotfix, reviewed by
precision, widened in round 1 with the lenses tests, silent failures, comments and spec
(the diff changes error handling in a class shared by the session loop and the UI
server's feed). Head reviewed last: `62da9f6` (= the remote head). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not
change, so no live tests were needed.

## Rounds

- **Round 1, local** (`origin/main...cedc791`): found F1 and F2.
- **Round 2, local** (`cedc791..b00dd46`, only the merge of `main`) and **round 1,
  external** (Claude Code GitHub Action; request issuecomment-6357456437, "Claude
  finished" at 04:35:07Z, newer than the request; answer issuecomment-6357473787): found
  E1–E4. It is of the same model family, so its "nothing more" weighs less.
- **Round 3, local** (`b00dd46..62da9f6`): a return from merge, where the archive's
  `openspec validate --specs --strict` failed because the modified requirement of
  `error-journal` grew past openspec's 500 characters. Its text is now word for word the
  living spec; the lock rule is linked by a new scenario. Found R1 (refuted). No
  external round: the hotfix's cap (1) was used and only spec text changed.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks) | the pull request conflicted with `main` in CHANGELOG.md, so CI did not run on `cedc791` | confirmed | blocker | fixed in `b00dd46` (both lines kept under 0.43.0 Fixed); CI green |
| F2 | 1 | local (feed) | `feed.Hub._errors` is not reset when `unsubscribe` cancels the `_run` task, so a stale `locked_since` can journal a lock at the first pass of a new task | confirmed (by code) | minor | declined: rare, at most one extra line in errors.jsonl, as before the change; left to the human |
| E1 | 2 | external | a lock alternating with another error restarts the 60 s count | refuted: the spec counts one error failing the passes without a break; another error ends the run and is journaled at once | — | dropped |
| E2 | 2 | external | no test of the real `LOCK_GRACE` = 60 s boundary with a faked clock | confirmed | minor | declined: both sides of the rule are tested (grace not reached; grace 0 gives one line), and a mutation probe fails them |
| E3 | 2 | external | `main` moved ahead after `b00dd46` (#144, schema 34) | refuted: `git merge-tree` clean, the pull request CLEAN | — | dropped |
| E4 | 2 | external | the CHANGELOG heading may not match `main` | refuted: `main` still has `## 0.43.0 (unreleased)` | — | dropped |
| R1 | 3 | local (spec) | the modified requirement still says every pass's exception SHALL be journaled; the lock exception is only in a scenario | refuted: the existing "repeated error once" exception is made the same way, and the lock rule is its own added requirement | — | dropped |

Metrics: 3 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted 1
(R1); external confirmed 1 (E2), refuted 3 (E1, E3, E4). Findings in code changed by the
developer's cleanup: 0.

## Checks

- `make lint`: clean; `make test`: 3876 passed, 2 skipped (on `cedc791`; later heads
  changed no code or tests of this change).
- `openspec validate database-lock-in-loop --strict`: valid; `openspec validate --specs
  --strict`: 45 of 45 after the archive.
- A mutation probe: the new tests can fail.
- CI on `62da9f6`: 23 of 23, `ci-ok` green, integration, UI, smoke and container included.

## Not checked

- The integration, UI and smoke tests were not run locally; CI ran them.
- A real lock of lado.db under a saturated disk is not reproduced by tests; the effect of
  `synchronous = NORMAL` rests on the design's measurement (1027 ms → 0.1 ms per commit).
- With `synchronous = NORMAL` a power cut or an OS crash may lose the last commits of
  lado.db (the human's decision, question #994).
- The other places that can meet a lock (the UI server's requests, hooks, `lado mcp`, the
  CLI) are out of scope and still journal it at once.

Found on the way: none.
