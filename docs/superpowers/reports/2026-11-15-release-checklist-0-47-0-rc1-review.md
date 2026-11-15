# LAD-286 release-checklist-0-47-0-rc1: review report

Pull request #317 `fix/lad-286-release-checklist-0-47-0-rc1` → `main`. Scale: tweak, depth
precision. Head reviewed: `97dce2c3`. The diff is documentation, CHANGELOG's Upgrade group
for 0.47.0 and one line of a test (the 0.47.0rc1 checklist among the real files), no
business logic, so no broad pass was made.

## Rounds

1. Local, precision, over `origin/main...97dce2c3`: tasks.md 6/6 checked; the text of
   `docs/releases/0.47.0.md` matches the proposal's block byte for byte; every quote checked
   against the code (`runtime.py`, `scripts/rc_check.py`, `hooks.py`, `providers/claude.py`,
   `kits.py`, `self_update.py`); all 16 named test files and folders exist; the LAD-173
   claim checked on live runs 43642033390 and 43642039014 (`6379201b`), green on 4 CLIs.
   Nothing found.
2. External 1, Claude Code GitHub Action, the whole pull request: three notes E1–E3,
   answered in the pull request.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: the quote «… Everything LADO recorded since then is lost: sessions, runs, …» is one line, while the terminal wraps it after `sessions,` | declined: the words match `self_update.py`; only the wrap differs, and the human compares it by eye |
| E2 | — | external: the check «no `Not started: …` line» is negative and cannot fail | refuted: on a build without the LAD-209 fix (`808f17f3`) the line is there, so the check proves the fix is in the RC; `web/src/Launch.test.tsx` guards it too |
| E3 | — | external: two `<filled in at the RC>` placeholders | refuted: by design, the RC commit and the live.yml run exist only after the merge (docs/release.md, section 2) |

Found on the way: nothing.

## Checks

- `make lint`: exit 0.
- `uv run pytest -n0 tests/test_rc_check.py`: 83 passed.
- `openspec validate release-checklist-0-47-0-rc1 --strict`: valid; a trial archive with
  `--skip-specs`, then `openspec validate --specs --strict`: 85 passed.
- `scripts/release_notes.py v0.47.0rc1` prints `### Upgrade` with its item.
- CI of #317 on `97dce2c3`: 27/27 pass, `ci-ok` and the smoke on Linux and macOS for all
  4 providers included.

## Not checked

- `make test` as a whole was not run by the reviewer (the developer's run: 5718 passed;
  green in CI).
- `scripts/rc_check.py` was not run: it installs the package from PyPI; its list is guarded
  by the real-checklists test.
- That each vitest and browser file covers its checklist item was checked by the file's
  existence and the task's history, not by reading its assertions; the checklist's manual
  checks are done at the RC.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`.
