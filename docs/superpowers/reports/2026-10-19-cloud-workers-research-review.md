# LAD-100 cloud-workers-research: review report

Pull request #104 `fix/lad-100-cloud-workers-research` → `main`. Scale: tweak,
documentation only, reviewed for precision (no business logic, user data or code
rewritten in earlier rounds, so no breadth pass). Head reviewed last: `f7051c3` (= the
remote head). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
and `tests/live/` did not change, so no live tests are needed before the merge.

## Rounds

- **Round 1, local** (precision over `origin/main..a6c60c2`): R1-R4 byte-identical to the
  change's `inputs/`; the `-s ours` merge leaves the tree unchanged; AC-1…AC-5 and AC-7
  checked; 13 relative links, none broken. F1, U1.
- **Round 1, external** (Claude Code GitHub Action; request at 06:10:38Z, "Claude
  finished" at 06:11:51Z): F-A (F4), F-B (F2), F-C (F3). The human decided F4 (option 1).
- **Round 2, local** (precision over the delta `a6c60c2..f7051c3`: `d8bcf74` the fixes of
  F2-F4, `f7051c3` the backlog entry of O1): other places of the same error class grepped
  ("Kilo allows", "Zen/Go", "R1 split"), the wording held against R4 §2.6, the pull
  request's description against the diff. Nothing new. No external round: the cap was
  used and the delta is round 1's triage.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | the pull request's description called the openspec change already archived | confirmed | minor | fixed: the description says "to be archived with `--skip-specs` at merge" |
| F2 | 1 | external (F-B) | section 5 of the plan used R1's split letters without mapping them to ours | confirmed | minor | fixed in `d8bcf74`: "(R1's split C, our D)" / "(R1's split D, our C)", the same in stage D's line |
| F3 | 1 | external (F-C) | step 0 of the plan cited wrong item numbers of R1 §6 | confirmed | minor | fixed in `d8bcf74`: MCP item 1, hooks item 2, latency item 3 |
| F4 | 1 | external (F-A) | the report's Kilo / OpenCode cells of scenarios (b) and (c) contradicted R4 and plan 4.6; the error came from the approved summary | confirmed | important | fixed in `d8bcf74` by the human's decision (option 1, 2026-10-19), an approved exception to AC-1 for this row only, said under the table |
| U1 | 1 | local (spec, AC-4) | AC-4 was checked against the one private name the human gave; whether the list is complete is unknown | unverifiable | — | residual risk: 0 hits in the diff, `git log -p`, commit messages and the pull request; left to the human at the merge gate |

## Found on the way

- **O1.** `openspec validate --specs --strict` is red on `main`: 33 of 39 specs fail
  (openspec 1.14.1, `--strict` turns warnings into errors). Recorded as P2 in BACKLOG.md
  (`f7051c3`); the Checks section of `.lado/sdlc.md` is the human's to fix. At archive the
  check was red with the same 33 of 39, unchanged by the archive (the change has no delta).

## Checks

- `make lint`: exit 0.
- `openspec validate cloud-workers-research --strict`: valid.
- CI of #104 on `f7051c3`: every job success, `ci-ok` success; smoke skipped by the skip
  list (docs, openspec, BACKLOG, ROADMAP only).
- Not run locally: `make test`, integration, UI: no code in the diff, CI ran them.

## Metrics

- Rounds: 2 local, 1 external, 0 substitutes.
- Confirmed: 1 local (F1), 3 external (F2, F3, F4). Refuted: 0. Unverifiable: 1 (U1).
- Declined: none.
- Findings in code after the developer's cleanup: 0 (documents only).

## Residual risk

- U1: the attribution, R2 above all (about 1900 lines of product survey), was checked
  against one private name only.
- The external reviewer is of the same model family as the kit's agents: its "nothing
  found" weighs less.
