# LAD-167 codex-subagents-off: review report

Pull request #190 `hotfix/lad-167-codex-subagents-off` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `17dd849f` (= the remote head). A Codex agent's config
switches both versions of Codex's own subagents off (`features.multi_agent`,
`features.multi_agent_v2`, `[agents] enabled = false`), since newer OpenAI models turned
the second version on through their metadata and the supervisor hung on "Waiting for
agents"; LADO's first input now asks the agent to end its turn instead of waiting.
`providers/codex.py`, `runtime.py` and `tests/live/` changed.

## Rounds

- **Round 1** (`ca7548fc..17dd849f`, the whole pull request): a local precision pass that
  read the whole diff, the spec, the tasks and the docs (both requirements and all five
  scenarios have code and a test; D1-D5 kept); external 1 of 1 (Claude Code GitHub
  Action), which read every file of code, tests and docs but BACKLOG.md and openspec. No
  blocking or important findings.

External rounds used: 1 of 1 (the hotfix cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | The live test checks only the last segments of the names in `SUBAGENT_TOOLS`, so a call of `collaboration.send_message`, `list_agents`, `followup_task` or `interrupt_agent` would pass it; the smoke test checks the `collaboration.` prefix and is stricter | declined at convergence |
| F2 | minor | `fake_endpoint.tool_names` records `None` for a tool without a name (and a `KeyError` on a malformed body): the smoke test would fail with an `AttributeError` instead of a clear assert; no false green | declined at convergence |
| F3 | — | external: the smoke test may flake if the first request is not a turn | unverifiable: only `POST /v1/responses` seen in probes; carried as a risk |
| F4 | minor | external: the new comment in `codex.py` splits an older paragraph | declined: cosmetic |

## Checks

- On `17dd849f`: `make lint` green; the Codex smoke tests 8 passed (Codex CLI 0.162.0);
  `openspec validate codex-subagents-off --strict` valid; `openspec validate --specs
  --strict` 53 passed; CI 23/23, integration, UI, JS, container and the Codex smoke on
  Linux and macOS.
- `make test` by the developer: 4694 passed; CI ran the unit tests on 3.10 and 3.13.
- Probes of the real `codex exec` against `tests/fake_endpoint.py` on gpt-6-sol and
  gpt-5.6-sol: six `collaboration.*` tools without a config and with
  `multi_agent`/`multi_agent_v2` off; none with `[agents] enabled = false`; six again with
  `multi_agent_v2 = true` beside it, which confirms D1 (both keys).

## Residual risk

- The live test `tests/live/test_codex_login.py::test_a_codex_supervisor_answers_the_human_s_first_message`
  is written, not run by the review: it needs the human's ChatGPT login (task 4.2). The
  format of Codex 0.162's rollout it reads is unconfirmed; whether the model really ends
  its start turn is shown only by a live run or the manual "hi" check.
- F3, a possible flake of the smoke test, not reproduced.
