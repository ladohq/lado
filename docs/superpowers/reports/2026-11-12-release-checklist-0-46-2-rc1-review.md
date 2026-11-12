# LAD-278 release-checklist-0-46-2-rc1: review report

Pull request #294 `fix/lad-278-release-checklist-0-46-2-rc1` → `main`. Scale: tweak, depth
precision. Head reviewed: `e8a05d4c`. The release checklist `docs/releases/0.46.2.md` gets the
section `0.46.2rc1` (hand checks of answers in the chat on weak and strong models, what going back
to 0.46.1 loses, what covers the one CHANGELOG item), and the real-file test of
`tests/test_rc_check.py` also checks `0.46.2rc1`. No delta (`--skip-specs`).

## Rounds

1. Local, precision. The diff `da59cd18..e8a05d4c` against the change's proposal, tasks and the
   design's decisions; the checklist's text compared byte for byte with the approved block of the
   proposal; every quoted line checked against the code (`runtime.HUMAN_REPLY_HINT`,
   `hooks.REPLY_REMINDER`, `web/src/Chat.tsx`'s `replied only in its terminal`); the 9 named test
   files exist; the rollback claim checked on `v0.46.1` (its API model has no `reminded`).
   Finding F1.
2. External 1, Claude Code GitHub Action: no blockers; F1 repeated, F2 and F3 confirmed (minor).
   It did not read the openspec files only; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local and external: "Before you start" does not name a Linux machine, which 4.5 of every RC needs (0.46.1's checklist had the line) | declined, left to the human at the merge gate: `rc_check.py` prints 4.5 among every RC's checks, so the check is not lost; the text was approved word for word |
| F2 | minor | external: the item "What 0.46.1 loses" has no step to try it | declined: by design, the human's decision (#6340, 2) |
| F3 | minor | external: the first line of the same item is long | declined: 4.7 asks only that the first line name the check, which it does |

## Found on the way

None.

## Checks

On `e8a05d4c`:
- `uv run pytest -n0 tests/test_rc_check.py` 82 passed; `openspec validate
  release-checklist-0-46-2-rc1 --strict` valid.
- CI: all 27 checks green, `ci-ok` success; the pull request mergeable, `CLEAN`.

Not run: `scripts/rc_check.py` itself (it installs from PyPI; the unit test covers its list); live,
smoke and integration tests locally (CI ran the integration tests; live runs at the RC through
`live.yml`). No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
or `tests/live/`.
