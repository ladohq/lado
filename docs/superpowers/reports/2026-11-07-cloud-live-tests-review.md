# LAD-231 cloud-live-tests: review report

Pull request #247 `feature/lad-231-cloud-live-tests` → `main`. Scale: full, review depth: breadth
first. Head reviewed: `8ed17276`. The live tests of all four providers move to cheap models on
OpenRouter, one entry per provider in `tests/live_models.py`; LM Studio, the LiteLLM bridge and
Claude Code's personal login leave them; `.github/workflows/live.yml` runs them weekly and by hand,
outside `ci-ok`; `scripts/smoke_ci.py live` is the cell. `src/` is unchanged: no schema migration,
no MCP or CLI change, no CHANGELOG.md line. Delta: 6 requirements added to
`continuous-integration`. Trial: `2026-11-07-cloud-live-tests-trial.md`.

## Rounds

1. Local, breadth, `origin/main...4685b63c`: lenses spec, tests, silent failures, comments and
   descriptions, general, architecture by AGENTS.md; the types lens skipped, as there are no new
   types. 2 important, 4 minor, 5 refuted.
2. Local, precision, `4685b63c..8ed17276`: no new findings. F1 and F2 reproduced again on the new
   code, now closed. `redact` timed: 36 MB of near matches in 0.8 s.
3. External 1, Claude Code GitHub Action, the whole pull request, `3f7222ff..8ed17276`: no blocker,
   one minor (E1). It read `live.yml`, the diff of `scripts/smoke_ci.py`, `tests/live_models.py`,
   `tests/real_clis.py`, `tests/smoke/conftest.py`, `tests/live/conftest.py`,
   `tests/live/test_live.py`, `tests/test_live_workflow.py`; not `tests/test_smoke_ci.py`,
   `tests/test_live_models.py`, the documents or openspec, which only the local reviewer read. It
   ran no tests, having no shell permission. It is the same model family as the kit's agents.

External rounds used: 1 of 2. Stand-ins: 0.

## The human's decisions

- **Design:** the paid-model rule is replaced (a limited key and the human's yes; the schedule in
  CI is that yes, given once by this task); $5 for the trial, $10 a month for CI, on a key of its
  own; weekly plus the button; a red run mails, no automatic retries; LM Studio goes; the release's
  live step is the button on the RC's commit; Claude Code on OpenRouter, with no subscription and
  no Anthropic key.
- **D16:** a real subscription login is no longer covered by any live test, as decided.
- **Gate `merge_ok`, approved** on `8ed17276`.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | a red Codex cell crashed while copying evidence with a dangling link and uploaded nothing | fixed in `63ead97f`, `test_a_red_cell_with_a_dangling_link_keeps_its_log_and_evidence`, `test_evidence_that_cannot_be_copied_costs_a_cell_nothing_else` |
| F2 | important | a key wrapped by the tmux window's width was neither redacted nor masked by GitHub | fixed in `63ead97f`, `test_redact_finds_a_key_torn_by_a_window`, `test_a_torn_key_reaches_neither_the_folder_nor_the_job_s_log`; checked on a real 80x24 tmux snapshot |
| F4 | minor | the spec promised evidence of a hung test | fixed in `a7d9ea0b`, `63ead97f`, text |
| F5 | minor | `LOGIN_VARIABLES` repeated the smoke's list | fixed in `a7d9ea0b`, one list |
| F6 | minor | docs/testing.md did not name the prefix `endpoint/` | fixed in `a7d9ea0b` |
| F7 | minor | D9 differed from the trial's key | fixed in `a7d9ea0b` |
| E1 | minor | external: `npm install` in the cell sees `LADO_LIVE_API_KEY` | declined: the same pinned packages run with the key right after it, so no boundary is lost, and the spec speaks of the step; answered on the pull request |
| F3 | — | the trial did not check Codex's sandbox on a runner | refuted: the live session runs in `bypassPermissions`, where Codex starts without its sandbox; the reviewer's premise was wrong |
| R1 | — | `redact` skips links, so their targets leave unredacted | refuted: `cell` resolves links before `redact`; the external reviewer agreed |
| R2 | — | `tool_result` weakens `check_turn_end_output` | refuted: both channels are covered in `tests/integration/test_agents.py` and `tests/integration/test_mid_turn_messages.py` |
| R3 | — | `state.read_messages` in the test hides a product defect | refuted: the refusal is meant, `src/lado/runtime.py` |
| R4 | — | agents on a runner have no commit author | refuted: `tests/agent_helpers.py` sets one |

Metrics: confirmed 6 local and 1 external; refuted 5 local and 0 external; findings in code changed
by the developer's clean-up: 0.

## Checks on `8ed17276`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 4861 passed, 7 skipped |
| `openspec validate cloud-live-tests --strict` | passed |
| `openspec validate --specs --strict` | 67 passed |
| Trial archive, then the specs | 67 passed |
| CI of PR #247 | 23 checks SUCCESS, `ci-ok` pass |

## Not checked

- `scripts/smoke_ci.py live` with a real install and real tests: run by nobody, the cell is proved
  by stubs only.
- `live.yml` itself: GitHub offers the button only on the default branch; the human's first run
  after the merge closes AC-3.
- The live tests after `5b6e5e9a`, where the last trial ran: of the live code only the import of
  `LOGIN_VARIABLES` in `tests/live/conftest.py` changed since, checked by collection.
- Integration, UI and smoke tests locally: CI ran them.

## Residual risk

- A key cut with an ellipsis by a CLI's interface escapes `redact`, and its start stays in a public
  file. It needs a model to print its environment; the key is limited to $10 a month.
- If `redact` itself fails, the cell is red with no log and no files: a safe failure.
- A running cell is silent in the job's log for up to 25 minutes, and a job killed before the
  redaction leaves nothing (docs/testing.md, D5).
- OpenCode on `qwen/qwen3.7-flash` passed 2 of 3 runs, so AC-3's first run may need a rerun of that
  cell.

## Notes on the way

- The line on `make test-live` in `.lado/sdlc.md` changed in `12e51a60`, by the developer's report
  on the human's word through the supervisor; the reviewer did not see that word.
- The developer took the permission for `OPENROUTER_API_KEY` as the yes to the paid trial and did
  not ask separately. Spent: $0.30.
- `3e84e136` was pushed with lint red, fixed in `8ed17276`; the temporary probe `97a2bcb9` stays in
  the history.
- Found on the way: `tests/live/test_codex_login.py` has no step in a release, in BACKLOG.md since
  `4bbaa745`.
