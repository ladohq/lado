Plan: `docs/superpowers/plans/2026-10-12-lead-recommendation.md` (each task's tests and
steps). Design doc: `docs/superpowers/specs/2026-10-12-lead-recommendation-design.md`.

## 1. State (D1, D4, D5)

- [x] 1.1 Schema 26: six columns on `gates` and `messages`, the `MIGRATIONS` step,
  `state.Gate` / `state.Message` fields, `tests/agent_helpers.previous_schema`. Check:
  `tests/test_state.py` migration tests, `make test`.
- [x] 1.2 `state.ask_recommendation`, `state.recommend` (conditional update),
  `state._drop_request` in every gate- and question-closing transaction,
  `state.recommendations_missed`, `missing` on the lead's end and on `stop_session`.
  Check: `uv run pytest tests/test_state.py -n auto -k recommend`.

## 2. Core (D2, D3, D6, D10)

- [x] 2.1 `runs._act_on_arrival`: the request instead of "waiting for the human at …"
  (message or notice), with the note's attachments; `runs.resume` asks again. Check:
  `uv run pytest tests/test_runs.py -n auto -k recommend`.
- [x] 2.2 `runtime.ask_human` asks the lead for another agent's question;
  `runtime.recommend` with its checks; `SUPERVISOR_INSTRUCTIONS` and `FLOW_INSTRUCTIONS`.
  Check: `uv run pytest tests/test_runtime.py -n auto -k recommend`.
- [x] 2.3 `mcp_server.recommend` for the lead only (read-only too); `hooks.main` calls
  `recommendations_missed` after `check_replies`, not with a resume planned. Check:
  `uv run pytest tests/test_mcp_server.py tests/test_runtime.py -n auto -k recommend`
  (the turn-end hook's tests live in `tests/test_runtime.py`).

## 3. CLI (D9)

- [x] 3.1 `cli._show_gate` and the `v` page: the recommendation's lines, the marked
  option, `asked` and `missing`. Check: `uv run pytest tests/test_cli.py -n auto -k
  recommend`.

## 4. API (D7)

- [x] 4.1 `RecommendationInfo`, `GateInfo.recommendation`, `MessageInfo.recommendation`;
  `make web-types`, both generated files committed. Check: `uv run pytest
  tests/test_server_gates.py tests/test_server_messages.py -n auto -k recommend`, `make web`.

## 5. Web UI (D8)

- [x] 5.1 `web/src/Recommendation.tsx`, `GateCard.tsx` (also compact and the closed
  view), `Question.tsx` (open and closed), `styles.css`; the recommended button primary.
  Check: vitest in `web/src/Recommendation.test.tsx`, `Chat.test.tsx`, `make web`.

## 6. End to end

- [x] 6.1 Integration with the fake agent (`tests/integration/test_flow_runs.py`,
  `test_human_messages.py`): a worker's advance into a gate gives the lead the request;
  the fake lead's `recommend` reaches `GateInfo`; a gate answered while the request is
  pending drops it; a turn end after the request marks `missing`; a worker's question
  gets a request. Check: `uv run pytest -m integration -n auto
  tests/integration/test_flow_runs.py tests/integration/test_human_messages.py`.
- [x] 6.2 UI e2e (`tests/ui/test_gates.py`, `test_chat.py`): a gate and a question with a
  recommendation that disagrees, the primary button, "preparing", a closed card's line;
  screenshots. Check: `uv run pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py`.

## 7. Docs

- [x] 7.1 AGENTS.md (Layout: `state.py` schema 26, `mcp_server.py` tool list, `runs.py`;
  How agents talk; Gates: the request instead of "waiting for the human at"), 
  docs/design/ui.md (Flow gates, A question, the open question's card: the block, the
  primary button; mockup `task/lad-27/mockup-recommendation.html` v3), CHANGELOG.md under
  `## 0.37.0 (unreleased)`.
- [ ] 7.2 Regression run of the plan; `openspec validate lead-recommendation --strict`.
