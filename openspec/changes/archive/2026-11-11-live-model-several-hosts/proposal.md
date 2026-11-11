Task: LAD-273

## Why

The live run of 0.46.1rc1 (`live.yml`, run 43065905041, commit 2579d9e3) is red: Codex failed
in both attempts, Kilo failed and passed on a rerun, each on OpenRouter's 429. The same happened
on 0.46.0rc1. The key is fine (paid, credits left).

Cause, checked by the supervisor: the three cells of Codex, Kilo and OpenCode run on
`qwen/qwen3.7-flash`, which OpenRouter serves from one host only, Alibaba. That host's shared
pool is exhausted (`qwen/qwen3.7-flash is temporarily rate-limited upstream`,
`limit_source: upstream_provider_shared_pool`, `provider_error_code: insufficient_quota` /
`limit_requests`); 4 of 5 tiny requests got 429. OpenRouter cannot route around a model's only
host. The model was chosen by price alone (LAD-231, `openspec/changes/archive/2026-11-07-cloud-live-tests/design.md`
D8, report `docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`); its fallback there
was `openai/gpt-5-nano`.

Options weighed:

- A (taken, the human's decisions #5980 and #6017): a new rule for the live model of a cell:
  OpenRouter serves it from more than one host; it declares tools and images; its tool calls
  are reliable; then the cheapest. The trial began on `openai/gpt-5-nano` (hosts OpenAI and
  Azure, $0.05 / $0.40 per million tokens): its tool calls did not hold (Codex 0 and 1 of 4
  tests, Kilo the same test red twice, OpenCode once). The human then chose
  `anthropic/claude-haiku-5.5` (five hosts: Anthropic, Amazon Bedrock, Azure, Google, Claude
  Platform on AWS; $0.10 / $0.50), green in every run of the Claude Code cell, for all four
  cells, Codex included if it passes (else `openai/gpt-5.4-nano`, then `openai/gpt-5-mini`).
  Long-term cost: a run of four cells about twice that of qwen, still cents; one model for the
  four cells; a rule that the next model choice follows.
- B: keep qwen and rely on reruns of red cells. A whole pool exhausted for days makes every RC
  red by chance; a rerun proves nothing. Rejected.
- C: OpenRouter's fallback of models (a list of models per request) or provider routing in each
  CLI's config. It needs code in `tests/live_models.py` for three CLIs, each with its own
  config format, while main is frozen for the RC; and a fallback hides which model a test
  passed on, which the tests check. Rejected.

Claude Code stays on `anthropic/claude-haiku-5.5`; the three other cells join it.

## What Changes

- `.github/workflows/live.yml`: the matrix's models of `codex`, `kilo` and `opencode` become
  `anthropic/claude-haiku-5.5`, the model each passed the trial on; its comment names the rule
  and the new trial report.
- `docs/superpowers/reports/2026-11-11-live-model-several-hosts-trial.md`: the trial, its runs,
  failures with causes, and the cost read from the key's usage.
- `docs/testing.md`: the rule for choosing a live model; the trial that chose the models and the
  cost of a run of four cells from the new report.
- Capability `continuous-integration`: the requirement "Live tests run weekly and by hand
  outside ci-ok" gains the rule for a cell's model.
- No CHANGELOG item: users of LADO do not see the CI's model. No version change: CI and docs
  only, nothing under `src/`.

## Scope

Changed: `.github/workflows/live.yml`, `docs/testing.md`, the new trial report, this change.
Nothing under `src/`, `tests/` or `scripts/`: main is frozen at the RC, and the final must equal
it.

## Out of scope

- OpenRouter's model fallback or provider routing (option C): code in the frozen tests, and it
  hides the model a test ran on.
- Claude Code's model: haiku has many hosts and passed every run; it stays.
- A unit test that a cell's model has several hosts: it needs OpenRouter's network API, which no
  unit test reaches; the trial and the report check it.
- A Codex agent whose turn ends on an API error stays busy (BACKLOG.md, "A Codex agent whose
  turn ends on a model or API error stays busy"): a known entry, its own task.
- Rewriting the archived trial report of LAD-231: it stays as history; the new report supersedes
  its choice of model.

## Impact

- The RC's live run: Codex, Kilo and OpenCode no longer depend on one host's quota.
- Cost: a run of four cells rises from about $0.07 to about $0.13 (the trial's report), within
  the key's $10 a month.
