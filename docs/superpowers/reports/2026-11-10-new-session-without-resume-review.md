# LAD-261 new-session-without-resume: review report

Pull request #272 `hotfix/lad-261-new-session-without-resume` → `main`. Scale: hotfix, depth
precision. Head reviewed: `2becc7fb`. The New session window no longer offers `Resume <name>`
beside a stopped session of the place: it shows one start button, `Start new session <free name>`
(in a project `Start new session in <title>`), the primary, and Enter starts the new session; a
stopped session is resumed from its page or the session list, where the Resume window opens on the
session's own CLI and model. Delta: changes to `new-session-window` and `projects`.

## Rounds

1. Local, precision. The whole diff, the change's spec and the tests. `resumeStopped`, `act`,
   `startButton` and `onlyTouched` are gone from `web/src/Launch.tsx` with no dangling reference;
   `changedFrom` is now called only from the Resume window, whose base is the session itself, which
   removes the defect's cause. `.peer` and `.launch-buttons.two` are used nowhere else. AC-1…AC-5
   are covered by vitest and UI e2e; every task of `tasks.md` is checked. No findings.
2. External 1, Claude Code GitHub Action: X1 and X2, both refuted. It did not read
   `web/src/Launch.test.tsx` or the openspec files; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| X1 | — | external: `busyLabel.resume` ("Resuming…") is now reached only in the Resume window | refuted: the Resume window sets `setBusyKind("resume")` in `submit()` and needs the label |
| X2 | — | external: to resume a session the human must go to its page or the session list | refuted: the human's choice (option E, answer #5411), recorded in the design and the REMOVED requirement's Migration |

## Found on the way

None.

## Checks

On `2becc7fb`:
- `npx vitest run src/Launch.test.tsx` 221 passed; `tsc --noEmit` green;
  `openspec validate new-session-without-resume --strict` valid; trial archive, then
  `openspec validate --specs --strict` 82 passed.
- CI: all green with `ci-ok` (unit 3.10/3.13, integration 6/6, web, ui 4/4, container 4/4); smoke
  skipped, the diff is within the skip list. No reruns.

## Not checked

- `make test`, `make lint` and UI e2e were not run locally; CI ran them on the same head.
- Live and smoke tests: not run; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py` and `tests/live/` did not change.
