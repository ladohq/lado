# LAD-294 mcp-server-fast-start: review report

Pull request #356 `feature/lad-294-mcp-fast-start` → `main`. Scale: full, review depth:
breadth. Head reviewed: `5b7406a3`. A new SDK-free module `lado.mcp_stdio` is the LADO MCP
server's process: it answers `initialize` and the four list requests from a cache in
`LADO_HOME/mcp-cache/` written from the SDK's own answers while the SDK loads, passes every
other message to the SDK over two pipes, checks its cached answers against the SDK's once it
is up, and records `mcp_ready` once. Every provider starts it from `providers.base`; `lado
mcp` runs the same front. Time to the `tools/list` answer: 0.370 s before, 0.033 s after
(the agents' command), 0.077 s through `lado.cli mcp`.

## Rounds

1. Local, breadth (spec, tests, silent failures, comments and description, types and
   invariants, general) plus the architecture against AGENTS.md, `origin/main..5b7406a3`.
   External 1, Claude Code GitHub Action: no blockers; it read `mcp_stdio.py` whole and the
   diffs of `mcp_server.py`, `cli.py` and `providers/base.py`, not the tests, docs or spec,
   and had no SDK installed (its SDK claims were from memory).

External rounds used: 1 of 2. Stand-ins: 0.

## The human's decisions

- **Gate `design_ok`**: answer the handshake and the lists from a cache of the SDK's own
  answers, not an MCP server of LADO's own (#7865).
- **Gate `merge_ok`, approved** with no comment; the declined minor findings stay as they are.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| R1-1 | minor | local: `Front._record_ready` catches only `state.SchemaError`; another database error writing `mcp_ready` ends the server process, where before it gave an error on `tools/list` | declined: a rare path, loud rather than silent |
| R1-2 | minor | local: a unit test of a thread failure leaves its loader unset, so a thread prints a traceback amid other tests 10 s later; the test passes | declined: noise, not a false green |
| R1-3 | minor | local: `mcp:cache` is journaled once per process, so a cache write error hides a later mismatch | declined: both rare; the external reviewer agreed |
| R1-4 | minor | local: docs/research/test-audit.md says 0.39 → 0.05 s, measured 0.38 → 0.03 s | declined |
| E1 | — | external: the `lado-check-*` requests may reach the SDK before `notifications/initialized` | refuted: checks follow lists the client sends after `initialized`; SDK 2.3 serves requests once `initialize` is accepted |
| E2 | minor | external: `build` runs under the front's lock and delays cached answers | declined: D8 needs that lock; a few ms, only after the SDK is loaded |
| E3 | minor | external: a client id `lado-check-1` or a reused id goes astray | declined: JSON-RPC ids are unique; no CLI LADO runs numbers so |
| E5 | — | external: `claim_stdio` fails with a bare OSError on closed fds 0/1/2 | refuted: the SDK's own claim failed the same way before |
| E6 | minor | external: the cache key misses schemas of other LADO modules and edits of package submodules | declined: every tool schema and docstring is in `mcp_server.py`; a reinstall rewrites `__init__.py`; the D5 check covers the rest |

## Checked against the code

- Every requirement and scenario of the delta `mcp-server-start` is implemented and tested:
  warm start, cold start and another tool set by unit tests and
  `tests/integration/test_mcp_start.py`; a client without the handshake, a cursor and ping,
  a tool call before the SDK is loaded with exactly one answer, a failing load, the
  journaled mismatch and `mcp_ready` once by unit tests.
- Every task of `tasks.md` checked (8 of 8); D1-D10 followed; nothing out of scope done.
- Architecture: the entry is shared in `providers.base` for every provider; one source for
  `tool_set` and `instructions`; no silent drops (`mcp:cache`, `mcp:stdio`); `SUPERVISOR`
  mirrors `runtime.SUPERVISOR`, with a test.

## Checks

| Check | Result |
|---|---|
| `make lint` | clean |
| `uv run pytest -n auto tests/test_mcp_stdio.py tests/test_mcp_server.py tests/test_providers.py tests/test_cli.py` | 687 passed |
| `uv run pytest -m integration -n auto tests/integration/test_mcp_start.py` | 2 passed |
| `openspec validate mcp-server-fast-start --strict` | valid |
| The design doc's probe, 10 starts, median to `tools/list` | before 0.370 s; after 0.033 s (`lado.mcp_stdio`), 0.077 s (`lado.cli mcp`) |
| CI on `5b7406a3` | 27 of 27 green, `ci-ok` success |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 4, external 3, all minor.
Refuted: local 0, external 2. Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing outside the task.

## Not verified (residual risk)

- No manual check with real Claude Code and Codex on a real model, and no live tests; CI's
  smoke runs the real CLIs with the new front against a 401 endpoint, green.
- Changed `mcp_server.py` and `providers/base.py`: the human may want `live.yml` run.
- The reviewer ran neither the full `make test` nor the full integration suite; CI did, green.
- AC-4 (an SDK import error after a cached answer) is proven by a unit test only.
