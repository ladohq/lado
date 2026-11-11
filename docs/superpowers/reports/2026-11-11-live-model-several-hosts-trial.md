# The trial of a live model with several hosts

Task: LAD-273. Change: `openspec/changes/live-model-several-hosts/`. Date: 2026-11-11.

Codex, Kilo and OpenCode leave `qwen/qwen3.7-flash` for `anthropic/claude-haiku-5.5`, the model
the Claude Code cell already runs on. All four cells of `live.yml` now run on one model with five
hosts on OpenRouter. A run of the four costs about $0.13; the whole trial cost $0.56.

## Why qwen left

The live run of 0.46.1rc1 (run 43065905041, commit 2579d9e3) was red: Codex in both attempts,
Kilo in the first, each on OpenRouter's 429. OpenRouter serves `qwen/qwen3.7-flash` from one host,
Alibaba, whose shared pool was exhausted (`qwen/qwen3.7-flash is temporarily rate-limited
upstream`, `limit_source: upstream_provider_shared_pool`); 4 of 5 tiny requests got 429.
OpenRouter cannot route around a model's only host, and LAD-231 had chosen the model by price
alone.

## Setup

`LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1`, `LADO_LIVE_IMAGE=1`, each run
`scripts/smoke_ci.py live <provider> <out>` with the CLIs at its pins (Codex 0.162.0, Kilo 7.8.8,
OpenCode 1.18.35), so the cell's own pass rule: pytest green, a pass and no skip. Four tests per
CLI: a worker's task, a flow run, an image, the agent's temporary folder. The key is the human's
`OPENROUTER_API_KEY`, allowed for this trial under $1; the cost is the key's `usage` from
`/api/v1/key` before and after each run, the key never printed. The numbers are of commit
e7af23f5 (main at 0.46.1rc1 plus this change's design), the runs one after another, then the three
cells at once as in CI (each with its own `TMPDIR`, started 20 seconds apart).

## Hosts

From `https://openrouter.ai/api/v1/models/<model>/endpoints` on 2026-11-11; every one declares
tools, and the model takes images.

| Model | Hosts | Price per million tokens (in / out) |
|---|---|---|
| `qwen/qwen3.7-flash` | Alibaba | $0.03 / $0.13 |
| `openai/gpt-5-nano` | OpenAI, Azure | $0.05 / $0.40 |
| `openai/gpt-5.4-nano` | OpenAI, Azure | $0.20 / $1.25 |
| `anthropic/claude-haiku-5.5` | Anthropic, Amazon Bedrock, Azure, Google, Claude Platform on AWS | $0.10 / $0.50 |

## Results

| CLI | Model | Runs passed | Tests passed | Cost of a run |
|---|---|---|---|---|
| Codex | `openai/gpt-5-nano` | 0 of 2 | 1 of 8 | $0.025 to $0.030 |
| Kilo | `openai/gpt-5-nano` | 1 of 3 | 10 of 12 | $0.016 to $0.027 |
| OpenCode | `openai/gpt-5-nano` | 2 of 3 | 11 of 12 | $0.017 to $0.021 |
| Codex | `anthropic/claude-haiku-5.5` | 3 of 3 | 12 of 12 | $0.017 to $0.023 |
| Kilo | `anthropic/claude-haiku-5.5` | 3 of 3 | 12 of 12 | $0.040 to $0.046 |
| OpenCode | `anthropic/claude-haiku-5.5` | 3 of 3 | 12 of 12 | $0.026 to $0.027 |

The three cells at once on `anthropic/claude-haiku-5.5`: each 4 of 4, in 113 seconds, $0.086.
A haiku run takes about a minute per CLI (Codex 51 to 57 seconds, OpenCode 63 to 70, Kilo 79 to
82); a nano run took 3 to 16 minutes, most of it the tests' waits. No run had a 429.

With the Claude Code cell's $0.04 (LAD-231's report), a run of the four cells costs about $0.13,
against $0.07 on qwen: some 75 runs a month within the key's $10.

## How the trial went

The design's order was `openai/gpt-5-nano` first, `openai/gpt-5.4-nano` for a CLI that failed.
Codex and Kilo each had a second red on nano, so both went to 5.4-nano. While Codex's first run on
5.4-nano was going, the human decided (#6017) to try `anthropic/claude-haiku-5.5` on all three
instead: five hosts, green in every run of the Claude Code cell; for Codex, `openai/gpt-5.4-nano`
and then `openai/gpt-5-mini` if haiku failed. The runs on nano stopped there (OpenCode's rerun of
its red run was not made), and the 5.4-nano run was stopped before its end: it is not counted.
Codex passed on haiku, so no OpenAI model was needed.

## Failures and their causes

All on `openai/gpt-5-nano`, all the model's; none a host's.

- **Codex, 7 of 8 tests: the model's.** The worker never called LADO's tools: it called Codex's
  own `read_mcp_resource` again and again (`uri must be provided`, `missing field server`), then
  ended its turn asking for help, and the test timed out. The one test that passed (run 2, the
  worker's task) shows the tools were there. LAD-231 had seen the same model once not idle within
  60 seconds on Codex.
- **Kilo, the worker's task, runs 2 and 3: the model's.** Told `write_artifact(name="report",
  file="report.md")`, it passed text instead of the file: the artifact was `REPORT` as
  `text/plain` in run 2, the string `report.md` in run 3.
- **OpenCode, the worker's task, run 2: the model's.** The same call, with a text of its own
  (`report.md added on branch lado/live/w1 ... REPORT`) as the content.

A model that answers a tool call wrongly makes a cell red at random; the rule for a cell's model
(docs/testing.md) now asks for tool calls that held in a trial before the price.

## Cost

$0.56 in all, read from the key's usage ($1.758 before, $2.317 after): $0.175 on `gpt-5-nano`,
$0.030 on the stopped `gpt-5.4-nano` run, $0.268 on the nine haiku runs one after another, $0.086
on the parallel one. Between the stop and the first haiku run the usage rose by $0.002 with no run
of the trial going; it is in the total.
