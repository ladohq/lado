# The trial of the live tests on OpenRouter

Task: LAD-231. Change: `openspec/changes/cloud-live-tests/`. Date: 2026-11-07.

**Status: not finished.** It stopped on a 402 at $0.08 spent: the OpenRouter account holds no
credits (`GET /api/v1/credits`: `total_credits` 0), though the key's limit is $5. A key's limit
is a ceiling, not money. The stability runs and Claude Code's full tests wait for credits.

Setup: `LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1`, `LADO_LIVE_IMAGE=1`, the CLIs at the pins
of `scripts/smoke_ci.py` (Claude Code 2.1.295, Codex 0.162.0, OpenCode 1.18.35, Kilo 7.8.8). The
key is the human's `OPENROUTER_API_KEY`, as they allowed at the design's gate, in place of the
design's separate trial key. Cost is the key's usage before and after each step.

## Results

Scenarios: a worker's task (W), a flow run (F), an image (I).

| Provider | Model | Scenarios | Full runs passed | Cost of a full run |
|---|---|---|---|---|
| Codex | `qwen/qwen3.7-flash` | W, F, I | 2 of 2 | $0.005 |
| OpenCode | `qwen/qwen3.7-flash` | W, F, I | 1 of 1 | $0.007 |
| Kilo | `qwen/qwen3.7-flash` | W, F, I | 1 of 1 | $0.010 |
| Claude Code | `anthropic/claude-haiku-5.5` | F passed; W, I failed | 0 of 1 | about $0.03 |
| Codex | `openai/gpt-5-nano` | W failed | 0 of 1 | $0.003 for W |

## What it answers

- **Codex reaches OpenRouter directly, its MCP tools included**, on `qwen/qwen3.7-flash`. The
  `namespace` error of openai/codex #32318 and #26234 did not show. No bridge is needed.
- **Claude Code runs on OpenRouter** with the variables of design.md D15: a reply, and a real MCP
  tool call by hand, its transcript naming only `anthropic/claude-haiku-5.5`.
- A run costs far less than the design's estimate of $0.20 to $0.50.

## Failures and their causes

- Codex W, twice, on the first model: the test, not the route. It expected the line sent while
  busy only in the turn-end hook's output, though since 0.45.0 it goes in a LADO tool's result;
  and it wrote to w1 while the passive supervisor had left the report's body unread, which LADO
  refuses. Both fixed in `tests/live/test_live.py`.
- Claude Code W: `check_models` of this change asked an answer of a lead that had no turn yet.
  Fixed; not yet run again.
- Claude Code I: the account's 402. The test failed at its 180-second wait and did not hang.
- Codex on `openai/gpt-5-nano`: the supervisor was not idle within 60 seconds. Not looked into
  further, as the cheaper model passed.
