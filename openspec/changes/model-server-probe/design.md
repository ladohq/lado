## Context

The epic branch has a session's model (`session-model`): a power table of `{cli, model}`
rows in `sessions.power`, checked by `model_check.py` against the CLI's own list, which
`providers/base.py` reads with a 15 s limit; a list that cannot be read is "no list" with
why (`base.ModelList`). LADO makes HTTP requests only with `urllib` (`update.py`,
`telemetry.py`; the latter guards DNS, which urllib's timeout does not cover). LADO knows
it runs in its image by `LADO_CONTAINER` (`update.in_container()`); the image's compose
file maps `host.docker.internal` to the host. A secret is read without echo or from stdin
by `cli._secret_value` (`lado project set --secret`).

The human's answers: questions #2541 (the command, the address without a scheme, the
output with the CLIs that suit and those that do not, no API method), #2548 and #2551 (the
key belongs to the server; the plan as drafted).

## Goals / Non-Goals

Goals: from an address and an optional key, the server's type, models and suitable CLIs,
proven by requests that generate nothing; clear failures; no key anywhere but the
requests' headers. Non-goals: the proposal's Out of scope.

## Decisions

### D1. Six requests, each proving one thing

The address is normalised (D2) to a root `R` and its API base `R/v1`. Requests:

| # | Request | Proves |
|---|---|---|
| 1 | `GET R/v1/models` | the model list; its shape (D4) |
| 2 | `GET R/api/version` | Ollama: a JSON object with a string `version` |
| 3 | `GET R/api/v0/models` | LM Studio: a JSON object with a list `data` |
| 4 | `POST R/v1/chat/completions`, body `{}` | chat completions |
| 5 | `POST R/v1/responses`, body `{}` | the Responses API |
| 6 | `POST R/v1/messages`, body `{}` | the Anthropic Messages API |
| 7 | `POST R/v1/lado-no-such-api`, body `{}` | the control: a path no server has |

A POST proves its API when it answers 400 or 422 with a JSON body (an object): the server
parsed the request and refused it for want of a model and input. 404, 405 or any other
answer is "no". The control (human, rejection at `design_ok`): a gateway that answers 400
with JSON to every path would otherwise prove all three APIs. When request 7 answers as an
API would (400 or 422 with JSON), no API counts as proven: requests 4–6 prove nothing on
that server, and the output says why (D9). `{}` holds nothing to generate, so no request costs anything or needs a
model. Every request carries `Content-Type: application/json` (POSTs),
`anthropic-version: 2023-06-01` and `User-Agent: lado/<version>`, and with a key the
headers of D7. At most one request per check per address (seven); no other path, port or host.

### D2. The address

Spaces around it are dropped. Without `://` it gets `http://` and the output's first line
says `(added http://)`. Only `http` and `https`; a user or password in it (it would be
printed), a query or a fragment are refused (exit 2) with one line each. Trailing `/` are
dropped, then one trailing `/v1`: the rest is `R`, kept with its path, so a gateway at
`https://gw.example/llm` probes `https://gw.example/llm/v1/models`. The output names `R`.

### D3. Time: 5 s per request, at most about 10 s per address

`TIMEOUT = 5` seconds per request, covering DNS: each request runs in a worker thread
that is waited for at most `TIMEOUT` (a hung resolver is abandoned, the thread a daemon).
Request 1 goes first, alone: when it gets no HTTP answer (refused, unknown host, timeout,
reset), the probe stops with "does not answer" (D8) and sends nothing more. Otherwise
requests 2–7 go at once, in six threads, under the same limit. Within the epic's
ceiling of 10 s per address.

### D4. The type: shown, never used for the rule

In this order: request 2 proves Ollama → `Ollama`; request 3 proves LM Studio →
`LM Studio`; request 1's body has items with `"type": "model"` or a key `has_more` →
`Anthropic-compatible`; request 1's body is an object with a list `data` →
`OpenAI-compatible`; else an API proven by 6 → `Anthropic-compatible`, by 4 or 5 →
`OpenAI-compatible` (never after a control answered as an API, D1). None of these: an unknown server (D8). The CLIs never follow from the
type (proposal, option B).

### D5. The rule: each provider declares the API it speaks

`providers/base.py` gets `server_api: str = ""` on `Provider` and the constants
`CHAT_COMPLETIONS = "chat completions"`, `RESPONSES = "Responses API"`,
`ANTHROPIC_MESSAGES = "Anthropic Messages API"`. OpenCode and Kilo (the OpenCode family)
declare `CHAT_COMPLETIONS`, Codex `RESPONSES`, Claude Code `ANTHROPIC_MESSAGES`; a
provider with `""` (a test's stand-in) is left out of the rule. `model_servers` maps
requests 4–6 to those constants and names every registered provider (`providers.names()`)
whose API was proven by its `Provider.title`, grouped by API in the order chat
completions, Responses API, Anthropic Messages API and within a group in the registry's
order; each other one with `no <API>`. One source of truth, no provider name above `providers/`.

### D6. No redirect followed

The opener has a redirect handler that follows nothing: a 3xx is an answer that proves
nothing, and the unknown server's message names it (`301 to <location>` with the
location's query dropped). urllib's own handler would send the key's headers on to
whatever host the server names.

### D7. The key

`--key` takes no value: `nargs="?"` with a sentinel `const`, so `--key abc` or
`--key=abc` is refused with `a server's key is never given on the command line (ps and the
shell's history keep it); run lado model-server probe <address> --key and type it, or pipe
it in`, which never repeats the value (argparse's "unrecognized arguments" would). The key
is read as `cli._secret_value` reads a secret: `getpass` (`Key of the server (not
shown): `) on a terminal, else the whole of stdin with one line break dropped; empty is
refused (`the key is empty`). It is sent as `Authorization: Bearer <key>` and
`x-api-key: <key>` on all seven requests (one host, D6) and kept nowhere: no file, no
`lado.db`, no log. Messages are built only from the status, the path and the server's
error text cut to 200 characters; an exception's text is never built from a request's
headers, so the error journal cannot receive the key either.

### D8. The messages

One line each, on stderr, exit 1 (`R` is the normalised address):

- `<R> does not answer (connection refused | unknown host | no answer in 5 s | <reason>)`
- in the container, for `localhost`, `127.0.0.0/8` or `::1`, a second line:
  `LADO runs in a container, where localhost is the container itself; a server on your
  machine: lado model-server probe <scheme>://host.docker.internal:<port><path> (not
  tried)`, with the port given or the scheme's default
- `<R>: TLS failed (<reason>); a company's CA goes in the file SSL_CERT_FILE names`
- any 401 or 403 among the answers, without a key: `<R> asks for a key (<status>): run
  lado model-server probe <R> --key`; with one: `<R> refused the key (<status>)`
- `unknown server: <R> answered, but not as an OpenAI-compatible, Anthropic-compatible,
  Ollama or LM Studio server (GET /v1/models: <status or 301 to …>)`; when the control
  answered as an API, the parenthesis ends `; it answers <status> to any POST, so its APIs
  cannot be told`

### D9. The output and the result

On success (exit 0), stdout:

```
http://192.168.1.10:11434 (added http://)
type: Ollama
models: llama3.1:8b, qwen2.5-coder:7b
CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)
not: Claude Code (no Anthropic Messages API)
```

`models: none` for an empty list, `models: no list (GET /v1/models: <status or reason>)`
when request 1 gave no list (the `model_check` rule: a failed list is no list, not an
error); `CLIs: none` when no API was proven; no `not:` line when every CLI suits. When the
control answered as an API on a server whose type is known, the line `APIs: cannot be
told: <R> answers <status> to any POST` comes before `CLIs: none`, exit 0. The
result is `model_servers.Probe` (frozen): `address`, `added_scheme`, `kind`,
`apis: frozenset[str]`, `models: tuple[str, ...] | None`, `models_why`, and the method
`clis()` (`suits`, `not_suits` from D5). Failures raise `model_servers.ProbeError(text,
hint)`; `cli.py` prints. A session's server will sit beside its power table with the same
fields.

### D10. Proxies and certificates as elsewhere in LADO

urllib's defaults: `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` from the environment, the
system's certificates and `SSL_CERT_FILE`. Answers are read up to 4 MiB (a large
gateway's model list); more is a list LADO does not read (`models: no list (the answer
is larger than 4 MiB)`).

## Risks / Trade-offs

- A server that answers an empty body with something other than 400/422 (200 with an
  error, 500) is named as lacking that API: the CLI is named under `not:`, which is the
  safe side; the human checks by hand (the epic's decision D7: a real server by hand).
- LM Studio's REST API `/api/v0` is marked beta by LM Studio; if it moves, LM Studio is
  shown as `OpenAI-compatible` and its CLIs are unchanged (D4, D5).
- Seven requests reach the server's log, among them four refused POSTs.
