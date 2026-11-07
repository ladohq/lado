# LAD-169 agent-model-visible: review report

Pull request #194 `feature/lad-169-agent-model-visible` → `epic/lad-154-models`. Scale:
full, review depth: breadth first. Head reviewed: `b7cfad12` (= the remote head). Every
agent's model and effort, each with its source (`cli`, `cli-config`) and a detail, are
kept in `lado.db` (schema 36) and shown by `list_agents`, the API, the agent's page, the
Team tooltip and `lado ls`; the model comes from the events the CLIs already send (Codex's
hooks, Claude Code's SessionStart, the OpenCode family's `chat.message`) and, for Codex,
from the carried `config.toml`. `providers/`, `hooks.py`, `mcp_server.py` and `runtime.py`
changed.

## Rounds

- **Round 1** (`origin/epic/lad-154-models...39c63108`): a local breadth pass (spec,
  tests, silent failures, comments, types, general, architecture against AGENTS.md). No
  external round: F1 was open.
- **Round 2**: a local precision pass over `39c63108..b7cfad12`, no new findings; external
  1 of 2 (Claude Code GitHub Action): no blocking problems, three non-blocking notes and
  one question. It read every changed file of `src/` (only diff hunks of `runtime.py`,
  `providers/*` and `state.py`), none of docs, openspec, web and tests; those were read
  locally in round 1.

External rounds used: 1 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | OpenCode/Kilo: a model's variant set back to the default left the old effort shown | fixed in 12b6056f, b7cfad12 (an effort reported as `""` is the CLI's default; a requirement and scenario of its own) |
| F2 | minor | The comment above `AgentTip` described the tooltip without the model | fixed in 748aa000 |
| F3 | minor | The comment of `AGENT_REST` stood above `CLI_DEFAULT` in `web/src/fakes.ts` | fixed in 748aa000 |
| F4 | minor | `report_model` takes `BEGIN IMMEDIATE` on every Codex hook even when nothing changes | declined: short transaction, writes nothing |
| E1 | — | external: does Claude's SessionStart now lose a field? | refuted: the event was the same before (no `prompt` on SessionStart) |
| E2 | — | external: `set_model` shows "CLI default" at each launch until the first event | refuted: the true state before the CLI names its model |
| E3 | minor | external: `lado ls` pads the model to 18 characters, a longer name shifts the branch column | declined: decided in design D9, cosmetic |
| E4 | — | external: schema 36 may collide with a migration in main | refuted: main has 35; the check at each merge of the base is in design.md |

## Checks (head b7cfad12)

- `make lint`: clean. `make test`: 4731 passed, 7 skipped.
- `uv run pytest -m integration -n auto tests/integration/test_agents.py
  tests/integration/test_fake_agent.py`: 38 passed. `uv run pytest -m ui
  tests/ui/test_agents_tab.py`: 4 passed.
- `openspec validate --specs --strict`: 54 passed; the change: valid.
- CI 41360694756: 23/23 green, `ci-ok`, the smoke of claude, codex, kilo and opencode on
  Linux and macOS, container.
- `make web` and `make test-js` were not rerun by the reviewer: CI green, the developer's
  runs 1150 and 17 passed.

## Not checked (residual risk)

- Live tests (`make test-live`) were not run, though `providers/`, `hooks.py`,
  `mcp_server.py` and `runtime.py` changed; the smoke of every provider is green.
- Whether Kilo puts the model into `chat.message` is unconfirmed (its bundle is packed);
  without it Kilo agents show "CLI default".
- Codex: after `/model` in the CLI the effort still reads "your Codex config" (D5: no
  Codex hook reports the effort).
- Claude Code: a `/model` change shows at the next SessionStart only.
- The migration number 36 is checked against main at each merge of the base: 0.44.0 ships
  from main separately.

## Found on the way

None.
