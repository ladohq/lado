## Context

Every provider starts the LADO MCP server from `providers.base` (`McpServer(lado_command("mcp"),
…)`), that is `python -c <loader> lado.cli mcp`. `lado.cli` imports most of LADO (0.08 s),
then `cli.main` imports `lado.mcp_server`, whose top imports the SDK
(`mcp.server.mcpserver.MCPServer`, 0.33 s), builds the server (`mcp_server.build`: the
tool set by the agent's row: no row, a worker, a read-only agent, the supervisor, a
read-only supervisor) and runs `MCPServer.run("stdio")`. `_Server.list_tools` records
`state.MCP_READY` with `LADO_INSTANCE` once. The session-start hook of a provider with
`hold_first_turn` polls for that event every 0.02 s (`hooks._wait_for_mcp`).

The SDK's `stdio_server(stdin, stdout)` takes explicit anyio text files; without them it
claims fds 0 and 1 (fd 0 to the null device, fd 1 to stderr), so that a child process of
a tool never reads the client's input or writes onto the wire. `MCPServer.run_stdio_async`
is `stdio_server()` plus `self._lowlevel_server.run(read, write,
self._lowlevel_server.create_initialization_options())`. `Server.run` serves two
protocol eras; the client's first request decides which.

Measured by probes outside the repository (design doc, Measurements):
`import lado.state` with Python 0.03 s; `importlib.metadata.version` 0.02 s more.

## Goals / Non-Goals

Goals: `tools/list` answered within about 0.05-0.07 s of the start on a warm cache; the
protocol, the tools and their results unchanged; nothing stale ever served.

Non-goals: an MCP server without the SDK, trimming the SDK, warm processes, kits' MCP
servers (proposal, Out of scope).

## Decisions

### D1. A lean front module, `lado.mcp_stdio`, is the server's process

`mcp_stdio.main()` imports only the standard library and `lado.state` at the top. It
claims fds 0 and 1 as the SDK does (dups them for itself, then fd 0 to `os.devnull`, fd 1
to fd 2) before anything else, starts the reader thread (D3), then imports
`lado.mcp_server` and builds the server in the main thread. `providers.base`'s LADO MCP
server entry becomes `interpreter.run_module("lado.mcp_stdio")`; `lado mcp` (cli) calls
`mcp_stdio.main()` too, so a session started before an upgrade keeps working. Reason: the
start through `lado.cli` alone costs 0.05 s, half of what is left.

Alternatives: keep `lado.cli mcp` (0.05 s lost per start); make `mcp_server.py` lean
with its SDK imports inside `build` (the SDK types of its annotations, `ToolError`,
`Image`, then all go local: a bigger diff of a protocol-sensitive file for nothing).

### D2. The cache: what, where, keyed by what

One JSON file per key under `state.home() / "mcp-cache"`, named
`<key>.json`, key = sha256 of: the bytes of `mcp_server.py` (its tools and docstrings), the
path, size and mtime_ns of the `__init__.py` of the installed `mcp`, `mcp_types` and
`pydantic` packages (found by `importlib.util.find_spec`, without importing them;
`importlib.metadata` costs 0.02 s), and the tool set (D6). The file holds, per requested
protocol version, the `initialize` result without `instructions`, and the results of the
four list methods. Written whole to a temp file and `os.replace`d (agents start in
parallel); the folder keeps its 20 newest files (by mtime), older ones are removed on a
write. An unreadable or invalid file is a miss.

Alternatives: key by LADO's version (a working copy changes code without it); one file for
all keys (parallel writers lose each other's entries).

### D3. Two pipes between the client and the SDK

A reader thread reads the client's lines from the claimed stdin. Before the hand-over it
answers `initialize` and each list request without `params.cursor` whose answer the cache
has, writing to the claimed stdout under a lock, and queues every message (the
`initialize` too) for the SDK. The SDK runs on `stdio_server(stdin, stdout)` with anyio
text files over two `os.pipe()`s: the reader feeds the SDK's input pipe with the queued
lines in order, and from the hand-over on every line as it comes; a writer thread reads
the SDK's output pipe and writes to the claimed stdout, dropping the answer to a request
id the front answered and taking the cache's data from the SDK's answers (D4, D5). The
front answers only until the SDK runs; then the SDK answers everything, lists included.
The server is run as `MCPServer.run_stdio_async` does, with `server._lowlevel_server` (the
SDK's private attribute, pinned by `mcp>=2.2,<3`; a unit test fails when it goes).

Alternatives: one thread answering and an anyio memory stream into the SDK (the SDK's
loop is not running while it is imported); a stdin wrapper the SDK reads directly (the
writer side still needs filtering).

### D4. Cache misses are filled from the SDK's own answers

When the front did not answer a cacheable request, the writer thread stores the SDK's
answer to it (and to `initialize`, keyed by the client's requested version) and writes the
file once the session has answered `tools/list`. A client whose first message is not
`initialize` disables the front and the cache for that process (the newer era, D7).

### D5. The front's answers are checked once the SDK is up

After the hand-over the front sends the SDK, with ids of its own (`lado-check-<n>`), the
list requests it answered from the cache; the writer thread takes those answers off the
wire and compares them, and the SDK's answer to the replayed `initialize`, with the cached
ones. A difference replaces the file's entry and is recorded with
`telemetry.record("mcp:cache", …)`; the client gets no notification (the server says
`listChanged: false`). Reason: no silent drops, should a key miss a cause (e.g. a
patched SDK file with the same size and mtime).

### D6. One function for the tool set and one for the instructions

`mcp_stdio.tool_set(me) -> str` (`none`, `worker`, `read-only`, `supervisor`,
`read-only-supervisor`) is what `mcp_server.build` branches on and what the cache key
takes; `mcp_stdio.instructions(session, agent)` is what `_Server` passes to the SDK and
what the front puts into a cached `initialize`. They live in the SDK-free `mcp_stdio`, and
`mcp_server` imports them from there. `tool_set` compares the agent's name with a
`SUPERVISOR` of its own, which mirrors `runtime.SUPERVISOR` as `artifacts.SUPERVISOR`
does (importing `lado.runtime` costs the front 0.05 s), with a unit test that they are
equal. The front reads the agent's row with `state.get_agent`; a `state.SchemaError` is
the tool set `none`, as in `build`.

### D7. Protocol eras and versions

Only a first message `initialize` turns the front on; any other first request hands
everything to the SDK at once. The cache holds an `initialize` answer per requested
`protocolVersion`, as the SDK gave it, so the front never negotiates a version itself.

### D8. mcp_ready

The front records `state.MCP_READY` with `LADO_INSTANCE` when it answers the first
`tools/list` from the cache, and then builds the server with the instance `""`, so that
`_Server.list_tools` records nothing more. When the SDK answers the first `tools/list`,
`_Server.list_tools` records it as now. If the SDK finished loading before the front
answered, the event is the SDK's: the front decides under the same lock.

### D9. A failure of the SDK

An import or build error in the main thread ends the process with the traceback on stderr
and a non-zero code, as `lado mcp` does today; the reader thread is a daemon. EOF on stdin
closes the SDK's input pipe, so the SDK ends as it does on EOF now. An unexpected
exception in the reader or writer thread is journaled (`telemetry.record("mcp:stdio", …)`)
and ends the process with a non-zero code: a client never waits on a dead thread.

### D10. Tests by layer

Unit (`tests/test_mcp_stdio.py`): the front with the SDK's load replaced by a loader that
blocks on an event: answers from the cache before the load, queue order, the replayed
`initialize` and the dropped duplicate answer, a cursor or an unknown method queued, a
non-`initialize` first message, the key's parts, the miss written, the check's mismatch
journaled, pruning, `mcp_ready` once. Integration (`tests/integration/`, marker
`integration`): real `lado mcp` processes in a temp `LADO_HOME`: a cold then a warm start
give byte-equal `initialize` (but `instructions`) and `tools/list`, and a tool call works
on both. That a warm start answers before the SDK is loaded is the unit tests' (a
loader that blocks); its time is the design doc's manual check, not a test (a timing
assertion is flaky under load). The existing
`test_first_turn_waits_for_the_one_lado_mcp_server_of_the_launch` and the fake agent's
suite through `LadoMcp` cover the readiness and every tool.

The plan with each task's tests: `docs/superpowers/plans/2026-11-23-mcp-server-fast-start.md`; the
measurements, the message flow and the manual check:
`docs/superpowers/specs/2026-11-23-mcp-server-fast-start-design.md`.
