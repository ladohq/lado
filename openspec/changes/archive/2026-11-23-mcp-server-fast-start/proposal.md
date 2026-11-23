Task: LAD-294

## Why

An agent's first turn waits until its CLI has listed the tools of the launch's LADO MCP
server (`hooks._wait_for_mcp`; Codex waits for its `required` server by itself). Measured
on 2026-11-23 (mcp SDK 2.3.0, no load, 10 starts): 0.38 s from starting `lado mcp` to its
answer to `tools/list`, of which 0.33 s is importing the MCP SDK, 0.08 s LADO's own
modules (`lado.cli` and what the server imports) and 0.01 s Python itself; under load it
doubles. Every agent of every session pays it; in the UI tests it is about a third of a
session's setup.

The cost is the SDK's import graph: importing any part of the `mcp` package runs its
`__init__`, which loads the client (0.13 s, which a server never uses), the types of two
protocol versions, the HTTP transports (starlette, uvicorn, sse) and pydantic. LADO
cannot change that, and skipping the package's `__init__` saves only 0.05 s. The human
chose (#7865) to answer the handshake and the lists before the SDK is loaded, from a
cache the SDK's own answers wrote, and to let the SDK serve everything else as now.

## What Changes

- **A lean front for `lado mcp`.** A new module, `lado.mcp_stdio`, owns the server's stdin
  and stdout. It starts with the standard library and `lado.state` only, and loads the
  SDK and `lado.mcp_server` while it already reads the client's requests.
- **Answers from a cache.** Until the SDK is up, the front answers `initialize` and the
  list requests (`tools/list`, `prompts/list`, `resources/list`,
  `resources/templates/list`) from a cache file in `LADO_HOME`, which holds what the SDK
  answered to the same requests before. The cache is keyed by the server's code, the
  installed SDK and pydantic, and the agent's tool set, so a stale answer cannot be
  served; after the SDK is up the front checks its cached answers against the SDK's and
  journals a difference.
- **The SDK serves the rest.** Every other request waits for the SDK, which gets the
  client's `initialize` replayed and then every message in order; its answer to a request
  the front already answered is dropped. When the cache lacks an answer, the SDK answers
  as today and the front writes the cache from it.
- **`mcp_ready` from the front.** The front records the launch's `mcp_ready` when it
  answers `tools/list` from the cache; otherwise the SDK's `list_tools` does, as now.
- **Agents start the front directly.** An agent's MCP config runs `lado.mcp_stdio` with
  LADO's Python, skipping `lado.cli`'s imports; `lado mcp` stays and runs the same front.
- **Docs and CHANGELOG.** docs/design/agents.md (the readiness paragraph),
  docs/design/modules.md (the new module, `mcp_server.py`), docs/research/test-audit.md
  (the reserve it names is taken), CHANGELOG: agents start about 0.3 s sooner.

## Scope

In: `src/lado/mcp_stdio.py` (new), `src/lado/mcp_server.py`, `src/lado/cli.py`'s `mcp`
command, `src/lado/providers/base.py`'s LADO MCP server entry; unit and integration tests;
the docs above.

## Out of scope

- **A MCP server of LADO's own without the SDK**: the human chose against it (#7865): the
  protocol, argument checks and error texts would become LADO's, and the task forbids
  changing the tools' behaviour.
- **Trimming the SDK's import** (skipping `mcp/__init__`): 0.05 s for a dependency on the
  SDK's package layout; the front makes it unneeded.
- **Answering tool calls before the SDK is up**: they need the SDK's argument checks; a
  model's first call comes seconds after the start, when the SDK is loaded.
- **The newer protocol era without a handshake** (a client whose first request is not
  `initialize`): such a client is served by the SDK alone, as now; no CLI LADO runs uses it
  yet.
- **Starting the SDK ahead of the agent** (a process kept warm by LADO): a daemon per
  session for 0.05 s more.
- **Kits' own MCP servers**: their start is theirs.

## Impact

- Each agent's first turn starts about 0.3 s sooner, after the first start of an agent of
  the same tool set on this LADO version; with every provider, since all of them start
  the LADO MCP server from `providers.base`.
- Protocol, tools and their results unchanged.
- A cache folder `LADO_HOME/mcp-cache/`, a few small JSON files.
- Running agents of a LADO upgraded in place keep their `lado.cli mcp` command, which runs
  the same front.
- Version: patch (no new tool, CLI command or schema change).
