The plan with each task's tests: `docs/superpowers/plans/2026-11-23-mcp-server-fast-start.md`.

## 1. Tool set and instructions without the SDK

- [x] 1.1 `tool_set` and `instructions` in `lado.mcp_stdio`, used by `mcp_server.build`
  and `_Server` (D6). Check: `tests/test_mcp_stdio.py`, `tests/test_mcp_server.py`.

## 2. The cache

- [x] 2.1 Key, read, atomic write, pruning, per-version `initialize` (D2, D4, D7). Check:
  `tests/test_mcp_stdio.py`.

## 3. The front

- [ ] 3.1 fd claim, reader and writer threads, pipes into `stdio_server`, replay and
  dropped duplicates, the check after the hand-over, `mcp_ready`, failures (D1, D3, D5,
  D8, D9). Check: `tests/test_mcp_stdio.py`.

## 4. The entry

- [ ] 4.1 `providers.base`'s LADO MCP server runs `lado.mcp_stdio`; `lado mcp` runs the
  front (D1). Check: the providers' config tests, `tests/test_cli*.py`.

## 5. End-to-end tests

- [ ] 5.1 Cold and warm real `lado mcp`: equal answers, tool calls, per tool set. Check:
  `uv run pytest -m integration tests/integration/test_mcp_start.py`.
- [ ] 5.2 Readiness and every tool through the fake agent. Check: `uv run pytest -m
  integration tests/integration/test_agents.py tests/integration/test_fake_agent.py
  tests/integration/test_mid_turn_messages.py`.

## 6. Docs and CHANGELOG

- [ ] 6.1 docs/design/agents.md, docs/design/modules.md, AGENTS.md, docs/research/test-audit.md,
  CHANGELOG. Check: `tests/test_agents_md.py`.

## 7. Regression run

- [ ] 7.1 `make lint`, `make test`, the integration files above, `openspec validate
  mcp-server-fast-start --strict`, CI green; the probe's medians before and after in the
  pull request.
