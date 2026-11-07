# LAD-172 mid-turn-messages: review report

Pull request #205 `hotfix/lad-172-mid-turn-messages` → `main`. Scale: hotfix, review
depth: precision, widened to breadth in round 1 (the diff touches message delivery for
every agent: `mcp_server.py`, `runtime.py`, `state.py`). Head reviewed: `d60501c1` (= the
remote head). The result of any call of a `lado` MCP tool now carries the caller's queued
messages (channel `tool_result`, `delivered` at once), `read_messages` takes the queue
first, and a `send_message` to an agent whose own message still waits for the sender is
refused until the sender has received it.

## Rounds

- **Round 1** (`origin/main...fa037e63`): local, breadth; lenses spec, tests, silent
  failures, comments and docs, types, general, architecture against AGENTS.md. External
  1 of 1 (Claude Code GitHub Action), which read `src/` in full but not the tests, the
  docs or the second half of the spec. CI on `fa037e63`: four integration shards red (F1,
  F2) → changes.
- **Round 2** (`fa037e63..d60501c1`): local precision on the delta; F1–F3 resolved, no
  new findings. No external round: the hotfix cap of 1 was used.

The external reviewer is of the same model family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | A `send_message` from `human` was refused: messages to the human are stored `delivered` and never `read`, so an agent's question with a body "waited" for the human forever (CI: six `test_project_*` tests and `test_session_start`) | fixed in 68f7765b: the check is skipped when `human` is sender or recipient; documented in d60501c1 |
| F2 | blocker | Three tests of `test_agent_liveness.py` queued a message before the worker's `read_messages` for its task, which then took it | fixed in 68f7765b: the tests wait for the worker's first pause |
| F3 | minor | The queue was taken before the result's type was checked, and a non-`ToolError` failure lost what `read_messages` had taken | fixed in 68f7765b, with tests seen red before the fix |
| E1 | — | external: `lado_messages` could break an `outputSchema` with `additionalProperties: false` | refuted: no output schema forbids extra keys at the top level |
| E2 | minor | external: `tool_result` messages may arrive before an unconfirmed `sent` batch | declined: only on the sweep's retype into a busy agent; nothing is lost |
| E3 | — | external: a worker's report is refused once when the supervisor's message waits for it | refuted: by design (D5), the error says to send again |
| E4 | minor | external: the integration test does not cover `sent` with a body | declined: one SQL condition covers `sent` and `delivered`; a unit test covers it |
| R2-1 | — | `except Exception` turns an `MCPError` into a `ToolError` when the queue is not empty | refuted: only to keep taken lines; lado's tools raise no `MCPError` |

Deviation from the spec accepted by the review: messages **from** `human` are not refused
either. The spec describes a send by agent A; the human is not an agent, and their
messages would otherwise be blocked for good.

## Checks

- Round 1 on `fa037e63`: `make lint` green; `make test` 4738 passed; `openspec validate`
  (change and specs) valid.
- Round 2 on `d60501c1`: `make lint` green; `make test` 4741 passed, 7 skipped;
  `-m integration` on the six touched files 33 passed, 1 flake
  (`test_project_secrets.py::test_every_agent_of_a_session_gets_its_project_s_secrets`, a
  30 s timeout under `-n auto`, passed twice alone with `-n0`, green in CI);
  `openspec validate mid-turn-messages --strict` valid. CI on `d60501c1` 23/23 with
  `ci-ok`, the smoke ×8 and the container cells ×2.

## Residual risk

- A result the CLI drops (interrupted by the human, a client timeout, an asyncio
  cancellation) takes messages already marked `delivered` with it: a property of D2.
- Which part of the result the model sees: Claude Code shows the structured content;
  Codex by its source, not reread; Kilo by analogy with OpenCode. Not checked live: task
  4.2 (AC-7), the human's manual check on the release candidate with Codex and Claude
  Code.
- UI, smoke and live tests were not run locally; CI ran UI and smoke green; live runs at
  a release. The change touches `mcp_server.py` and `runtime.py`.
