# LAD-62 flow-step-direction: review report

Pull request #48 `fix/lad-62-flow-step-direction` → `main`. Scale: tweak, reviewed for
precision, at most one external round. Head reviewed last: `9b2cf28` (= the remote head);
the archive commit follows it. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so live tests are not needed before the
merge.

## Rounds

- **Round 1, local** (precision over `origin/main...bb0213d`: the diff, the spec and
  tasks, then the tests, then the build report): F1.
- **Round 2, local** (precision over `bb0213d..06abdcc`): F1 closed; F2.
- **Round 3, local** (precision over `06abdcc..9b2cf28`, openspec texts only): F2 closed,
  no new finding.
- **Round 1, external** (Claude Code GitHub Action, request 2026-10-14T20:29:02Z, answer
  20:31-20:32Z, on `9b2cf28`): no blocker; E1, E3, E4 declined as minor, E2 refuted; a
  fifth remark (the declared-order rule in a cycle) taken as intended, no finding. The
  analysis is posted on the pull request.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec, tests) | the step's direction did not reach the accessible name: Chromium drops an `aria-label` on a plain `<span>`, and the tests checked only the attribute | confirmed | important | fixed in `06abdcc`: hidden `.visually-hidden` text after the chip (`flowSteps.tsx`); tests check what is read out (`aria_snapshot` in `tests/ui/test_flows_tab.py`, `textContent` in vitest), red on the old bundle, green on the new |
| F2 | 2 | local (spec) | after F1 the spec and proposal still required the chip's own accessible name | confirmed | important | fixed in `9b2cf28`: "SHALL say the direction to assistive technology with the outcome", scenario "a screen reader reads it as `changes, a step back`" |
| E1 | ext. 1 | external | while the runs load, the chat's chips are neutral, then take their colour | confirmed | minor | declined: the spec asks for it; guessing by a second rule was the original bug |
| E2 | ext. 1 | external | in the Flows tab a chip of unknown direction became neutral | refuted | — | dropped: `.feed-chip` without a modifier keeps the green ground (`styles.css`), as before |
| E3 | ext. 1 | external | `Flows.tsx` calls `direction` twice, for the dot and in `OutcomeChip` | confirmed | minor | declined: the call is cheap; a shared helper would add indirection |
| E4 | ext. 1 | external | the "Runs again" tooltip cannot be reached from the keyboard | confirmed | minor | declined: out of scope by design; the direction is read out |

## Checks

- On `06abdcc` (code unchanged since; `9b2cf28` changes openspec texts only): `make web`
  728/728, `make lint` ok, `uv run pytest -m ui tests/ui/test_chat.py
  tests/ui/test_flows_tab.py -n 4` 20 passed.
- On `9b2cf28`: `openspec validate flow-step-direction --strict` valid,
  `openspec validate --specs --strict` 22 passed.
- CI on `9b2cf28` (run 38632366555): `ci-ok` success; unit 3.10/3.13, integration 6/6,
  ui 2/2 and js success; smoke skipped, every file on the skip list.

## Stop

Converged: no blocker and no confirmed important finding in the last round, CI green, the
pull request's title and description match the diff.

## Metrics

- Rounds: 3 local, 1 external, 0 replacements of the external.
- Findings: local 2 confirmed, 0 refuted; external 3 confirmed (all minor, declined), 1
  refuted.
- Findings in code reworked by the developer's cleanup: 0.

## Not checked (residual risk)

- `make test` was not run locally (no Python changed); CI ran it.
- The smoke was skipped by CI: the changes are on the skip list.
- The "back" rule relies on the order a flow declares its states: a kit that declares a
  branch after the state it joins colours that step wrongly. ui.md advises kit authors;
  nothing checks it.
- The "Runs again" tooltip cannot be reached from the keyboard (E4).
- The read-out was checked in Chromium's accessibility tree (`aria_snapshot`), not with a
  real screen reader (VoiceOver, NVDA).

## Found on the way

Nothing.
