# An external model provider by address and key: design

Task: LAD-220. Change: `openspec/changes/external-model-provider/`. Technical decisions D1-D11 are
in its `design.md`; this document holds the measured facts they rest on and the text of the docs.

## What a real provider answers

From the human's report `lad-220-run` (their key, their machine) and keyless requests by their yes.

| | cloud.ru | OpenRouter |
|---|---|---|
| Address, root | `https://foundation-models.api.cloud.ru/v1`, no path | `https://openrouter.ai/api/v1`, root `…/api` |
| Probe | 1.5-2.5 s; Claude Code, Kilo, OpenCode; not Codex | 1.1-1.8 s; all four CLIs |
| Models | 114 with or without a key | 422 with the key, 458 without |
| Context | `context_length` = `max_model_len`, 112 of 114 (none: two speech models) | `context_length`, all |
| Output | none | `top_provider.max_completion_tokens` |
| Prices in the list | `metadata.prompt_tokens_cost`, `generated_tokens_cost` | `pricing` |
| Tools | `function_calling`: true 98, false 1, absent 15 | `supported_parameters` |
| 401 | `text/plain`, `{"message":"Missing authorization in request"}` | `{"error":{"message":…,"code":401}}` |
| Session on OpenCode | `ls` and `list_agents` ran, 3.5 s, idle | ran, 9.8 s, idle |
| Session on Kilo | ran, 5.7 s, idle | ran, 6.0 s, idle; its TUI shows `$0.01` |

Models: `openai/gpt-oss-120b` on cloud.ru, `openai/gpt-oss-20b` on OpenRouter. The config had no
`limit` and the TUIs no percent: the gap this change closes. Not seen on a real provider: a real 429,
402 or quota, a Claude Code session on OpenRouter, a compaction.

## What a CLI does on a refusal

A fake server, every POST answered alike, `run`/`-p` mode. Requests of one turn, and its length.

| Answer | OpenCode 1.18.35 | Kilo 7.8.8 | Claude Code 2.1.295 |
|---|---|---|---|
| 401 | 2, at once | 1, at once | 11, 179 s, `authentication_failed` |
| 402 | 2, at once | 1, at once | 1, `unknown` |
| 403 | 2, at once | 1, at once | 1, `authentication_failed` |
| 429 | 9, about 70 s | 6, about 71 s | 11, 179 s, `rate_limit` |
| 429 with `Retry-After: 7` | 9, 35 s | 6, 35 s | 11, 194 s |
| 429 of a quota | as 429 | as 429 | as 429 |
| 500, `CLAUDE_CODE_MAX_RETRIES=2` | | | 3, `server_error` |
| 200 and a cut stream | | | 2, `unknown` |

`session.error` of OpenCode and Kilo holds `name: APIError` and `data` with `message`, `statusCode`,
`isRetryable`, `responseBody`, `responseHeaders`, `metadata.url`. `StopFailure` of Claude Code holds
`error` and `last_assistant_message`, no `error_details`: `API Error: 402 Insufficient credits`,
`Failed to authenticate. API Error: 401 …`, `API Error: Request rejected (429) · …`.

Claude Code's «retries for hours» of the earlier check (2.1.319, LM Studio) was not reproduced here;
the human's check covers it.

## The late answer (F2)

Direct from the host both providers answered well under 5 s. The two false refusals of the earlier
check came through a logging proxy, its first TLS connection slow, and from LM Studio just after a
load. The defect is in the code all the same: no answer and "not this API" are one branch.

## `docs/install.md`: what the new section says

Under the agents' variables, `#### A cloud provider`, linked from "What to expect of a small model":

- Add it as any server: `lado model-server add <name> <address> --key`, the address with its path:
  `https://foundation-models.api.cloud.ru/v1`, `https://openrouter.ai/api/v1`. Checked on both, on
  OpenCode and Kilo; Claude Code on cloud.ru's Anthropic API.
- LADO reads the context from the provider's list, and limits answers to what it reports, or 32K
  tokens on a context of 128K or more. A provider that lists no context is warned about at the start.
- **A large context costs money.** The agent compacts only near the model's context: on a 1M model
  late requests carry up to a million tokens. Prefer a model of 128K-256K. A limit of your own does
  not exist yet.
- **What it costs.** LADO does not show what a session spent. Look in the provider's console (cloud.ru)
  or Activity (OpenRouter); Kilo's TUI shows OpenRouter's cost; Claude Code has `/cost`, its own count,
  not compared with a bill.
- **Refusals.** 401, 402, 403 and 429 end the agent's turn, after about 70 s of the CLI's own repeats
  on a 429, and the chat says why. Nothing repeats by itself after that: a run waits for you or the
  lead, also at night.
- **Claude Code with your plugins.** Your own plugins, rules and `CLAUDE.md` count: at 65536 they can
  fill the context in the first turn. Take a model of 131072 or more, or fewer plugins. (Also a line in
  "What to expect of a small model".)
- A key the provider repeats in an error is removed from LADO's texts, not from the CLI's terminal.

## Manual check (goes into the pull request from the start)

Branch `feature/lad-220-external-model-provider`, in a folder of your own; `env | grep LADO_` and
`unset`; `export LADO_HOME=/tmp/lad-220-home LADO_TMUX_SOCKET=lado-lad-220`; `make web`.

1. `probe`, `model-server add`, `model add` on cloud.ru and OpenRouter, on all three CLIs.
2. A session on each: a shell tool and `list_agents`; the TUI shows a percent of the context.
3. A wrong key: the chat's line in LADO's words, no key in it.
4. Claude Code logged out, on a server; a worker on a server's model.
5. A long session up to a compaction on each CLI, on a model of 131072.
6. `grep -r <key> "$LADO_HOME" --exclude-dir=model-servers`: nothing.
