# Codex on a model server: design

Task: LAD-230. Change: `openspec/changes/codex-model-server/`. Technical decisions D1-D12 are in its
`design.md`; this document holds the measured facts they rest on and the text of the docs.

## What real Codex does

Codex CLI 0.162.0 in throwaway homes, `codex exec` and the TUI in tmux.

| Question | Answer | Measured on |
|---|---|---|
| `model_providers` with `wire_api = "responses"`, `env_key` | requests go to `<base_url>/responses`, `Authorization: Bearer <value>` | fake, OpenRouter |
| No `env_key`, `OPENAI_API_KEY` set, a key in `auth.json` | no `Authorization` at all | fake |
| The tools of a request | `exec_command`, `write_stdin`, the MCP resource tools, `request_user_input`, `view_image`, `web_search`, each MCP server one `namespace` | fake, OpenRouter |
| A way out of `namespace` | none: `non_prefixed_mcp_tool_names` only renames it, a catalogue entry does not change it | fake |
| `/model` on a custom provider, no catalogue | OpenAI's eight models | fake, OpenRouter |
| `/model` with `model_catalog_json` | exactly the file's models | fake |
| A catalogue entry | every field is required; `context_window` may be null | fake |
| `codex debug models --bundled` | 23 ms, no network | here |
| A compaction | `model_auto_compact_token_limit` passed: before the next turn an ordinary `POST /v1/responses` with Codex's compaction prompt | fake |
| An output limit | no setting; `max_output_tokens` is not sent | fake |
| `notify`, hooks on a refused turn | neither runs | fake |
| A refused connection | `Reconnecting... waiting for network` without end, no `task_complete` | fake, 70 s |

## What a server's refusal leaves in the journal

A fake server, every POST answered alike. `task_complete.error`:

| Status | Requests, time (`exec`) | `message` | `codex_error_info` |
|---|---|---|---|
| 400 | 1, 0 s | the body as it came | `other` |
| 401, 402, 403, 404, 413, 422 | 6, 6-7 s (401: 12 in the TUI) | `unexpected status <n> <reason>: <text>, url: <url>` | `http_connection_failed.http_status_code` |
| 429 | 6, 6 s, `Retry-After: 1` | `exceeded retry limit, last status: 429 Too Many Requests` | `response_too_many_failed_attempts.http_status_code` |
| 500 | 30, 25 s | `We're currently experiencing high demand, …` | `internal_server_error` |

The journal keeps a server's text as it came, so a server that echoes the key puts it there: LADO does
not write that file, and takes the key out of what it reads. OpenRouter's wrong key:
`unexpected status 401 Unauthorized: Missing Authentication header, url: …, cf-ray: …`, six requests.

## What a real server does

OpenRouter, `https://openrouter.ai/api/v1`, `deepseek/deepseek-v4-flash`, by the human's yes (#4538),
the key from the project's secrets on a command's standard input.

- A direct request with a `namespace` tool: 200, a `function_call` `ping` with `namespace`
  `mcp__probe`, and the response repeats the tool. The same with a plain function.
- `codex exec`: a shell command and an MCP tool ran, the right word came back. 6.7K tokens a request,
  $0.00016.
- A LADO session, an isolated `LADO_HOME`, the provider in a carried user config: `mcp_ready`, the
  session-start and turn hooks, `pwd`, `list_agents`, `send_message`, idle in 14 s. The model showed
  in `lado ls`. `/model` showed OpenAI's list.
- The key was in no file of the temporary home but the project's secret, in no output and no report.

Not checked on a real server: a worker, a compaction, a real 429 or quota, the catalogue. The first
three are the human's manual check; the catalogue goes with it. LM Studio's loss of the tools is the
project's record (`tests/local_models.py`, `docs/testing.md`), not checked again here. LiteLLM keeps
the tools: the live tests' bridge. Ollama and vLLM are not checked.

## The docs

`docs/install.md`, after **Claude Code on a model server**:

> **Codex on a model server.** A Codex model saved on a server with the Responses API runs there, with
> no Codex login: an entry in the agent's own Codex home, your own config untouched, and the key only
> in the agent's environment. Codex sends its MCP tools in a form not every server knows, and an agent
> without them cannot talk to LADO. OpenRouter and LiteLLM keep them. LM Studio's Responses API loses
> them, so LADO does not offer Codex there; put LiteLLM in front of it. Ollama, vLLM and other servers
> are not checked: if a Codex agent works but never answers, this is why.
>
> - The model takes the agent's whole process: `/model` shows that model alone.
> - The agent knows the context the server reports and compacts in time. Codex has no setting for
>   its output: a model that repeats without end stops at your provider's own limit, so set one.
> - A refusal ends the turn in LADO's words within a few seconds of Codex's last repeat. On a 429
>   Codex keeps only the status, not the server's text.
> - A server that goes away in the middle of a turn is no refusal: Codex waits for it without end and
>   goes on when it returns, and the agent stays busy meanwhile.

`docs/install.md`, [A cloud provider](#a-cloud-provider), one more item:

> - A model can fail through a CLI with no error at all: llama-3.3 on cloud.ru's Anthropic API writes
>   its tool calls as text, and gpt-oss after a compaction took the tools for forbidden. LADO cannot
>   see this, so watch the first session on a new model.

`docs/install.md`'s sentence `Codex does not run on a model server yet, and LADO says so before it
starts it` goes, and the list of checked CLIs in the cloud section names Codex on OpenRouter.

CHANGELOG.md, under New:

> - **Run Codex on your own server.** An agent on a saved model of a server with the Responses API runs
>   there, with no Codex login, and a refusal reads in plain words. LM Studio loses Codex's tools, so
>   LADO says so before you save the model.

## The screen

Only `Found` changes: one warning line. Mock-up: the artifact `mockup-lm-studio-note.html`. By the
gate's rule for a text of a column or a window, the developer's screenshots are enough, with no bench.
`docs/design/ui.md` gets the line beside `Found`'s description.
