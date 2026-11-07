# The trial of the live tests on OpenRouter

Task: LAD-231. Change: `openspec/changes/cloud-live-tests/`. Date: 2026-11-07.

All four providers run on OpenRouter, directly, on cheap models. No bridge and no Anthropic or
OpenAI key is needed. A full run of the four costs about $0.07, and the whole trial cost $0.30.

Setup: `LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1`, `LADO_LIVE_IMAGE=1`, the CLIs at the pins
of `scripts/smoke_ci.py` (Claude Code 2.1.295, Codex 0.162.0, OpenCode 1.18.35, Kilo 7.8.8). The
key is the human's `OPENROUTER_API_KEY`, as they allowed at the design's gate, in place of the
design's separate trial key. Cost is the key's usage before and after each step. The numbers below
are of commit 5b6e5e9a, the three runs one after the other.

## Results

Three scenarios per provider: a worker's task, a flow run, an image.

| Provider | Model | Runs passed | Tests passed | Cost of a run |
|---|---|---|---|---|
| Claude Code | `anthropic/claude-haiku-5.5` | 3 of 3 | 9 of 9 | $0.04 |
| Codex | `qwen/qwen3.7-flash` | 3 of 3 | 9 of 9 | $0.01 to $0.025 |
| Kilo | `qwen/qwen3.7-flash` | 3 of 3 | 9 of 9 | $0.004 to $0.013 |
| OpenCode | `qwen/qwen3.7-flash` | 2 of 3 | 8 of 9 | $0.007 |

A run takes 1 to 2 minutes per provider. A round of four cost $0.064 to $0.085, so about 10 runs
a month are under $1, against the design's estimate of $2 to $5, and well within the $10 limit.
These models go in `live.yml`'s matrix. `openai/gpt-5-nano` was tried on Codex once: its
supervisor was not idle within 60 seconds; it was not looked into, as the cheaper model passed.

## What it answers

- **Codex reaches OpenRouter directly, its MCP tools included.** The `namespace` error of
  openai/codex #32318 and #26234 did not show on `qwen/qwen3.7-flash`.
- **Claude Code runs on OpenRouter** with the variables of design.md D15: a real turn with LADO's
  tools, each answer in its transcripts on `anthropic/claude-haiku-5.5`.

## Failures and their causes

- **OpenCode, the image test, run 2: the model's.** It read the image and said `red`, right, as
  plain text instead of calling `send_message`, so the test timed out. LADO did its part. Such a
  flake would make a cell red now and then; a rerun of the failed cell is the rule.
- **Claude Code's image test, first run: the account.** OpenRouter answered 402: the account held
  no credits, though the key's limit was $5. A key's limit is a ceiling, not money. The test
  failed at its 180-second wait and did not hang. The human added credits.
- **Codex's worker test, twice: the test.** It expected the line sent while busy only in the
  turn-end hook's output, though since 0.45.0 it goes in a LADO tool's result; and it wrote to w1
  while the passive supervisor had left the report's body unread, which LADO refuses. Both fixed
  in `tests/live/test_live.py`.
- **Claude Code's worker test, first run: this change's check.** `check_models` asked an answer of
  a lead that had no turn yet. Fixed.
