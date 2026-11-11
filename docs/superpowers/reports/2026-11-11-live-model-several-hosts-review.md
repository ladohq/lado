# LAD-273 live-model-several-hosts: review report

Pull request #291 `fix/lad-273-live-model-several-hosts` → `main`. Scale: tweak, depth
precision. Head reviewed: `433c01c7`. The live cells of Codex, Kilo and OpenCode leave
`qwen/qwen3.7-flash`, which OpenRouter serves from one host whose shared pool was exhausted
(429s of run 43065905041), for `anthropic/claude-haiku-5.5`, the model of the trial (the human's
decision #6017 after `openai/gpt-5-nano` failed); the capability `continuous-integration` gains
the rule that a cell's model has more than one host on OpenRouter and declares tools and images;
`docs/testing.md` names the rule and the new trial report.

## Rounds

1. Local, precision. The diff `main...433c01c7` (6 files, +268/−8) against the spec and the
   design; the hosts of `anthropic/claude-haiku-5.5` checked on OpenRouter's public endpoints
   API (five providers, all with tools, inputs text, image and file, $0.10 / $0.50). Finding F1.
2. External 1, Claude Code GitHub Action: all 6 files of the diff read; F2 and F4 confirmed
   (minor), F3 refuted.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the trial report's four parts of the cost already sum to the total ($0.559), yet the idle $0.002 is said to be in the total | declined: the total ($0.56) is right; wording |
| F2 | minor | external: the spec names only several hosts, tools and images; `docs/testing.md` also reliable tool calls | declined: by design (decision 1), the spec holds only what can be checked |
| F3 | — | external: the proposal still names Codex's fallback models and Claude's cell "staying" | refuted: consistent with the report and decision #6017 |
| F4 | minor | external: all four cells now on one model; a failure on the model's side reddens them all | declined: the human accepted it (#6017); five hosts remove the original cause |

## Found on the way

None.

## Checks

On `433c01c7`:
- `uv run pytest tests/test_live_workflow.py tests/test_workflow_security.py -n0`: 34 passed.
- `openspec validate live-model-several-hosts --strict` valid; `openspec validate --specs
  --strict`: 83 passed, 0 failed.
- CI of the pull request all green, no reruns.

Not run: the trial again (paid, the human's key; its numbers taken as reported, their arithmetic
and the hosts checked), `make lint` and `make test` locally (no Python changed; CI ran them).
`live.yml` on the new models has not run in CI yet (the `live` environment admits only main and
tags): task 3.2, the supervisor's dispatch on main after the merge and before the tag, proves
AC-6.

No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
