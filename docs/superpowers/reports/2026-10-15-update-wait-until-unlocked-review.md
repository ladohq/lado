# LAD-57 update-wait-until-unlocked: review report

Pull request #49 `hotfix/lad-57-update-wait-lock` → `main`. Scale: hotfix, precision
review. Head reviewed last: `5017991` (= the remote head); the archive commit follows it.
The diff changes only the wait's end condition in `web/src/SystemPanel.tsx` and the test
helper, so the breadth pass was not widened. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not change, so live tests are not
needed before the merge.

## Rounds

- **Round 1, local** (precision pass over `main...5017991`: the diff, spec
  `ui-update-wait`, tasks.md, the architecture against AGENTS.md): no defect. The
  requirement's code is `finished()` (`update.running` → false), and the `UpdateInfo` the
  page keeps is the answer that ended the wait (`setInfo(update)`), so its `running` is
  false. The three scenarios are covered by the vitest `the wait ends only once the
  update's lock is released` (four cases). `update_from_the_ui` waits by the same rule;
  both UI update tests keep their assertions, `info["running"] is False` included; no
  longer timeout, no retry. `self_update.run` and the API unchanged, as the design
  decided: the lock stays the one source of `running`.
- **Round 1, external** (Claude Code GitHub Action, request 2026-10-14T20:30:14Z, answer
  20:32:16Z, "Claude finished"): no defect, two minor remarks.

External rounds used: 1 of 1 (the cap for a hotfix).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | external | one over-long line left in `docs/design/ui.md` by the reflowed U2 paragraph | confirmed | minor | declined: cosmetic, the line was long before the change |
| F2 | 1 | external | the comment of `finished()`: "In both," reads better as "In both cases," | confirmed | minor | declined: style, the meaning is clear |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 0 | 0 | 0 |
| external, Claude Code Action | 2 (F1, F2) | 0 | 0 |

## Checks

- Reviewer on `5017991`: vitest `src/SystemPanel.test.tsx` 21 passed;
  `uv run pytest -m integration -n auto tests/integration/test_update_process.py`
  10 passed.
- CI: run 38631645547 on `c134ab7` success; run 38632434044 on `5017991` success
  (`ci-ok` green).
- At archive: `openspec validate --specs --strict` 23 passed.

## Found on the way

None.

## Not checked

- `make check`, `make test`, `make web`, `make lint` not run locally by the reviewer;
  the green CI covers them. Smoke and live not run (no provider changed).
- The reproduction by an injected delay and the 20 runs in a row are from the
  developer's build report; the reviewer did not repeat them.
- After the fix, `info["running"] is False` in the test is nearly always true by
  construction: a leaked lock would show as the wait's timeout ("the server back after
  the update"), not as that assertion; the test still fails, with a less precise message.
- The external reviewer is the same model family.

## Result

Converged after round 1 (1 of 1 external rounds).
