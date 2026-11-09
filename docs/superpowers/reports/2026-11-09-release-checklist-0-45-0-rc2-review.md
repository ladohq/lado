# LAD-258 release-checklist-0-45-0-rc2: review report

Pull request #270 `fix/lad-258-release-checklist-rc2` → `main`. Scale: tweak, depth precision. Head
reviewed: `1ea54f2b`. The 0.45.0 checklist: rc1's wrong expectations corrected in place, check 4.3
a session of the built-in supervisor instead of an sdlc run, 4.4 with the whole recipe of the test
home, and the new section `## 0.45.0rc2`. Docs and one unit test only; no delta (`--skip-specs`).

## Rounds

1. Local, precision, `origin/main...11932ada`: the diff read by hand, every exact line checked
   against the code. Found F1.
2. Local, precision, `11932ada..1ea54f2b` (one line of the document): F1 closed, nothing new.
   External 1, Claude Code GitHub Action: no defects, two notes (E1, E2), both refuted. It read the
   diffs of the documents and the test and the code the lines come from, not the openspec change's
   files or the unchanged parts of `docs/releases/0.45.0.md`.

## Findings

| ID | Source | Finding | Verdict | Fate |
|---|---|---|---|---|
| F1 | local | rc1's line of a server's removal lacked `Its key is deleted too.`, which the code prints for a server with a key (`web/src/ModelSources.tsx`) | confirmed, important | fixed in `1ea54f2b` |
| E1 | external | "Codex's shared login, live" asks for a clone at `v0.45.0rc2` before the tag exists | refuted | the manual checklist runs after the RC's tag is pushed (docs/release.md, section 2, step 4) |
| E2 | external | the new test pins the whole text of the 4.3 line | refuted | intended: it catches the line drifting from what rc_check prints (tasks 4.1, decision 6) |

## Checks

- Round 1: `uv run pytest -n0 tests/test_rc_check.py tests/test_release_check.py
  tests/test_agents_md.py` 98 passed; `make lint` green; `openspec validate
  release-checklist-0-45-0-rc2 --strict` valid.
- CI on `1ea54f2b`: 27 of 27 checks pass, `ci-ok` included.

## Not checked, residual risk

- The checklist's texts were checked against the code statically; whether 4.4's recipe and rc2's
  scenarios (the container without a login, OpenRouter) run as written shows only rc2's manual
  check.
- No full local `make test` (CI ran every layer); no live tests: no code changed, nothing under
  `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.

## Found on the way

None.
