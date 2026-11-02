# What a model server is: design

Task: LAD-177 (epic LAD-154). Change: `openspec/changes/model-server-probe/` (proposal, the
delta of the new capability `model-servers`, design.md D1-D10). No mockup: the change has
no screen.

## What the human sees

**`lado model-server probe <address>`** asks a model server what it is and prints:

```
$ lado model-server probe 192.168.1.10:11434
http://192.168.1.10:11434 (added http://)
type: Ollama
models: llama3.1:8b, qwen2.5-coder:7b
CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)
not: Claude Code (no Anthropic Messages API)
```

and exits 0. A server behind a key:
`printf '%s' "$KEY" | lado model-server probe https://gw.example/llm --key`, or `--key` on a
terminal, which asks `Key of the server (not shown): `. The key is never an argument, and
is kept nowhere.

Failures, one line on stderr, exit 1:

```
http://localhost:11434 does not answer (connection refused)
LADO runs in a container, where localhost is the container itself; a server on your machine: lado model-server probe http://host.docker.internal:11434 (not tried)
```

(the second line only in LADO's container), `https://gw.example/llm asks for a key (401):
run lado model-server probe https://gw.example/llm --key`, `https://gw.example/llm
refused the key (401)`, `unknown server: http://h:8080 answered, but not as an
OpenAI-compatible, Anthropic-compatible, Ollama or LM Studio server (GET /v1/models:
404)`, `https://gw.example/llm: TLS failed (<why>); a company's CA goes in the file
SSL_CERT_FILE names`. A malformed address (another scheme, a password, a query) exits 2.

Without the command, nothing in LADO changes: no session, agent, page or API uses the
probe yet.

## Facts the design rests on

- The servers' endpoints and shapes, and which CLI speaks which API: the proposal, Why.
- An empty JSON body has nothing to generate; every server named answers it with 400 or
  422 and a JSON error when it has the API, 404 or 405 when it does not.
- `session-model`'s rule that a CLI's list is local and never fetched from a model API
  is about a CLI's list; a server's list is the server's own, asked by the human's
  command, so the two do not contradict.
- LADO's secrets are a layer of every agent's environment and accept only the CLIs'
  login variables; a project's secrets belong to one project. Hence the key belongs to
  the server (human, #2548).
- `update.in_container()` is LADO's one test of its container.

## Architecture

`src/lado/model_servers.py`, standard library only:

- `address(text) -> (root, added_scheme)` or `ValueError` (D2).
- `probe(text, key=None) -> Probe` or `ProbeError(text, hint)`: request 1, then 2–6 in
  five threads, each under `TIMEOUT = 5` (D1, D3); an opener with the environment's proxies (D10) and
  with a redirect handler that follows nothing (D6, D10).
- `Probe` (frozen): `address`, `added_scheme`, `kind`, `apis`, `models`, `models_why`;
  `clis()` gives the providers that suit and those that do not, from
  `Provider.server_api` (D5).
- `lines(probe) -> list[str]`: the output of D9, the one place of its text.

`providers/base.py`: `server_api` and the three constants; each provider's value.

`cli.py`: `model-server` with the subcommand `probe`, `address` and `--key` (D7); the key
read by the same reader as `lado project set --secret` (shared, not copied), `--key`'s
value refused before anything is read or sent.

## Options and their cost, against the roadmap

- Probe by APIs, rule by the providers' declarations (taken): the coming steps (a session
  on a server through OpenCode and Kilo; saved servers; Claude Code and Codex on a server)
  read `Probe` and `clis()` as they are; a new CLI declares its API in its provider.
- A table per type: stale with each server release, nothing for gateways.
- A generation per API: costs money, needs a model.

Design principles: neutral core (no provider name above `providers/`; the rule works for
all four CLIs), one source of truth (the provider declares its API), no silent drops
(every CLI that does not suit is named with why; no silent rewrite of an address), only
what is used (no API method, no store, no `--json` until a step reads them).

## Tests by layer

- Unit, `tests/test_model_servers.py`, against `tests/fake_model_server.py` in-process
  (real HTTP on `127.0.0.1:0`): each yes and no of the rule, the type of each profile, the
  address forms, the 5 s limit on a hanging server, no redirect followed, at most one
  request per check, the key's headers, the messages of D8, the container's hint with
  `LADO_CONTAINER=1` and without it.
- Unit, `tests/test_cli_model_server.py`: the output, exit codes, the key from stdin, the
  key refused on the command line without being echoed, `lado model-server` alone.
- Integration, `tests/integration/test_model_server_probe.py` (marker `integration`): the
  real command in its own process against the fake server in its own process; a canary
  key appears in no output, file of `LADO_HOME` or `lado.db`, and reaches the server.
- No UI, smoke or live test: no screen; the human checks a real server by hand (epic D7),
  steps in the pull request.
