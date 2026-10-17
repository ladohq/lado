# LAD-86 answer-files: review report

Pull request #97 `feature/lad-86-answer-files` → `main`. Scale: full, reviewed breadth
first. Head reviewed last: `c680049` (= the remote head), merge-base `3a8126c`. The pull
request changes `src/lado/runtime.py` (a reply's attachments and `human_files`, the one
helper `write_as_human` shares); `providers/`, `hooks.py`, `mcp_server.py`,
`agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1, local** (breadth over `3a8126c..c680049`; lenses spec, tests, silent
  failures, comments, types/invariants, general, architecture against AGENTS.md; the
  screenshots `shot-gate-tab`, `shot-gate-move`, `shot-question-answered` checked against
  `docs/design/ui.md` and the spec): F1, F2.
- **Round 1, external** (Claude Code GitHub Action, answer
  `issuecomment-6243271415`, finished in 40 s): E1, E2; it confirmed F1 and F2 as minor.
  The external reviewer is of the same model family, so its "nothing more" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | `gates.answer_note` is also set when `flow_set` forces a step over an open gate, while the comments and `docs/design/modules.md` call it the note of the *answer* | confirmed | minor | declined: text only, the behaviour is right (`force` attaches no files, so `answer_attachments` is empty); the external reviewer agreed |
| F2 | 1 | local (general) | `filesOnly` in `web/src/Question.tsx` hides the reply's own words when they start with `<n> file(s): ` and the reply has exactly n files | confirmed | minor | declined: a contrived edge, display only; the agent gets the whole text |
| E1 | 1 | external | when the upload succeeds but the answer is refused (question closed, gate already answered), the uploaded files stay as unreferenced session artifacts | confirmed | minor | declined: the composer's accepted order (D4); artifacts are the session's documents |
| E2 | 1 | external | files attached under Other… stay hidden in the card's state after a choice is picked and are not sent | refuted | — | dropped: by design (D2, `docs/design/ui.md`: Other… and Skip share files, a picked choice takes none) |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 2 (minor), refuted 0;
external confirmed 1 (minor), refuted 1. Findings in code changed by the developer's
cleanup: 0.

## Spec check

Every requirement and scenario of the delta (`question-answers`, `gate-answer-files`,
`chat-question-card`, `closed-gate-card`) is implemented and tested: the core in
`tests/test_runtime.py`, `tests/test_runs.py`, `tests/test_state.py` (schema 31); the
server in `tests/test_server_gates.py`, `tests/test_server_messages.py`; integration with
the fake agent reading a reply's file and a step's file; vitest for `attachFiles`,
`WaitingCard`, `Chat`, `Flows`; UI e2e in `tests/ui/test_gates.py`, `tests/ui/test_chat.py`.
`tasks.md` 12 of 12 checked; D1–D10 followed; nothing out of scope.

## Checks

- On `c680049`: `make lint` green; `make test` 3428 passed; `uv run pytest -m integration
  -n auto tests/integration/test_human_messages.py tests/integration/test_flow_runs.py`
  21 passed; `make web` green (51 files, vitest 905 passed, stale types clean); `openspec
  validate --specs --strict` 34 passed, the change valid in strict mode.
- CI of PR #97 on `c680049`: 23 of 23 SUCCESS, `ci-ok` among them (UI ×2, container
  amd64/arm64, smoke 8 cells).

## Not checked (residual risk)

- `make test-live`: only at a release. The change touches `runtime.py`.
- The smoke and UI e2e were not run locally by the reviewer: CI ran them on the same head.
- The external reviewer found no merge-base with `origin/main` in its checkout and read
  the tree against `origin/main`, ignoring files outside the pull request; it ran no
  tests.

Found on the way: none.
