# LAD-295 smoke-model-list-time: review report

Pull request #349 `hotfix/lad-295-smoke-model-list-time` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `5824e0a1`. The fixture `smoke_provider`
(`tests/smoke/conftest.py`) sets `base.MODEL_LIST_TIMEOUT` to 60 s for every smoke test, so a
fresh CLI home on a loaded CI runner (`kilo models` fetching its list beside two other workers)
no longer trips the users' 15 s; the assertion of `test_the_session_s_model_reaches_the_cli`
is unchanged, and users keep 15 s. Tests and docs only: no `src/`, `web/`, schema or API
change, no CHANGELOG.md line; a delta to continuous-integration.

## Rounds

1. Local, precision and a check against the design, `origin/main..5824e0a1`. External 1,
   Claude Code GitHub Action: no blockers, one minor finding (F2); every risky file read,
   `proposal.md` not read (a document, not code).

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `design_ok`**: the users' limit stays 15 s (#7693); a hanging CLI must not hold the
  start longer.
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the new sentence in the smoke paragraph of `docs/testing.md` left a line of 128 characters | declined: style only; the file already has lines over 100 (46, 156, 160, 212) |
| F2 | minor | external: 60 is a bare literal in the fixture, not a named constant | declined: one use, with a comment naming why; a constant with no second user goes against "Only what is used" |

## Checked against the code

- The patch reaches the check: only `src/lado/providers/base.py:456` reads
  `MODEL_LIST_TIMEOUT`, as a module global at call time, and the smoke runs
  `runtime.start_session` in pytest's process; the developer's AC-2 probe at 0.5 s failed with
  `timed out after 0.5 s`.
- Every test of `tests/smoke/test_smoke.py` and `test_codex_git_server.py` takes
  `smoke_provider` (AC-1); `monkeypatch` restores the value after each test.
- The assertion is unchanged, so "A list that never answers" holds; `src/` is unchanged, so
  "Users keep their limit" holds, and `tests/test_model_check.py:114` still proves the timeout.
- Every task of `tasks.md` checked; nothing out of scope done.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `openspec validate smoke-model-list-time --strict` | valid |
| `openspec validate --specs --strict`, and after a trial archive | 87 passed |
| CI run 44698760641 on `5824e0a1` | 27 of 27 green on the first attempt, `smoke macos-latest kilo` among them |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 1, external 1, both minor.
Refuted: 0. Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing new; a local smoke red with `OPENROUTER_API_KEY` in the shell is in BACKLOG.md (P2).

## Not verified (residual risk)

- One green CI does not prove the flake gone: it came about once a month; the margin is four
  times larger.
- The reviewer ran neither the smoke nor `make test`; by the developer's report kilo's smoke
  passed locally (14 passed, `env -u OPENROUTER_API_KEY`) and `make test` 6075 passed; CI green.

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
