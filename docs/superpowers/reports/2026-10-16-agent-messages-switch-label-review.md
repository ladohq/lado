# LAD-77 agent-messages-switch-label: review report

Pull request #72 `fix/lad-77-agent-messages-label` → `main`. Scale: tweak, reviewed for
precision over the diff, at most one external round. Head reviewed last: `7554355` (a
merge of `origin/main` over `a1a96cd`); the archive commit follows it. The diff touches
only `web/`, `tests/ui/`, `docs/design/ui.md`, CHANGELOG.md and the openspec change;
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change (the merge commit's `runtime.py` lines came from `main`,
LAD-68). No live or smoke test was needed before the merge.

## Rounds

- **Round 1, local** (precision over `origin/main...a1a96cd`: spec, tests, comments and
  the pull request's description, CSS, the architecture against AGENTS.md, the
  screenshots against `docs/design/ui.md` and the approved mockup, variant Б; then, on
  the supervisor's request, the team's row with 5 and 7 agents): F1, F2.
- **Round 2, local** (precision over `a1a96cd..7554355`, only the merge of `origin/main`:
  the pull request's diff against `main` is the same 12 files, the conflict in
  CHANGELOG.md resolved with both lines kept) and **external round 1** (Claude Code GitHub
  Action, request 20:12:01Z, answer 20:13:32Z, on `7554355`; it read `Sessions.tsx`,
  `icons.tsx` and `styles.css` only, and ran no tests): F3. The external reviewer is of
  the same model family, so its "nothing blocking" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (checks) | the pull request conflicted with `main` (CHANGELOG.md, LAD-68's lines under the same `0.40.0 (unreleased)`), so CI never ran on `a1a96cd` | confirmed | important | fixed in `7554355` (merge of `origin/main`, both lines kept); `ci-ok` green there |
| F2 | 1 | supervisor | with 5 or more agents the icon could stand alone at the start of the team's second line | refuted | — | `.team-row` does not wrap and the button is `flex: none`; only the chips inside `.team` wrap. A browser probe with 5 and 7 agents in a column of at most 484 px: 2 passed. The external reviewer agreed |
| F3 | ext. 1 | external | comments in `Sessions.tsx` and `styles.css` name `mockup-placement.html variant Б`, a file not in the repository | confirmed | minor | declined: the mockup is a run artifact, named so as `main` already names `mockup-team-chip.html variant B`; `docs/design/ui.md` gives its full name `task/lad-77/mockup-placement.html` |

## Checks

- Round 1: vitest 819 passed; `tsc --noEmit` clean; UI e2e `test_chat`, `test_layout`,
  `test_agents_tab` 33 passed; the 5/7-agent probe 2 passed; `openspec validate
  agent-messages-switch-label --strict` valid; all 6 tasks of tasks.md checked.
- Round 2: CI of #72 on `7554355`: unit (3.10, 3.13), integration (6 shards), js, ui (2
  shards), container (amd64, arm64) and `ci-ok` all green; the smoke skipped by its rule
  (the whole diff on the skip list).
- At archive: `openspec validate --specs --strict` 30 passed.

## Not checked / residual risk

- The external reviewer read the code only, not the tests, docs or spec; the local
  rounds checked those.
- Live and smoke tests were not run: nothing that starts or talks to an agent CLI
  changed.

## Found on the way

None.
