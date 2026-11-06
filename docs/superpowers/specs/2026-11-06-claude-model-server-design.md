# Claude Code on a model server: design

A Claude agent whose model is on a server runs there, with tools, MCP and hooks, and nothing of the
human's Claude credentials goes with it. The rules are in `openspec/changes/claude-model-server/`;
this document holds what was seen on the real CLI and why the pieces fit.

## The problem

Claude Code has one endpoint per process. A saved Claude model on a server is refused at the start,
while `lado model add --cli claude --server …` and a server's `CLIs` promise it. The obvious fix, one
variable in the agent's environment, sends the human's login to the server.

## What was seen

Claude Code 2.1.295, a fake Anthropic server with scripted tool use, a temporary `HOME`, and a proxy
that refused and logged everything else. No request reached a real cloud; the human allowed this at
gate #308.

| Case | Seen |
|---|---|
| A turn with a shell tool and an MCP tool | both ran; `SessionStart`, `PostToolUse` (2), `Stop` hooks ran |
| `ANTHROPIC_AUTH_TOKEN` | `Authorization: Bearer`; no dialog |
| `ANTHROPIC_API_KEY` | `x-api-key` |
| Base URL, no key, a login file | **the login's token went to the server** |
| Base URL, no key, no login | `Not logged in`, nothing sent |
| Token and the human's `ANTHROPIC_API_KEY` | **both went to the server** |
| Token and `CLAUDE_CODE_OAUTH_TOKEN` | the token alone |
| `CLAUDE_CODE_USE_BEDROCK` in the environment | the base URL was left aside |
| `env.ANTHROPIC_BASE_URL` in `~/.claude/settings.json` | **beat the environment; the token went there** |
| `env.ANTHROPIC_API_KEY`, `env.ANTHROPIC_AUTH_TOKEN`, `apiKeyHelper` there | each went to the server |
| The same value in `--settings` | beat the user's settings |
| `apiKeyHelper: printenv VAR` in `--settings`, blanks in its `env` | one key, in `x-api-key` and `Authorization`; the user's helper, key, token and base URL all lost; nothing on disk |
| `/model`, nothing set | Default, Opus, Fable, Sonnet, Haiku, and the model |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` | `GET /v1/models` sent; no row added: only ids with `claude` or `anthropic` are kept |
| `availableModels: [m]`, `ANTHROPIC_DEFAULT_MODEL=m` | Default and `m`; `/model opus`: `Your organization restricts model selection` |
| Alias variables `ANTHROPIC_DEFAULT_OPUS_MODEL=m`, … | five rows of `m` (not taken) |
| A subagent with `model: haiku`, then | `Model "haiku" is restricted`, ran on `m` |
| Enter in `/model` | `"model": "m"` in the user's `settings.json`; `s` is the session only |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS=32000` | `contextWindow` 32000 |
| `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` | no `context_management`, `safeguards`; betas from 10 to 4 |
| The first request | 63 kB, about 16k tokens, 21 tools |
| Outbound with nonessential traffic off | `downloads.claude.ai`, `github.com` tried in the TUI, refused |
| A clean config | the first-run screens, so LADO must record the first run |

One `api.anthropic.com` CONNECT was logged during the run of eight credential cases, refused at the
proxy; which case made it was not told apart, and none appeared in the runs with the final settings.

Real servers, by their documents only, none run here: Ollama from 0.14, LM Studio from 0.4.1 and
LiteLLM's `/v1/messages` each describe Claude Code with `ANTHROPIC_BASE_URL`. Whether `thinking` and
`output_config` pass them, and whether the probe proves their API, the human's manual check tells.

## The shape

```
start_model → check_start (_on_server: API, list, reserved names)
           → agent_servers: one ServerEntry for a CLI of one model per process
           → ClaudeProvider.launch_command
                settings.json: address, blanks, model, apiKeyHelper (variable's name only)
                Launch.env:    LADO_MODEL_KEY_<ID>=<key>, LADO_MODEL_SERVER=<id>
           → needs_login(env) false: no wait, first run recorded
```

Everything Claude-specific stays in `providers/claude.py`. `runtime.py` learns one neutral fact, that
a start on a server of a one-model CLI needs no login check, and that holds for Codex next.

## What the human sees

- The launch window, Settings → Models and `lado start` accept the model; their line `takes the whole
  process` is already there, so no screen changes, and no `web/` change or mock-up is needed.
- `/model` in such an agent has two rows. `docs/install.md` says why, what Enter writes, and that a
  worker on another model is the way to another model.
- An OpenCode or Kilo agent with a silent TUI no longer shows `Open its terminal` for a few seconds.

## Roads not taken

A private `CLAUDE_CONFIG_DIR`: clean, but the agent would lose the human's `CLAUDE.md`, plugins, skills
and hooks (#3880). The environment alone: the leaks of the table. Alias variables: five equal rows.
