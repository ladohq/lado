# The lead's recommendation on each question to the human: implementation plan

**Goal:** when a flow gate opens or another agent asks the human, LADO asks the lead for
its recommendation; the lead answers with the MCP tool `recommend`; the recommendation is
stored on the gate or question and shown inside its card and in `lado answer` (LAD-27).

**Architecture:** six columns on `gates` and `messages` (schema 26) hold the
recommendation; `runs._act_on_arrival` and `runtime.ask_human` queue the request from
`lado` (or a notice); `runtime.recommend` stores it; closing transactions drop a pending
request; the lead's turn end marks a request it got and did not answer `missing`. The UI
reads `recommendation` of `GateInfo` / `MessageInfo` from the existing change feed.

**Tech stack:** Python 3.10+ (SQLite, FastAPI, pydantic, the MCP SDK), React +
TypeScript (vitest), pytest (unit, integration with the fake agent, UI with Playwright).

**Spec:** `openspec/changes/lead-recommendation/` (proposal, deltas `lead-recommendation`
and `chat-question-card`, `design.md` D1–D12). **Design doc:**
`docs/superpowers/specs/2026-10-12-lead-recommendation-design.md`. **Mockup:** run
artifact `task/lad-27/mockup-recommendation.html` v2 (screens 1, 2b, 3–7).

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-27)` at the end).

## Global constraints

- States: `asked`, `given`, `missing` (constants `state.REC_ASKED`, `REC_GIVEN`,
  `REC_MISSING`); NULL is "not asked".
- Columns (both tables): `recommendation_state TEXT`, `recommendation TEXT`,
  `recommended_choice TEXT`, `recommendation_disagrees INTEGER NOT NULL DEFAULT 0`,
  `recommended_at TEXT`, `recommendation_request INTEGER`.
- Texts, exactly: request summaries `recommend on gate #<id>: <run> at <state>` and
  `recommend on question #<id> of <agent>`; tool result `recommendation on gate #<id>
  stored; the human sees it on the gate's card` (`question #<id>` / `the question's
  card`); refusals `give gate or question, not both`, `give gate or question`, `the
  recommendation is empty`, `the recommendation is <n> characters, the limit is <limit>`,
  `gate #<id> is closed already: <answer> by <who>`, `question #<id> is <state>`,
  `question #<id> is your own`, `question #<id> has no choices`, `no gate #<id>`, `no
  question #<id> in session <s>`, and `runs.canonical_option`'s own text for a gate's
  option, `question #<id> has no choice "<c>"; its choices: <list>` for a question's.
- UI texts: `Supervisor's recommendation`, `disagrees with <agent>`, `Supervisor is
  preparing a recommendation…`, `The supervisor gave no recommendation`, `Supervisor
  recommended: <option>`, ` · disagreed with <agent>`.
- CLI texts: `Supervisor recommends: <option>` / `Supervisor's recommendation:`, `
  (disagrees with <agent>)`, ` (v: the full text, <n> more line[s])`, `   ← supervisor
  recommends`, `Supervisor is preparing a recommendation… (v shows it once it is given)`,
  `The supervisor gave no recommendation.`
- Limit: `runtime.MAX_MESSAGE` (8000) only; no limit of its own.
- Version 0.37.0 (CHANGELOG `## 0.37.0 (unreleased)`); `make web-types` after the models
  change, both generated files committed.

## Review focus

1. A request handed over in the turn-end hook's output of the same turn end must not be
   marked `missing` by that turn end — Task 3's hook-output test.
2. The human answers while the request is still pending: the request is dropped in the
   answer's transaction, and a `recommend` after it is refused — Task 2's drop tests.
3. A loop-limit gate (`continue` / `cancel`) and a choice gate with options in mixed case
   accept a recommended option the way `lado answer` accepts it — Task 3's option tests.
4. A worker's `ask_human` while the lead is stopped (session running, lead ended): the
   question is asked, no error to the worker, no block — Task 3's not-running test.
5. A recommended option on a gate in a stopped session: the card's buttons stay off and
   the block still shows — Task 6's stopped test.

---

### Task 1: Schema 26 (D1)

**Files:** modify `src/lado/state.py` (`SCHEMA_VERSION`, `SCHEMA`, `MIGRATIONS`, `Gate`,
`Message`, the message's column list near line 1804); `tests/agent_helpers.py`
(`previous_schema` undoes 26); test `tests/test_state.py`.

**Produces:** `state.REC_ASKED = "asked"`, `REC_GIVEN = "given"`, `REC_MISSING =
"missing"`; on `Gate` and `Message`: `recommendation_state: str | None = None`,
`recommendation: str = ""`, `recommended_choice: str | None = None`,
`recommendation_disagrees: bool = False`, `recommended_at: str | None = None`,
`recommendation_request: int | None = None`.

- [ ] Step 1: tests `test_schema_26_adds_the_recommendation_columns` (a fresh db and a
  migrated one from `previous_schema()` both have the six columns on both tables, NULL /
  0 on old rows) and `test_a_gate_and_a_question_read_back_their_recommendation_fields`.
- [ ] Step 2: `uv run pytest tests/test_state.py -n auto -k "schema_26 or recommendation_fields"`: fail.
- [ ] Step 3: code: the columns in `SCHEMA`, one `MIGRATIONS` step of twelve `ALTER
  TABLE … ADD COLUMN`, the fields, `previous_schema`.
- [ ] Step 4: the run passes; `uv run pytest tests/test_state.py -n auto`.
- [ ] Step 5: commit "Gates and questions keep the lead's recommendation (LAD-27)".

### Task 2: State functions (D2, D3, D4, D5)

**Files:** `src/lado/state.py`; test `tests/test_state.py`.

**Consumes:** Task 1. **Produces:**
- `state.ask_recommendation(session: str, kind: str, item: int, summary: str | None,
  body: str, attachments: Attached = (), before_start: bool = False) -> int | None`:
  `kind` is `"gate"` or `"question"`; with `summary`, queues a pending message from `lado`
  to `supervisor` (raises `NotRunning` as `queue_message` does when the lead does not run,
  unless `before_start`) and sets `recommendation_state = 'asked'`,
  `recommendation_request = <id>` in one transaction; `summary=None` (a notice) sets
  `asked` with no request. Returns the request id or None.
- `state.recommend(kind: str, item: int, text: str, choice: str | None, disagrees: bool)
  -> bool`: one `UPDATE … WHERE id = ? AND answer IS NULL` (gate) / `AND
  question_state = 'open'` (question) setting `given`, the text, choice, disagrees and
  `recommended_at = strftime('%Y-%m-%d %H:%M:%f','now')`; returns whether a row changed.
- `state._drop_request(db, table: str, where_sql: str, params)`: sets `state = 'dropped'`
  on the pending request messages of the rows being closed; called in `update_run` when
  `closes` closes a gate, in `reply_to_question`, and in `_close_questions`.
- `state.recommendations_missed(session: str) -> None`: `asked` → `missing` for open
  gates and open questions of the session whose `recommendation_request` is NULL or
  names a message in `delivered` or `read`.
- In `agent_ended` (for `SUPERVISOR`) and `_stop_session`: every `asked` of the session
  → `missing`.

- [ ] Step 1: tests:
  - `test_ask_recommendation_queues_the_request_and_marks_asked` (a gate made with
    `update_run(..., opens=...)` as `tests/test_runs.py` does; message from `lado` to
    `supervisor`, pending, attachments copied; gate `asked`, request id kept).
  - `test_a_notice_marks_asked_without_a_request`.
  - `test_recommend_stores_and_replaces` (two calls; second wins; `disagrees` back to
    False) and `test_recommend_on_a_closed_gate_changes_nothing` (returns False).
  - `test_answering_a_gate_drops_its_pending_request`,
    `test_a_handed_over_request_is_not_dropped`, `test_dismissing_a_question_drops_its_request`,
    `test_a_forgotten_agents_question_drops_its_request`.
  - `test_missed_marks_only_requests_the_lead_got` (one `delivered`, one `pending`, one
    notice: the first and third become `missing`, the second stays `asked`; a `given` and a
    closed gate untouched).
  - `test_the_leads_end_and_a_stop_mark_asked_missing`.
- [ ] Step 2: `uv run pytest tests/test_state.py -n auto -k recommend`: fail.
- [ ] Step 3: code as above.
- [ ] Step 4: passes; `uv run pytest tests/test_state.py -n auto`.
- [ ] Step 5: commit "State asks for, stores and drops the lead's recommendation (LAD-27)".

### Task 3: The core and the tool (D2, D3, D5, D6, D10)

**Files:** `src/lado/runs.py` (`_act_on_arrival`, a new `_ask_recommendation`,
`resume`), `src/lado/runtime.py` (`ask_human`, new `ask_recommendation`, `recommend`,
`SUPERVISOR_INSTRUCTIONS`, `FLOW_INSTRUCTIONS`), `src/lado/hooks.py` (`TURN_END`),
`src/lado/mcp_server.py`; tests `tests/test_runs.py`, `tests/test_runtime.py`,
`tests/test_mcp_server.py`.

**Consumes:** Task 2. **Produces:** `runtime.recommend(session: str, agent: str, text:
str, gate: int | None, question: int | None, choice: str | None, disagrees: bool) -> str`;
`runtime.ask_recommendation(session: str, question: state.Message) -> None`;
`runs.recommendation_request(gate: state.Gate) -> tuple[str, str]` (summary, body; also
used by `resume`).

- [ ] Step 1: tests:
  - `tests/test_runs.py`: `test_a_gate_asks_the_lead_for_a_recommendation` (a worker's
    advance into an approval gate: one message from `lado` with the summary of Global
    constraints, its body holds the question, `Options: approve, reject`, the note, the
    reads' lines, the instruction paragraph; the note's attachments attached; no message
    containing `waiting for the human at`), `test_a_loop_limit_asks_too`,
    `test_the_leads_own_advance_gets_the_request_as_a_notice`,
    `test_a_gate_opens_when_the_lead_does_not_run` (no request, state NULL, the popup
    still asked for via the `fake_tmux` recorder), `test_a_resume_asks_again_for_gates_without_a_given_recommendation`.
  - `tests/test_runtime.py`: `test_a_workers_question_asks_the_lead`,
    `test_the_leads_own_question_asks_nothing`, `test_a_question_while_the_lead_is_stopped_is_asked_without_a_request`,
    `test_recommend_*` for each refusal of Global constraints and for a gate option in
    mixed case and an approval outcome name (`approved`), a loop limit's `continue`;
    `test_a_turn_end_marks_a_request_the_lead_got_missing`,
    `test_a_turn_end_with_a_planned_resume_keeps_asked`,
    `test_a_request_handed_over_in_the_hook_output_is_not_marked_by_that_turn_end`
    (drive `hooks.main` as the existing turn-end tests do), and
    `test_the_instructions_name_recommend_and_forbid_a_separate_message`.
  - `tests/test_mcp_server.py`: `test_the_lead_has_recommend`,
    `test_a_read_only_lead_has_recommend`, `test_a_worker_has_no_recommend`.
- [ ] Step 2: the three files with `-k "recommend or ask"`: fail.
- [ ] Step 3: code:
  - `runs._act_on_arrival`: for `WAITING`, `_ask_recommendation(run, gate, notices)`:
    with `notices` append `f"flow {run.name}: {summary}\n{body}"` and call
    `state.ask_recommendation(..., summary=None)`; else `state.ask_recommendation` with
    the note's attachments (`state.note_attachments(gate.note_id)` or the existing reader
    `runs.gate_attachments` uses) inside `with suppress(state.NotRunning)`, then
    `runtime._deliver(session, SUPERVISOR, id)`; then `_popup` as now.
  - `runs.resume`: after the steps, `for gate in` the open gates of the session whose
    state is not `given`: `state.ask_recommendation(..., before_start=True)`; the gate's
    line in the body ends with `A request for your recommendation follows.`
  - `runtime.ask_human`: after `add_question`, if `sender != SUPERVISOR`:
    `ask_recommendation(session, state.get_message(session, asked))`.
  - `runtime.recommend`: the checks in D3's order, then `state.recommend`; False from it
    re-reads and raises the closed text.
  - `hooks.main`, `TURN_END`, after `state.check_replies`: `if agent == SUPERVISOR and
    not state.get_agent(session, agent).resume_at: state.recommendations_missed(session)`
    — after `runtime.turn_failed` so a planned resume is seen (move the call below it).
  - `mcp_server.py`: `recommend` registered for `me.name == runtime.SUPERVISOR` outside
    the `not me.read_only` block; its docstring says what it is for in two lines.
  - `SUPERVISOR_INSTRUCTIONS`: a bullet `- recommend: …` and the replaced rule of D10;
    `FLOW_INSTRUCTIONS`' last paragraph adds `LADO asks you for your recommendation on
    it; give it with recommend.`
- [ ] Step 4: passes; `uv run pytest tests/test_runs.py tests/test_runtime.py tests/test_mcp_server.py tests/test_read_only_hooks.py -n auto`.
- [ ] Step 5: commit "The lead recommends on each gate and agent's question with a tool (LAD-27)".

### Task 4: `lado answer` (D9)

**Files:** `src/lado/cli.py` (`_show_gate`, the `v` page's text); test `tests/test_cli.py`.

- [ ] Step 1: tests `test_answer_shows_the_recommendation_and_marks_the_option`,
  `…_with_a_disagreement`, `…_while_it_is_prepared`, `…_when_none_was_given`,
  `…_without_one_shows_nothing_new`, `test_v_shows_the_whole_recommendation`.
- [ ] Step 2: `uv run pytest tests/test_cli.py -n auto -k recommend`: fail.
- [ ] Step 3: code: in `_show_gate` after the note's artifacts, a helper
  `_recommendation_lines(gate) -> list[str]` (the head line with the `v` hint when the
  text has more than one line, the first line indented two spaces); in the options loop
  `f"  {n}) {option}{'   ← supervisor recommends' if option == gate.recommended_choice else ''}"`;
  the `v` page appends `\nSupervisor's recommendation:\n<text>` when given.
- [ ] Step 4: passes; `uv run pytest tests/test_cli.py -n auto`.
- [ ] Step 5: commit "lado answer shows the supervisor's recommendation (LAD-27)".

### Task 5: API (D7)

**Files:** `src/lado/server/models.py`; `web/openapi.json`, `web/src/api.gen.ts`; tests
`tests/test_server_gates.py`, `tests/test_server_messages.py`.

**Produces:** `RecommendationInfo {state: Literal["asked","given","missing"], text: str,
choice: str | None, disagrees: bool, by: str | None, at: str | None}`;
`GateInfo.recommendation: RecommendationInfo | None`, `MessageInfo.recommendation:
RecommendationInfo | None`; `models.recommendation_info(row, by)`.

- [ ] Step 1: tests: `test_a_gate_carries_its_recommendation` (`by` is the note's actor),
  `test_a_question_carries_its_recommendation` (`by` is its sender),
  `test_a_message_has_no_recommendation`, `test_the_feed_sends_the_gate_again_when_recommended`
  (the change journal, as the existing feed tests).
- [ ] Step 2: `uv run pytest tests/test_server_gates.py tests/test_server_messages.py -n auto -k recommend`: fail.
- [ ] Step 3: code; `make web-types`.
- [ ] Step 4: passes; `make web` (stale-types check).
- [ ] Step 5: commit models and both generated files: "The API gives a gate's and a question's recommendation (LAD-27)".

### Task 6: The cards (D8)

**Files:** create `web/src/Recommendation.tsx`, `web/src/Recommendation.test.tsx`;
modify `web/src/GateCard.tsx` (`GateCard`, the closed gate's read-only view),
`web/src/Question.tsx`, `web/src/styles.css`, `web/src/Chat.test.tsx`, `web/src/fakes.ts`.

**Produces:** `Recommendation({ rec }: { rec: RecommendationInfo })`,
`RecommendationLine({ rec })`, `primaryOf(options: string[], rec?: RecommendationInfo |
null): string` (the recommended choice when given and one of `options`, else
`options[0]`).

- [ ] Step 1: vitest: the block's head, text, time; the orange chip only with
  `disagrees`; `asked` and `missing` lines; nothing for `null`; `primaryOf`; in
  `Chat.test.tsx` a gate whose recommendation is `reject` has Reject `.primary` and
  Approve `.quiet`, a question's recommended choice `.primary`, a closed question's line
  "Supervisor recommended: later" opening its text, the chosen choice still once
  (`chat-question-card`), a stopped session's gate keeps its buttons off with the block
  shown, the compact card in Flows shows the block.
- [ ] Step 2: `cd web && npx vitest run Recommendation Chat`: fail.
- [ ] Step 3: code to the mockup v2 (screens 1, 2b, 3–6): classes `.rec`, `.rec.differs`,
  `.rec.waiting`, `.rec-head`, `.rec-title`, `.rec-differs`, `.rec-closed`; colours only
  through tokens (`--avatar-6` is not used for the band: the supervisor's avatar colour
  comes from `avatar("supervisor")`; the band is `--line`, `--human` when it differs).
  No "→ option" chip in the open block's head (the human's decision).
- [ ] Step 4: `make web`.
- [ ] Step 5: commit "The gate and question cards show the supervisor's recommendation (LAD-27)".

### Task 7: End to end

**Files:** `tests/integration/test_flow_runs.py`, `tests/integration/test_human_messages.py`,
`tests/integration/fake_agent.py` (only if the fake has no generic MCP call command;
it runs message bodies as commands, so a step body can call `recommend`), `tests/ui/test_gates.py`,
`tests/ui/test_chat.py`.

- [ ] Step 1: integration: `test_a_gate_asks_the_lead_and_its_recommendation_reaches_the_gate`
  (a fake worker advances into a gate; the fake supervisor gets `recommend on gate #…`;
  it calls `recommend`; `GET …/gates` shows `given`), `test_a_gate_answered_first_drops_the_request`
  (the supervisor held busy with `pause`, the human answers through `runs.answer`, the
  request is `dropped`, `agent_helpers.release`), `test_the_leads_turn_end_without_recommend_marks_missing`,
  `test_a_workers_question_asks_the_lead`.
- [ ] Step 2: UI e2e: `test_a_gate_with_a_recommendation_that_disagrees` (block, orange
  chip, Reject primary; screenshot light and dark), `test_a_gate_whose_recommendation_is_prepared`,
  `test_a_question_with_a_recommendation_open_and_closed`; data made through the core as
  the existing tests make gates and questions.
- [ ] Step 3: `uv run pytest -m integration -n auto tests/integration/test_flow_runs.py
  tests/integration/test_human_messages.py`; `uv run pytest -m ui tests/ui/test_gates.py
  tests/ui/test_chat.py`.
- [ ] Step 4: commit "End-to-end tests of the lead's recommendation (LAD-27)".

### Task 8: Docs

**Files:** `AGENTS.md`, `docs/design/ui.md`, `CHANGELOG.md`.

- [ ] Step 1: AGENTS.md: Layout (`state.py` from schema 26: the recommendation columns of
  `gates` and `messages`; `mcp_server.py`: `recommend`, the lead's, also read-only;
  `runs.py`: the request); How agents talk (the request, the turn-end check, Codex's
  error turns keep `asked`); Gates: "The supervisor gets one line, `flow <run>: waiting
  for the human at …`" becomes the request `recommend on gate #<id>: …`.
- [ ] Step 2: docs/design/ui.md: Flow gates, A question, The open question's card: the
  block, the primary button, preparing / missing, the closed line (decided 2026-10-12,
  LAD-27, mockup `task/lad-27/mockup-recommendation.html` v2).
- [ ] Step 3: CHANGELOG.md under `## 0.37.0 (unreleased)`: "The supervisor's
  recommendation on a gate or an agent's question is part of its card (the recommended
  option is the blue button; a disagreement is marked) and of `lado answer`, instead of a
  separate chat message." and "MCP: the lead's tool `recommend`; schema 26 (restart
  running sessions after the upgrade)."
- [ ] Step 4: `make lint`, `openspec validate lead-recommendation --strict`; commit
  "Docs of the lead's recommendation (LAD-27)".

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_flow_runs.py tests/integration/test_human_messages.py`; `uv run
pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py tests/ui/test_needs_you.py
tests/ui/test_flows_tab.py`; `make web`; `openspec validate --specs --strict`. CI runs
`make check` and the smoke. No provider code changes: live tests are not needed.
