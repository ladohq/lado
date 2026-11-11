## 1. The trial (live, by hand)

- [x] 1.1 Before any run: the hosts of each candidate from OpenRouter's public
  `https://openrouter.ai/api/v1/models/<model>/endpoints` (`openai/gpt-5-nano`: OpenAI, Azure on
  2026-11-11), with tools and images declared; and the key's usage from
  `https://openrouter.ai/api/v1/key` with `OPENROUTER_API_KEY` (the human's key, allowed for
  this trial under $1). Never print the key: send it in the header, print only `usage`.
- [x] 1.2 Three runs of each of `codex`, `kilo`, `opencode` one after another on
  `openai/gpt-5-nano`, with the CLIs at the pins of `scripts/smoke_ci.py`:
  `LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1 LADO_LIVE_API_KEY="$OPENROUTER_API_KEY"
  LADO_LIVE_MODEL=openai/gpt-5-nano LADO_LIVE_IMAGE=1 uv run python scripts/smoke_ci.py live
  <provider> <out>` (the cell's own pass rule: a pass and no skip), the usage read after each
  run. Then one run of the three cells at once, as in CI. Each red test's cause from its
  evidence: a 429 or another host error, the model's (a tool call answered as text), or the
  test's.
- [x] 1.3 A CLI passes on a model when its four runs are green; one red run whose cause is the
  model's and not a host's passes when its rerun is green, and the report names it a flake. A
  429, a second red or a red without a cause: that CLI goes to the next model. The order, by the
  human's decision #6017 after `openai/gpt-5-nano` failed: `anthropic/claude-haiku-5.5` for all
  three, Codex then `openai/gpt-5.4-nano`, then `openai/gpt-5-mini`. Red on all: stop and report
  `redesign` with the evidence.
- [x] 1.4 Stop at $0.90 of usage spent since 1.1, whatever is left, and report it.

## 2. The files

- [x] 2.1 `.github/workflows/live.yml`: each of the three cells on the model it passed on
  (Claude Code's cell stays on `anthropic/claude-haiku-5.5`); the matrix comment says the rule (more than
  one host on OpenRouter, tools and images, reliable tool calls, then the price; the CLI's own
  vendor dropped, as the trial showed Codex needs no OpenAI model) and names the new report.
  Check: `uv run pytest tests/test_live_workflow.py tests/test_workflow_security.py -n0`.
- [x] 2.2 `docs/superpowers/reports/2026-11-11-live-model-several-hosts-trial.md`, in the shape of
  the 2026-11-07 report: task, change, date, setup (pins, endpoint, key), the hosts of each model,
  a table per CLI and model (runs passed, tests passed, cost of a run), the parallel run, each
  failure with its cause, the total cost, and why qwen left (the 429s of run 43065905041).
- [x] 2.3 `docs/testing.md`, the live tests: the rule of 2.1 for a cell's model, in a few lines;
  "the trial that chose them" names the new report (the old one stays as history); the cost of a
  run of four cells from the new report.
- [x] 2.4 No CHANGELOG item, no version change: users do not see the CI's model, and nothing
  under `src/` changes (proposal, What Changes).

## 3. Checks

- [x] 3.1 `make lint`, `make test`, `openspec validate live-model-several-hosts --strict`,
  `openspec validate --specs --strict` and the trial archive of the settings' Checks.
- [ ] 3.2 After the merge, before the tag: the supervisor dispatches `live.yml` on main
  (`gh workflow run live.yml`), and its four cells are green. Not yet: it runs only after the
  merge, as the key's environment admits only main and tags.
