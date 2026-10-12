# The lead's recommendation on each question to the human: design

Task: LAD-27. Change: `openspec/changes/lead-recommendation/`. Mockup: run artifact
`task/lad-27/mockup-recommendation.html` (v2; screens 1, 2b, 3–7 are the approved look;
2a and the v1 variant A were rejected).

## Problem

A flow gate makes two entries in the chat: the gate's card, and a message from the
supervisor with an overview and a recommendation. The human values the supervisor's own
view but wants it as one entry with the gate. Root cause: the core opens the gate and
sends the lead "waiting for the human at <state> (gate #N)"; the lead's instructions
(LADO's "the question and your recommendation", kit sdlc's "A gate opens…") make it write
a free message to the human that nothing ties to the gate.

## What the user sees after the change

**In the web UI** (chat, Needs you, a run's page in Flows)

1. An open gate's card, and an open question's card of an agent other than the
   supervisor, has a block between its text (the question, the note, the artifacts it
   reads) and the answer: the supervisor's small avatar, "Supervisor's recommendation",
   its time, and the whole text as Markdown.
2. The option the supervisor recommends is the blue (primary) button; the others are
   quiet. No label on the button. Without a recommended option, the first is blue, as
   today.
3. When the supervisor disagrees with the agent whose report led to the gate (or who
   asks), the block's head has an orange "disagrees with <agent>" and its band is orange.
4. Until the supervisor answers: "Supervisor is preparing a recommendation…"; the human
   may answer at once. When its turn ended without one, or it stopped: "The supervisor
   gave no recommendation". A later recommendation replaces either.
5. A closed card keeps one quiet line, "Supervisor recommended: <option>" (" · disagreed
   with <agent>" in orange), whose text opens on a click; the closed gate's read-only view
   the same.
6. The supervisor's own questions have no block. No separate message from the supervisor
   about a gate any more.

**In the terminal** (`lado answer`, the tmux popup)

```
Gate #41, session lad-27, run task/lad-27 at design_ok:
Approve the design?
Note: LAD-27, full: … (v: the full note, 14 more lines)
Supervisor recommends: approve (v: the full text, 3 more lines)
  Approve. The design keeps one source of truth …
Artifacts it reads:
  task/lad-27/design: LAD-27 design — …
Options:
  1) approve   ← supervisor recommends
  2) reject
```

With a disagreement: `Supervisor recommends: reject (disagrees with reviewer)`. While
asked: `Supervisor is preparing a recommendation… (v shows it once it is given)`; missing:
`The supervisor gave no recommendation.`

**For the supervisor**

7. When a gate opens or another agent asks the human, it gets one message from `lado`:
   `recommend on gate #41: task/lad-27 at design_ok` (or `recommend on question #812 of
   developer`), with the question, options, note and artifacts in the body and the note's
   artifacts attached; when its own `flow_advance` opened the gate, the same in the
   result's `notices`. It answers with `recommend(gate=41, text=…, choice="approve",
   disagrees=false)`, which it may call again until the human answers.

## Architecture

- `src/lado/state.py`: schema 26 (D1), `ask_recommendation`, `recommend`,
  `_drop_request`, `recommendations_missed`, `missing` on the lead's end and on stop.
- `src/lado/runs.py`: `_act_on_arrival`'s request (D2), `resume`'s new requests (D6).
- `src/lado/runtime.py`: `ask_human` → `ask_recommendation`, `recommend` (D3), the
  instructions (D10).
- `src/lado/hooks.py`: the turn-end check (D5). `src/lado/mcp_server.py`: the tool (D3).
- `src/lado/cli.py`: `_show_gate` and the `v` page (D9).
- `src/lado/server/models.py`: `RecommendationInfo` (D7); `web/openapi.json`,
  `web/src/api.gen.ts`.
- `web/src/Recommendation.tsx`, `GateCard.tsx`, `Question.tsx`, `styles.css` (D8).

## Choices and their long-term cost

See `design.md` Options: a core recommendation tied to the gate or question (chosen: one
tool, six columns on two tables, a turn-end check, one UI component; the same for every
kit and provider), instructions only (loses the opinion the human values), merging the
lead's free message in the UI (a guess from text, the wrong card for a late message).
Decisions D1–D12 in `design.md`.

## Tests by layer (AGENTS.md, Testing)

| Requirement | Layer | Where |
|---|---|---|
| LADO asks the lead (gate, loop limit, notice, worker's question, lead's own question, lead not running) | unit | `tests/test_runs.py`, `tests/test_runtime.py` |
| The tool recommend (store, replace, every refusal, read-only lead has it, workers do not) | unit | `tests/test_runtime.py`, `tests/test_mcp_server.py` |
| A request not needed is dropped (answer, dismiss, override, cancel, agent's end) | unit | `tests/test_state.py`, `tests/test_runs.py` |
| Not given (turn end, pending request, resume planned, lead's end, stop, resume asks again) | unit | `tests/test_state.py`, `tests/test_runtime.py`, `tests/test_runs.py` |
| Schema 26 migration | unit | `tests/test_state.py` |
| API and feed carry it | unit | `tests/test_server_gates.py`, `tests/test_server_messages.py` |
| lado answer shows it | unit | `tests/test_cli.py` |
| The card (block, disagreement, primary button, preparing, missing, none, closed line, compact) | vitest | `web/src/Recommendation.test.tsx`, `web/src/Chat.test.tsx` |
| Request, recommend, drop and turn-end check across hooks, `lado mcp` and the queue | integration | `tests/integration/test_flow_runs.py`, `tests/integration/test_human_messages.py` |
| The cards in a browser, light and dark | UI e2e | `tests/ui/test_gates.py`, `tests/ui/test_chat.py` |

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_flow_runs.py tests/integration/test_human_messages.py`, `uv run
pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py tests/ui/test_needs_you.py
tests/ui/test_flows_tab.py`, `make web`, `openspec validate --specs --strict`; CI runs the
rest (`make check`, smoke). No provider code changes; live tests are not needed.

## Docs

AGENTS.md (Layout: `state.py` schema 26, `mcp_server.py`'s tools, `runs.py`; How agents
talk; Gates: the request replaces "waiting for the human at"; the Codex exception of D5),
docs/design/ui.md (Flow gates, A question, The open question's card: the block, the
primary button, the closed line; decided 2026-10-12, LAD-27, mockup
`task/lad-27/mockup-recommendation.html` v2), CHANGELOG.md `## 0.37.0 (unreleased)`.
Kit sdlc's paragraph "A gate opens…" is shortened in the kit's repository afterwards.
