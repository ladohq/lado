Task: LAD-177

## Why

A human who wants LADO's agents on a model served in their network (Ollama, LM Studio,
vLLM, a company's gateway) knows its address and, at most, its key. Which API the server
speaks, which models it holds and which agent CLI can talk to it are things they would
have to find out by hand, with curl and each CLI's documentation. LADO has no notion of a
model server at all: a session's model (`session-model`) is always a model of its CLI's
own list.

What the servers answer, without generating anything:

- An OpenAI-compatible server (vLLM, LiteLLM, a gateway) lists its models at
  `GET /v1/models` as `{"object": "list", "data": [{"id": …}]}` and serves
  `POST /v1/chat/completions`; some also serve `POST /v1/responses`.
- Ollama answers `GET /api/version` with `{"version": …}` and also serves the
  OpenAI-compatible `/v1/models` and `/v1/chat/completions`; recent versions serve
  `/v1/responses` and the Anthropic-compatible `/v1/messages` too.
- LM Studio answers `GET /api/v0/models` (its own REST API) and serves the
  OpenAI-compatible `/v1/…`; recent versions serve `/v1/responses` too.
- An Anthropic-compatible server lists its models at `GET /v1/models` (with the header
  `anthropic-version`) as `{"data": [{"type": "model", "id": …}], "has_more": …}` and serves
  `POST /v1/messages`.
- Each of these refuses a request with an empty JSON body `{}` (no model, no input) with
  400 or 422 and a JSON error, answers 404 or 405 for an API it lacks, and 401 or 403
  for a missing or wrong key. An empty body has nothing to generate: proving an API this
  way costs nothing and needs no model.

Which CLI speaks which API: OpenCode and Kilo take an OpenAI-compatible provider (chat
completions); Codex speaks the Responses API to its model providers; Claude Code speaks
the Anthropic Messages API.

Root cause: LADO has no way to learn what is behind an address, so no later work (a
session on a server, saved servers, a server in the launch window) has anything to build
on.

Options weighed:

- A (taken): one probe of a few requests per address that never generates: the model
  list, the native endpoints of Ollama and LM Studio, and one empty POST per API. The CLIs
  that suit a server follow from the APIs it proved, by each provider's own declaration
  of the API it speaks; the server's type is only shown. A control POST to a path no server has
  tells a gateway that answers 400 to everything from one that has the APIs (human, at
  `design_ok`). Long-term cost: seven small requests per probe; a server that hides an API behind something other than 400/422 for
  an empty body is named as not having it.
- B: decide by type: recognise Ollama, LM Studio, OpenAI or Anthropic and look the CLIs up
  in a table per type. One request fewer, but the table goes stale with every server
  release (Ollama added the Responses and Messages APIs within a year), and an unknown
  gateway gets nothing.
- C: prove an API by generating one token with a model from the list. Proves the most,
  but costs money on a paid gateway, needs a model and is slow on a local server that
  first loads the model.

The server's key (human, question #2548, which revises the epic's decision that a key is a
reference by name to a secret of LADO or of a project): the key belongs to the server. A
reference to LADO's secrets would put it in every agent's environment, and a project's
secret does not fit a server shared by all projects. In this change the key is asked for
the probe alone and kept nowhere.

## What Changes

- New command `lado model-server probe <address> [--key]`. It names:
  - the server's type: Ollama, LM Studio, OpenAI-compatible, Anthropic-compatible;
  - its models;
  - the agent CLIs that can use it, and each CLI that cannot, with why.

  Exit 0 for a server it recognised, 1 otherwise. `lado model-server` alone prints its help.
- The address may come without a scheme (`http://` is added and the output says so) and
  with or without a trailing `/v1`.
- Clear one-line messages for an address that does not answer, a server that asks for a
  key, a key it refused, an unknown server, a TLS failure.
- A server that answers every POST alike proves no API: a control request to a path no
  server has tells it apart.
- In LADO's container, a `localhost` address that does not answer gets a loud hint naming
  `http://host.docker.internal:<port>`, which LADO does not try itself.
- `--key` asks for the key without echo, or reads it from stdin; never from the command
  line. Its value appears in no output, log, error journal or `lado.db`.
- Each provider declares the server API its CLI speaks; the compatibility rule reads
  those declarations.

## Scope

- `src/lado/model_servers.py` (the probe and the rule), the providers' declaration of the
  API each speaks, `lado model-server probe` in `cli.py`.
- Tests: unit tests against in-process fake servers, CLI unit tests, an integration test
  of the real command against a fake server in its own process.
- Docs: `docs/cli.md`, `docs/design/modules.md`, AGENTS.md's line of the module, CHANGELOG,
  the new capability `model-servers`.

## Out of scope

- A session on a model server, the server and its key in an agent's config or
  environment, the check before a start: the next work, a session on a server through
  OpenCode and Kilo; nothing uses the probe's result yet.
- A server field in the launch window, and an API method for it: that same next work
  builds both on the probe (only what is used).
- Saved servers (`add`, `list`, `remove`), where a saved server keeps its key, Settings →
  Models: later work.
- Claude Code and Codex actually running on a server: later work; this change gives only
  the rule of who suits.
- A key from an environment variable, from `LADO_ENV_DIR`, or by the name of a secret of
  LADO or of a project: the key belongs to the server (human, question #2548).
- Trying `host.docker.internal` or any other address or port by itself, scanning the
  network: never; the human gives the address.
- A generation request to prove an API (option C): it can cost money and needs a model.
- Following redirects: a redirect could carry the key to another host (design.md D6).

## Impact

- Code: new `src/lado/model_servers.py`; `providers/base.py` and each provider (one
  attribute); `cli.py`.
- Tests: `tests/fake_model_server.py` (new helper), `tests/test_model_servers.py`,
  `tests/test_cli_model_server.py`, `tests/integration/test_model_server_probe.py`.
- No schema change, no API or UI change (`make web` not needed).
- Version: the minor (a new CLI command), within the epic's `## 0.45.0 (unreleased)`.
