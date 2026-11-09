# LAD-254 agent-popup-model: review report

Pull request #267 `hotfix/lad-254-agent-popup-model` → `main`. Scale: hotfix, depth precision.
Head reviewed: `75c88810`. An agent's popup in the session's head and on the terminals' strip
reads in three parts (the name with its status, labelled facts `Role`, `CLI`, `Model`, `Flow`,
the click's hint) and names the agent's model; CHANGELOG 0.45.0's item is corrected to what the
popup and `lado ls` show. Delta: changes to `session-head` and `agent-model`.

## Rounds

1. Local, precision, `8ad4ee8b..75c88810`: the whole diff against the spec; no finding.
2. External 1, Claude Code GitHub Action: no blockers, the observations E1 and E2. It read
   `Team.tsx`, `styles.css`, `fakes.ts`, `test_layout.py`, `CHANGELOG.md` and `ui.md`, not the
   openspec documents or the Vitest tests; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: `.tooltip .tip-agent` holds only while the popup is inside `.tooltip`; `.agent-tip .tip-agent` would be sturdier | declined: `AgentPopup` is rendered only as a `Tooltip`'s tip (the head's avatars, the terminals' strip) |
| E2 | minor | external: the facts' array holds `false` for a left-out `Role`, dropped only by the truthiness filter; `null` would read clearer | declined: the behaviour is right, a matter of reading |

## Found on the way

Nothing.

## Checks

On `75c88810`:
- `make web`: 82 files, 1842 Vitest tests passed, the stale-types check and the build green.
- UI e2e `tests/ui/test_layout.py`: 20 passed.
- `make lint` green; `openspec validate agent-popup-model --strict` valid.
- CI: `ci-ok` green (unit 3.10/3.13, integration, UI, container, web); smoke skipped by CI's
  rules, the diff being within its skip list.

## Not checked

- Locally: `make test`, integration, smoke, container and live; no Python changed, CI ran unit,
  integration and container.
- Live tests: not needed; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py` and `tests/live/` did not change.
- A named model (not `CLI default`) in a real browser: only the Vitest tests render it, as the
  fake agent names no model (design D3).
