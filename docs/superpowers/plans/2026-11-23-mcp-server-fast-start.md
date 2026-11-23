# The LADO MCP server answers its handshake and lists before the SDK loads: Implementation Plan

**Goal:** `lado mcp` answers `initialize` and `tools/list` (and the other three lists)
from a cache the SDK's own answers wrote, while the SDK loads; the SDK serves everything
else as now; an agent's first turn starts about 0.3 s sooner.

**Architecture:** a new SDK-free module `lado.mcp_stdio`: the process's entry, the fds'
claim, a reader thread (answers from the cache, queues the rest), a writer thread (drops
duplicate answers, fills and checks the cache), two pipes into the SDK's
`stdio_server(stdin, stdout)` (D1, D3-D5, D7-D9). `tool_set` and `instructions` move there
and `mcp_server.build` uses them (D6). `providers.base` and `lado mcp` start the front.

**Tech Stack:** Python 3.10+ (standard library: threading, os.pipe, json, hashlib,
importlib.util), the MCP SDK 2.x (`mcp>=2.2,<3`), anyio (through the SDK), pytest
(`-n auto`, `-m integration`).

**Spec:** `openspec/changes/mcp-server-fast-start/` (proposal, delta `mcp-server-start`,
`design.md` D1-D10) and `docs/superpowers/specs/2026-11-23-mcp-server-fast-start-design.md`
(measurements, the probe, the message flow, tests per requirement, docs, manual check).

## Global Constraints

- The protocol, the tools, their results and errors stay the SDK's: the front answers only
  `initialize` and the four list methods without a cursor, only from the cache, only until
  the SDK runs.
- The front's top imports: the standard library and `lado.state` only (a unit test imports
  it in a fresh interpreter and checks `mcp`, `pydantic`, `lado.runtime` are not in
  `sys.modules`).
- Read docs/design/agents.md before touching `mcp_server.py` or `hooks.py`; `hooks.py`
  does not change.
- The client gets exactly one answer per request id and nothing the SDK would not send.
- CHANGELOG: the next patch's `(unreleased)` heading (0.48.0 is released).

## Review Focus

- Thread safety of the stdout writes (one lock) and of the hand-over moment (the reader
  decides "answer or queue" under the same lock the main thread takes to mark the SDK up).
- fd 0/1 claimed before any thread or import that could spawn a child.
- No path where the client waits forever: EOF, an SDK import error, a cache write error
  (a write error is journaled and ignored).

## Task 1: `tool_set` and `instructions` in `lado.mcp_stdio` (D6)

Files: `src/lado/mcp_stdio.py` (new), `src/lado/mcp_server.py`.

- [ ] Tests first, `tests/test_mcp_stdio.py`: `tool_set` for no row, a worker, a read-only
  worker, the supervisor, a read-only supervisor, a `SchemaError`; `SUPERVISOR ==
  runtime.SUPERVISOR`; `instructions` text equals today's.
- [ ] Move them; `build` branches on `tool_set(me)` (same tools per set as before:
  `tests/test_mcp_server.py` unchanged and green); `_Server` uses `instructions`.
- [ ] `make test` green; commit.

## Task 2: The cache (D2, D4, D7)

Files: `src/lado/mcp_stdio.py`.

- [ ] Tests first: the key changes with `mcp_server.py`'s bytes, with each of the three
  packages' `__init__` stat (monkeypatched `find_spec`), with the tool set; a missing,
  unreadable or invalid file is a miss; per-version `initialize` entries; a write is
  atomic (temp + replace) and prunes to the 20 newest; the folder is
  `state.home() / "mcp-cache"`.
- [ ] Implement `cache_key`, `read_cache`, `write_cache`; commit.

## Task 3: The front: reader, writer, pipes, hand-over (D1, D3, D5, D8, D9)

Files: `src/lado/mcp_stdio.py`, `src/lado/mcp_server.py` (`main` goes or calls the front).

- [ ] Tests first, the front driven with in-memory pipes and a loader that blocks on an
  event: a warm `initialize` and `tools/list` answered before the event; `mcp_ready`
  recorded once and the server built with instance `""`; the queue reaches the SDK in
  order after the replayed `initialize`; the SDK's duplicate answer to id 1 dropped; a
  `tools/call` sent before the load answered once after it; a cursor request and
  `ping` queued; a first message other than `initialize` turns the front off; a cold
  start writes the file from the SDK's answers; a cached tool list that differs from the
  SDK's is replaced and journaled once (`telemetry.record("mcp:cache", …)`) with nothing
  extra to the client; a failing loader exits non-zero with its traceback on stderr; EOF
  ends the process; `MCPServer` still has `_lowlevel_server`; the module's top imports
  (fresh interpreter).
- [ ] Implement `main()`; commit.

## Task 4: The agents and `lado mcp` start the front (D1)

Files: `src/lado/providers/base.py`, `src/lado/cli.py`.

- [ ] Tests first: the LADO MCP server entry of each provider's config runs
  `interpreter.run_module("lado.mcp_stdio")` (update the providers' config tests;
  `grep -rn '"mcp"' tests src` for others that name the old command, `tests/leftovers.py`
  included); `lado mcp` runs `mcp_stdio.main`.
- [ ] Implement; `make test` green; commit.

## Task 5: End-to-end tests (integration, fake agent)

Files: `tests/integration/test_mcp_start.py` (new).

- [ ] A cold then a warm real server in one temp `LADO_HOME` (the command
  `providers.base` gives): `initialize` equal but `instructions`, `tools/list` equal,
  `list_agents` works on both, the cache file exists after the cold start; a worker after
  the supervisor gets the worker's tools, not the supervisor's.
- [ ] `test_agents.py::test_first_turn_waits_for_the_one_lado_mcp_server_of_the_launch`
  green as it is (w1 is the second start, after the supervisor's).
- [ ] `uv run pytest -m integration -n auto tests/integration/test_mcp_start.py
  tests/integration/test_agents.py tests/integration/test_fake_agent.py
  tests/integration/test_mid_turn_messages.py`; commit.

## Task 6: Docs and CHANGELOG

- [ ] docs/design/agents.md (readiness), docs/design/modules.md, AGENTS.md's Layout line,
  docs/research/test-audit.md, CHANGELOG (Changed: agents start about 0.3 s sooner);
  `tests/test_agents_md.py` green; commit.

## Task 7: Regression run and numbers

- [ ] `make lint`, `make test`, the integration files of Task 5, `openspec validate
  mcp-server-fast-start --strict`; CI's full integration and UI suites.
- [ ] The probe before (on `origin/main`) and after, both medians in the pull request;
  the manual check of the design doc with Claude Code and Codex.
