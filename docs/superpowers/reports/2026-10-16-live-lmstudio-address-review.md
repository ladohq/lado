# LAD-56 live-lmstudio-address: review report

Pull request #74 `hotfix/lad-56-lmstudio-v1` → `main`. Scale: hotfix, reviewed for
precision (not widened: only `tests/` and the openspec change changed, no product code).
Head reviewed: `0bfdcba` (= the remote head). `tests/live/conftest.py` changed: the
developer ran `make test-live PROVIDER=kilo` (3 of 3) and `PROVIDER=opencode` (3 of 3) on
LM Studio; the reviewer did not run them.

## Rounds

- **Round 1, local** (precision and the spec over `origin/main...0bfdcba`): F1. `make
  lint` 0, `tests/test_local_models.py` 26 passed, `pytest -m live --collect-only` 12
  collected, `openspec validate --specs --strict` 30 passed.
- **Round 1, external** (Claude Code GitHub Action, request 21:50:08Z, "Claude finished"
  21:50:24Z): F2, and agreement with F1. CI on `0bfdcba`: every job passed, `ci-ok`
  included (smoke on Linux and macOS for all four providers).

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | `tasks.md` 2.2 is checked though its part "LM Studio's log has no `Unexpected endpoint`" was not looked at | confirmed | minor | declined: documentation only; the live runs passing (3/3 each) are indirect proof, as before the fix every request missed `/v1` |
| F2 | ext 1 | external | `open(path).read()` in the new test instead of `Path(path).read_text()` | confirmed | minor | declined: style; the file mixes both already, same behaviour |

Blockers: 0. Important: 0. Refuted: 0.

## Checked

- Root cause: the conftest passed `lmstudio_url()` (no `/v1`) to `opencode_config`, which
  takes the URL as given since 6a6a5f9. `write_lmstudio_config` now writes
  `f"{lmstudio_url()}/v1"`; `lmstudio_url()` strips a trailing `/`.
- No other caller of `opencode_config` with LM Studio's address; the Codex bridge adds
  `/v1` itself and is untouched.
- The unit test (kilo and opencode × default URL and one with a trailing `/`) pins the
  variable, the model and `baseURL`, and fails without `/v1` (the developer saw 4 failed).
- No second rule of who adds `/v1`; the test is at the unit layer. No CHANGELOG line or
  version bump: only tests change.

## Not checked (residual risk)

- The reviewer did not run the live tests; LM Studio's log was not read by anyone (F1).
- Claude Code's and Codex's live tests were not run (paid / not affected).
- The full `make test` was not run locally; CI's unit jobs on 3.10 and 3.13 passed.

Found on the way: nothing.
