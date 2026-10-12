## Context

A gate opens in `runs._act_on_arrival` (status `waiting`): the core stores the gate
(`state.update_run`, its card reaches the UI through the `gates` triggers and the feed),
opens the tmux popup and tells the lead `flow <run>: waiting for the human at <state> (gate
#N)` (`runs._tell_supervisor`: a message from `lado`, or a notice in the result of the
lead's own `flow_advance`). An agent's question is `runtime.ask_human` →
`state.add_question`, a message of kind `question` to `human`; the lead hears nothing of
it. The lead's instructions (`runtime.SUPERVISOR_INSTRUCTIONS`: "Talk to the human only
when a decision is needed (the question and your recommendation)") and kit sdlc's
supervisor paragraph "A gate opens…" make the lead answer the gate's line with a
`send_message(to="human")` overview and recommendation: the second chat entry. Nothing ties
that message to the gate.

Root cause: two producers for one event, the core's gate card and the lead's free message,
with no link between them; the line to the lead invites the second one.

## Options

1. **A core recommendation tied to the gate or question** (chosen with the human): LADO
   asks the lead, the lead answers with a tool, the answer is stored on the gate or
   question and drawn in its card. Long-term cost: one MCP tool, six columns on two tables
   (schema 26), a turn-end check and one UI component; every kit and provider gets it
   alike, and Projects and the desktop app (ROADMAP, later stages) show the same cards.
2. **Instructions only**: tell the lead never to write about a gate. No code, but the
   human loses the opinion they value, and a kit's role text can bring the message back.
   Rejected by the human.
3. **The UI merges the lead's next message into the gate's card** by time or by a gate id
   in its text. A guess from free text (a second source of truth, "events not screens"
   broken in spirit): a message about two gates, or a late one, lands in the wrong card.
   Rejected.

Held against AGENTS.md's Design principles: *Neutral core*: the request is an ordinary
message from `lado` through the queue and the tool is an MCP tool, so every provider gets
both the same way; the turn-end check uses the neutral `TURN_END` (Codex runs no hook for
a turn that ends on an API error: there the state stays `asked` until its next turn end,
said in AGENTS.md). *One source of truth*: the recommendation lives on the gate's or
question's row only; the UI, the API and `lado answer` read it there; the request's
message id is kept with it, never matched by text. *No silent drops*: a request dropped
because its gate closed first is the only drop, and the gate's answer is what the lead
learns next; a recommendation not given shows as such. *Only what is used*: one tool, one
flag (`disagrees`, which the human asked to see), no switch, no history, no length limit
of its own.

## Decisions

- **D1. Storage: columns of `gates` and `messages` (schema 26).** Both tables get
  `recommendation_state TEXT` (NULL: not asked; `asked`, `given`, `missing`),
  `recommendation TEXT`, `recommended_choice TEXT`, `recommendation_disagrees INTEGER NOT
  NULL DEFAULT 0`, `recommended_at TEXT` (UTC, as `created_at`) and
  `recommendation_request INTEGER` (the request's message id; NULL for a notice). On
  `messages` only a question's are used. The existing triggers of both tables journal each
  update, so the feed sends the changed `GateInfo` / `MessageInfo` with no new table or
  trigger. `SCHEMA_VERSION = 26`, a step in `MIGRATIONS` (six `ALTER TABLE … ADD COLUMN`
  per table), `tests/agent_helpers.previous_schema` updated. `state.Gate` and
  `state.Message` get the fields (`GATE_COLUMNS` is `*`; the message's column list in
  `state.py` gets them).
- **D2. The request.** `runs._act_on_arrival` (status `waiting`) replaces the "waiting for
  the human" line with `_ask_recommendation(run, gate, notices)`; `runtime.ask_human`
  calls `runtime.ask_recommendation(session, question)` after `add_question` unless the
  asker is the lead (`SUPERVISOR`). Summary: `recommend on gate #<id>: <run> at <state>`
  or `recommend on question #<id> of <agent>` (cut to `SUMMARY_LIMIT` as
  `_to_supervisor` does). Body: the question; `Options: a, b` (or `Choices:`, or "free
  answer only"); for a gate the note (`Note of <actor> at <state>: <summary>` and its
  body), then `Artifacts it reads:` lines (`runs.gate_reads`, as `lado answer` prints
  them); for a question its details; then one paragraph: `Only the human answers it. Give
  your own view with recommend(gate=<id>, text=..., choice=..., disagrees=...): what you
  would choose and why, the risks, what to check; short, no retelling. Write no separate
  message to the human about it.` Attachments: the gate's note's or the question's
  (their stored records, `state.Attached`). A state function
  `state.ask_recommendation(kind, id, request)` sets `asked` and the request's id in the
  transaction that queues the message (`queue_message` with a callback, or one function
  doing both, the developer's choice within `state.py`); then `runtime._deliver` as
  `post` does. For the lead's own `flow_advance` the text goes into `notices` and the
  state is `asked` with no request id. The lead not running (`NotRunning`): no request,
  the state stays NULL, the gate or question opens as before (today's `_arrived` error
  for a lead that is gone stays as it is for the popup and the rest).
- **D3. The tool.** `mcp_server.recommend(text: str, gate: int | None = None, question:
  int | None = None, choice: str | None = None, disagrees: bool = False) -> str`,
  registered when `me.name == SUPERVISOR`, outside `COMMAND_TOOLS` (a read-only lead has
  it). It calls `runtime.recommend(session, ...)`: exactly one of `gate`, `question`;
  `text.strip()` not empty and at most `MAX_MESSAGE`; the gate by `state.get_gate` (its
  session; open, else `gate #N is closed already: <answer> by <who>` as `runs._changed`
  words it), the choice through `runs.canonical_option`; the question by
  `state.get_message` (kind `question`, open, else `question #N is <state>`; its sender
  not the lead: `question #N is your own`), the choice one of its choices (`question #N
  has no choices` when it has none). Stored by `state.recommend(kind, id, text, choice,
  disagrees)`, one conditional update `WHERE … answer IS NULL` / `question_state =
  'open'`, so an answer between the check and the write refuses it. Result:
  `recommendation on gate #N stored; the human sees it on the gate's card` (question
  alike). Allowed whatever the state was (NULL, asked, missing, given).
- **D4. Drops.** Every transaction that closes a gate (`state.update_run` with `closes`:
  answer, override, cancel) or a question (`reply_to_question`; the close of a forgotten
  agent's questions) also sets the request's message `dropped` when it is still
  `pending` (`state._drop_request(db, request_id)`); one already handed over stays, and
  the lead's late `recommend` is refused with the closed state.
- **D5. Not given.** `state.recommendations_missed(session)` runs in `hooks.main`'s
  `TURN_END` branch for the lead (`SUPERVISOR`) only, after `runtime.turn_failed` (so a
  resume it plans for a transient error is seen) and before the agent is idle and its
  queue handed over, and not when a resume is planned (`agents.resume_at` set): every open
  gate or question of the session with state `asked` whose `recommendation_request` is
  NULL or names a message in `delivered` or `read` becomes `missing`. A notice came in a
  tool's result of a turn, so its turn's end marks it. `state.agent_ended` for the lead
  and `state.stop_session` set every `asked` of the session `missing` in their
  transactions.
- **D6. Resume.** `runs.resume` queues, after `session resumed` and the steps, a request
  (`before_start=True`) for each open gate whose state is not `given`, and sets it
  `asked`; the gate's line in the `session resumed` body adds "a request for your
  recommendation follows". Questions are closed by the stop, so none.
- **D7. API.** `models.RecommendationInfo {state: "asked" | "given" | "missing", text: str,
  choice: str | None, disagrees: bool, by: str | None, at: str | None}`, `by` the agent
  the disagreement is with (the gate's note's `actor`, else none; a question's sender);
  `GateInfo.recommendation` and `MessageInfo.recommendation`: `RecommendationInfo | None`
  (None when not asked and for every message that is no question). Built in
  `models.gate_info` and `message_info`. `make web-types`.
- **D8. The cards.** A new `web/src/Recommendation.tsx`: `Recommendation` (the open
  block: `.rec`, the supervisor's `MiniAvatar`, "Supervisor's recommendation", an orange
  chip "disagrees with <by>" (`.rec-differs`; the block's band `--line`, `--human` when it
  differs), the time, the text as `Body`; `asked` and `missing` as the muted lines of the mockup) and
  `RecommendationLine` (closed: a `<details>` "Supervisor recommended: <choice>" or
  "Supervisor's recommendation", " · disagreed with <by>" in orange, the text inside).
  `GateCard` (also `compact`) and `Question` draw it between the text and the form, and
  make the recommended option's button `.primary` and every other `.quiet` (no
  recommended choice: the first primary, as now). The closed gate's read-only view and the
  closed question card draw the line. Colours only through tokens.
- **D9. `lado answer`.** `cli._show_gate` prints after the note and its artifacts the
  recommendation's line(s) of the spec, marks the option, and the `v` page adds
  `Supervisor's recommendation:` with the whole text after the note. The gate is read
  anew at each show, as now; no redraw while it waits for input.
- **D10. Instructions.** `runtime.SUPERVISOR_INSTRUCTIONS` gets a bullet for `recommend`
  and its rule replaces "Talk to the human only when a decision is needed (the question
  and your recommendation)…" with: for a gate or another agent's question LADO asks for
  your recommendation; answer only with `recommend`, never a separate message to the
  human about it; a short own view (what you would choose and why, risks, where you
  disagree with the step's report or the asking agent, what to check), not a retelling;
  set `disagrees` when you disagree. Talk to the human otherwise only for your own
  decisions (`ask_human`, with your recommendation in it) or a milestone.
  `FLOW_INSTRUCTIONS`' "When a run waits for the human…" says LADO asks for a
  recommendation then. For a read-only lead the same text (the tool is not a command).
- **D11. The popup.** No change of its own: it runs `lado answer`, which D9 covers.
- **D12. Version.** Minor: a new MCP tool and a schema migration; part of 0.37.0, already
  the next minor in CHANGELOG.md. Running sessions must be restarted after the upgrade.

## Risks

- Kit sdlc's paragraph keeps asking the lead for a separate message until the kit's own
  change; LADO's instruction for gates is the later and more specific one. Named in the
  proposal's Out of scope.
- A lead that is busy for long (its own step) leaves the block "preparing" that long; the
  human answers anyway (non-blocking by design).
- The turn-end check must not mark a request handed over in the hook's output of the same
  turn end: it runs before `_idle` hands the queue over, and such a batch is `sent`, not
  `delivered`, until the turn that goes on from it ends (`confirm_channel`).
