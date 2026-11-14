# LAD-282 test-run-drops-agent-launch: review report

Pull request #304 `hotfix/lad-282-test-run-drops-agent-launch` → `main`. Scale: hotfix, depth
precision. Head reviewed: `1af11473`. A test run started in a LADO agent's shell was red where CI
was green: `tests/conftest.py` cleared a fixed list of LADO's names but not `LADO_LAUNCH_VARS` nor
the names it lists (`CLAUDE_CODE_TMPDIR` among them), and the run's environment reaches the agents
the tests start. The run now drops `LADO_LAUNCH_VARS` and every name it lists but `TMPDIR`
(`tests/agent_helpers.without_agent_launch`), besides the fixed list.

## Rounds

1. Local, precision (`origin/main..1af11473`), checked against the change's proposal and tasks;
   and external 1, Claude Code GitHub Action (request 17:55:17Z, answer 17:56:06Z, "no blocking
   findings"). The external round did not read the openspec files (checked locally with
   `openspec validate`).

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | — | external: a model server's key named in `LADO_LAUNCH_VARS` is now dropped, so a live or smoke run in an agent's shell would lose it | refuted: the live layer takes its key from its own variable (`tests/live/conftest.py`), and dropping the outer agent's launch key is the leak's fix, as `agent_env.without_launch` does |
| F2 | minor | external: the conftest loop has no test of its own, only the helper is tested | declined: the loop is one line over the tested helper; `tests/test_temp_dirs.py` covers the path end to end in an agent's shell |

The local pass found no defect. Checked by reading: only LADO's and a provider's names reach
`LADO_LAUNCH_VARS` (never `PATH`, `HOME`, `SHELL`); `without_agent_launch` drops what
`agent_env.without_launch` drops but `TMPDIR`; an empty list is harmless; popping while iterating
works on a copied key set.

## Metrics

Rounds: 1 local, 1 external, 0 stand-ins. Findings: local 0 confirmed / 0 refuted; external 1
confirmed (minor, declined), 1 refuted; findings in code changed by the developer's cleanup: 0.

## Checks

- In an agent's shell with `LADO_LAUNCH_VARS` set: `uv run pytest -n0 tests/test_agent_helpers.py
  tests/test_temp_dirs.py`: 38 passed (reviewer); `make test`: 6120 passed, 7 skipped (developer).
- `make lint`: green. `openspec validate test-run-drops-agent-launch --strict`: valid.
- CI on `1af11473`: 27/27 pass, `mergeStateStatus: CLEAN`.

## Residual risk

- In CI no agent variables are set, so the conftest path is checked there only trivially (F2).
- The reviewer did not run `make test` locally nor repeat the developer's mutation runs; live
  tests were not run (no change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py` or `tests/live/`).
- The external reviewer is of the same model family.

Found on the way: none.
