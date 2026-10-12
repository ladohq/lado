# LAD-25 question-card-choice-once: review report

Pull request #9 `fix/lad-25-question-card-choice-once` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `afdc142`; the archive commit follows it. Web UI only:
`web/src/Question.tsx`, `web/src/styles.css`, `web/src/Chat.test.tsx`,
`tests/ui/test_chat.py`, docs/design/ui.md, CHANGELOG.md and the openspec change; no core,
API, MCP or schema change.

## Rounds

- **Round 1** (`origin/main...afdc142`, 4 commits): local precision pass over the whole
  diff (`Given`, `replyOf` and the `.chosen` list of `Question.tsx`, the styles, the vitest
  and UI e2e tests, docs/design/ui.md, CHANGELOG, the change's proposal, spec and tasks);
  the screenshots checked against docs/design/ui.md and the approved option A. External
  round by the Claude Code Action (request comment 6130561504, "Claude finished" in
  comment 6130565822). No blockers, no important findings.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: spec | `tasks.md` 2.1 names `test_the_chat_looks_as_a_feed_in_light_and_dark`, while `test_each_message_says_its_text_once_…` was changed; the check of 1.1 (`grep -rn answer-choice web/src` finds nothing) finds the negative assertion in `Chat.test.tsx` | confirmed | minor | declined: wording of the plan only, named in the build report; code and tests are right |
| E1 | 1 | external (Action) | A chosen choice not in the question's `choices` would show nowhere in the closed card | refuted | — | dropped: the core refuses such an answer (`src/lado/runtime.py`, `question #N has no choice ...`); answered in the PR (comment 6130587908) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 1 (F1) | 0 | — |
| external, Claude Code Action | 0 | 1 (E1) | — |

No blocker or important finding. All four scenarios of `chat-question-card` are covered by
tests that fail on the old code.

## Found on the way

Nothing.

## Checks

- On `afdc142`: `make web` 36 files, 647 passed (tsc, stale-types check, build);
  `uv run pytest -m ui tests/ui/test_chat.py -n0` 10 passed; `make lint` clean;
  `openspec validate --specs --strict` 5 passed, the change valid.
- CI of PR #9 on `afdc142` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos ×
  claude/codex/kilo/opencode.
- Not run locally: `make test` (no Python changed; green in CI, the developer's run 2487
  passed), integration (unchanged; in CI), live and local smoke (UI only).
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed before the merge.

## Result

Converged after round 1 (1 of 1 external rounds).
