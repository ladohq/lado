# OpenCode and Kilo on local models: design

Task LAD-211. The rules are in `openspec/changes/local-model-limits/`; this document keeps what was
measured, so nobody has to measure it again.

## Measured

OpenCode 1.18.35, Kilo 7.8.8, fake OpenAI-compatible server; token counts on the fake are characters
divided by 4, those on a real model are from the human's check of PR #219.

| Fact | OpenCode | Kilo |
|---|---|---|
| Request of a bare `run` (fake) | 7.8K | 16.5K |
| Request of LADO's supervisor (fake) | 14.2K, 30 tools | 24K, 44 tools |
| The same on a real model | 21K | 31K |
| `max_tokens` with no limit | 32000 | 32000 |
| With `limit` 24000/2048 | compacts at about 21K | compacts at about 20.5K |
| With no limit, context 24000 | not reached in 8 turns | one turn lost, then compacts |
| With no limit, context 12000 | turns lost, compacts | not run |
| Fixed request above the context | loops without end, 1107 requests in 45 s | ends after 3 attempts |
| The same with a `limit` | loops too | not run |
| `limit` without `output` | refuses the config | not run |
| Server's 500 | retried, error at 74 s | retried, error at 74 s |

First start on a fresh `HOME`, seconds to the first request to the model:

| Outside traffic | OpenCode | With npm's switches | Kilo |
|---|---|---|---|
| Allowed | about 10 | not run | about 5 |
| Refused (closed port) | 78 | 6 | 12 |
| Silent (held connection) | over 150 | 10 | over 195, over 140 with the switches |

OpenCode's wait: any `plugin` entry calls `waitForDependencies`, which waits for the install of
`@opencode-ai/plugin` in each config folder; its fetch of `models.opencode.ai` gives up in 10 s by
itself. Kilo's wait is its own model list from `api.kilo.ai`, 30 and 70 s in its log.

What servers report:

| Server | Where | Field | Seen on |
|---|---|---|---|
| LM Studio | `/api/v0/models` | `loaded_context_length` of `state: loaded`; `max_context_length` is the model's ceiling | a real server |
| LiteLLM | `/v1/models`, `/v1/model/info`, `/model_group/info` | `max_input_tokens`, `max_output_tokens`; floats in `/model_group/info` | a real proxy, latest from PyPI, in front of the fake |
| Ollama | `/api/ps` | `context_length` of a running model | from memory, not checked |

Two entries of LiteLLM on one backend model showed the same numbers, so a gateway's value is what its
config says, right or not.

LADO's tools: a model that calls a tool answers through `send_message` and the message is `replied`; one
that does not answers in its terminal and the chat says so. No change is needed; weak real models are
in the human's check.

## The choice

The options are in the proposal, the decisions in `design.md`. Against the principles:

- Neutral core: limits are read for any server, each provider writes them its own way; the need is a
  provider's field; the reply check is the same for every provider.
- No silent drops: a context LADO cannot read is today's behaviour by design, and `docs/install.md` says so.
- One source of truth: limits are read, not stored, so no copy goes stale.
- Only what is used: no `max_model_len` of vLLM until someone runs one.
- Never touch the user's global config: nothing goes to `~/.config/opencode`, which is why LADO cannot
  place the plugin's dependency there.

## The human's check

Mock-up of the warning: the run artifact `mockup-context-warning.html`. To be seen on real servers, one big model at a
time: see the plan's last section.
