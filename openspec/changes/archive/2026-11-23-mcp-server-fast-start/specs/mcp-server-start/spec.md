## Purpose
How the LADO MCP server of an agent's launch starts: it answers the handshake and the
lists of tools, prompts and resources from a cache of its SDK's own answers while the SDK
loads, so that the agent's first turn waits less, and leaves every other request to the
SDK.

## ADDED Requirements

### Requirement: The LADO MCP server answers its handshake and lists from a cache

Until the MCP SDK is loaded, `lado mcp` SHALL answer `initialize` and the requests
`tools/list`, `prompts/list`, `resources/list` and `resources/templates/list` without a
cursor from a cache in `LADO_HOME` written from the SDK's own answers, keyed by the
server's code, the installed SDK and pydantic, the agent's tool set and the requested
protocol version; with no entry for the key it SHALL let the SDK answer.

#### Scenario: A warm start
- **WHEN** an agent of a tool set starts after another of the same tool set on the same LADO, SDK and protocol version
- **THEN** its `lado mcp` answers `initialize` and `tools/list` before it loads the SDK, with the same content the SDK gave, the instructions naming this agent

#### Scenario: A cold start writes the cache
- **WHEN** the cache has no entry for the key (the first start after an upgrade, or of a new tool set)
- **THEN** the SDK answers as before and the cache holds its answers afterwards

#### Scenario: Another tool set
- **WHEN** a worker starts after only the supervisor has started
- **THEN** the worker's `tools/list` is not answered from the supervisor's entry

#### Scenario: A client without the handshake
- **WHEN** a client's first request is not `initialize`
- **THEN** the SDK answers it and every later request, and nothing is answered from the cache

### Requirement: The SDK serves every other request as before

`lado mcp` SHALL pass every message it does not answer from the cache to the MCP SDK in
the order the client sent it, after replaying the client's `initialize`, and SHALL drop
the SDK's answer to a request it already answered; tools, their results and errors SHALL
be the SDK's as before.

#### Scenario: A tool call right after the list
- **WHEN** a client calls a tool before the SDK has loaded
- **THEN** the call waits for the SDK and gets the same result as without the cache, and the client gets exactly one answer to `initialize`

#### Scenario: The SDK cannot load
- **WHEN** the SDK's import fails after the front answered from the cache
- **THEN** `lado mcp` exits with an error and the traceback on stderr, as without the cache

### Requirement: A cached answer the SDK contradicts is journaled

Once the SDK is up, `lado mcp` SHALL compare each answer it gave from the cache with the
SDK's answer to the same request; on a difference it SHALL replace the cache's entry with
the SDK's answers and record an error in LADO's error journal, and SHALL send the client
nothing more.

#### Scenario: A cache file edited by hand
- **WHEN** the tools of a cache entry differ from the SDK's
- **THEN** after that start the entry holds the SDK's tools and the error journal has one entry `mcp:cache`

### Requirement: mcp_ready is recorded once per launch

`lado mcp` SHALL record the launch's `mcp_ready` event once, when it answers the first
`tools/list` from the cache or, without a cache entry, when the SDK lists the tools.

#### Scenario: The first turn waits for the cached list
- **WHEN** an agent with a `hold_first_turn` provider starts and its tools come from the cache
- **THEN** `mcp_ready` with the launch's instance is recorded before its first turn and only once
