# The LADO MCP server answers its handshake and lists before the SDK loads: Design

Task: LAD-294. Change: `openspec/changes/mcp-server-fast-start/` (proposal, delta
`mcp-server-start`, `design.md` D1-D10). Approach chosen by the human: #7865.

## Problem and root cause

An agent's first turn waits for its CLI to list the LADO MCP server's tools
(`hooks._wait_for_mcp`, or Codex's own wait for a `required` server). The server spends
almost all of that time importing the MCP SDK, whose package `__init__` loads the client,
the types of two protocol versions, the HTTP transports and pydantic whatever part of it
is imported. LADO cannot change the SDK's import graph; it can stop waiting for it before
the first answers.

## Measurements (2026-11-23, this container, mcp 2.3.0, Python of `.venv`, no load)

From `Popen` of `python -m lado.cli mcp` to the answer line, 10 starts, median:

| Answer | Time |
|---|---|
| `initialize` | 0.383 s |
| `tools/list` | 0.383 s |

`python -X importtime -c "import lado.mcp_server"` (warm): 0.33 s in all; `mcp.server.mcpserver`
0.29 s, of it `mcp.client` 0.13 s, `mcp_types` 0.09 s (two protocol versions 0.03 s each),
`mcp.types` 0.06 s, starlette/uvicorn/sse 0.04 s; `lado.kits` 0.02 s. A stub for
`mcp/__init__` brings `mcp.server.mcpserver` to 0.28 s only. `python -c "import lado.cli"`
0.08 s; `python -c "import lado.state"` 0.03 s; `importlib.metadata.version` twice 0.03 s.

Expected after: 0.05-0.07 s to `tools/list` on a warm cache (Python, `lado.state`, the
key, one file read, one database write for `mcp_ready`); a cold start as before plus the
cache write.

The probe for the pull request's before/after numbers; it is not committed, it lives here
so that the developer and the reviewer measure the same way:

```python
import json, os, subprocess, sys, time, tempfile, statistics
def once(home):
    env = {**os.environ, "LADO_SESSION": "s", "LADO_AGENT": "a", "LADO_HOME": home}
    env.pop("LADO_INSTANCE", None)
    t0 = time.perf_counter()
    p = subprocess.Popen(sys.argv[2:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)
    def send(m): p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "b", "version": "1"}}})
    p.stdout.readline(); t1 = time.perf_counter()
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    p.stdout.readline(); t2 = time.perf_counter()
    p.kill(); p.wait()
    return t1 - t0, t2 - t0
home = tempfile.mkdtemp()
once(home)  # the cold start, which writes the cache
r = [once(home) for _ in range(int(sys.argv[1]))]
print("initialize median %.3f s, tools/list median %.3f s" % (statistics.median(x[0] for x in r), statistics.median(x[1] for x in r)))
```

Run as `.venv/bin/python probe.py 10 .venv/bin/python -m lado.cli mcp` before the change
and `.venv/bin/python probe.py 10 .venv/bin/python -c "<interpreter.LOADER>" lado.mcp_stdio`
after it (the command an agent's config gets), and once more after with `lado.cli mcp`.

## The message flow

Warm start (cache hit), a Claude Code-like client:

1. Process start: claim fds 0/1 (D1), start the reader thread, the main thread imports
   `lado.mcp_server` (and with it the SDK).
2. Client `initialize` (id 1): the reader reads the agent's row, computes the key, reads
   the file, answers with the cached result for the requested version and this agent's
   `instructions`, remembers id 1 as answered, queues the line.
3. Client `notifications/initialized`: queued.
4. Client `tools/list` (id 2): answered from the cache; `mcp_ready` recorded (D8); not
   queued.
5. The SDK is up: the main thread builds the server with instance `""`, opens the pipes,
   starts `stdio_server(stdin, stdout)` and the server's run. The reader writes the queue
   (the `initialize`, the `initialized`) into the SDK's input pipe, then the check
   requests `lado-check-1` (`tools/list`) …, then every later line as it comes.
6. The writer drops the SDK's answer to id 1 after comparing it with the cached one, takes
   the answers to `lado-check-*` off the wire and compares them (D5); every other line
   goes to the client.

Cold start (miss): steps 2 and 4 queue instead of answering; the SDK answers both; the
writer stores them and writes the file after the `tools/list` answer (D4). A list
request with a cursor is always queued for the SDK.

## Tests per requirement

| Requirement | Test | Layer |
|---|---|---|
| answers its handshake and lists from a cache | `tests/test_mcp_stdio.py`: warm answers before a blocked loader returns; cold writes the file; the key changes with the code, each package's `__init__` stat and the tool set; per-version `initialize`; a cursor queued; a first non-`initialize` message disables the front; an invalid file is a miss; pruning to 20 | unit |
| same | `tests/integration/test_mcp_start.py` (new): a cold then a warm real `lado mcp` in one `LADO_HOME`: `initialize` equal but `instructions`, `tools/list` equal, a `list_agents` call works on both, the cache file exists after the cold one; a worker after the supervisor gets the worker's tools | integration |
| SDK serves every other request | unit: queue order, replayed `initialize`, one answer per id, a tool call queued before the load answered after it, the private `_lowlevel_server` present; a failing loader exits non-zero with the traceback | unit |
| same | the whole fake-agent suite (every tool through `LadoMcp`), `test_fake_agent.py::test_a_tool_call_fails_when_the_mcp_server_cannot_start` | integration (regression run, CI) |
| cached answer contradicted is journaled | unit: a cache whose tools differ: the file is replaced, `telemetry.record` called once with `mcp:cache`, the client gets nothing extra | unit |
| mcp_ready once | unit: front records once, the SDK's `list_tools` records nothing after it; `tests/integration/test_agents.py::test_first_turn_waits_for_the_one_lado_mcp_server_of_the_launch` with a warm cache (the supervisor's start warms it for nothing: run the test as it is, and a second agent of the same tool set) | unit, integration |

`tool_set`'s `SUPERVISOR` equals `runtime.SUPERVISOR`: unit. `providers.base`'s entry
runs `lado.mcp_stdio`: the providers' existing config tests, updated.

Regression run: `make test`, `uv run pytest -m integration -n auto` over the changed and
new files, then CI's full integration suite (every agent of every test starts `lado mcp`).

## Docs

- `docs/design/agents.md`: the readiness paragraph (`mcp_ready`): who records it now, the
  cache and its check, one sentence on the newer protocol era.
- `docs/design/modules.md`: `mcp_stdio.py` (front, cache, pipes), `mcp_server.py` (no
  longer the process entry).
- AGENTS.md's Layout: `mcp_stdio.py` next to `mcp_server.py`, one line.
- `docs/research/test-audit.md`: the reserve it names is taken by LAD-294.
- CHANGELOG under the next patch's `(unreleased)` heading: agents start about 0.3 s sooner.

## Manual check

1. Run the probe before and after (above); put both medians in the pull request.
2. `uv run lado start <repo>` with `LADO_HOME` and `LADO_TMUX_SOCKET` of your own, Claude
   Code and Codex agents: tools listed, a `send_message` works, `hooks.log` has no "listed
   no tools", `ls $LADO_HOME/mcp-cache` shows the files.
