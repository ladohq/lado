Task: LAD-27

## Why

Almost every flow gate makes two entries in the session's chat: the gate's card, and right
under it a message from the supervisor to the human with an overview of the gate and its
recommendation. The human finds the supervisor's own view useful and wants to keep it, but
as one entry with the gate, and under LADO's control rather than by habit.

Root cause: two independent producers answer one event. The core opens the gate (its card
in the feed, `runs._act_on_arrival`) and, in the same move, sends the lead a line from
`lado`, "flow <run>: waiting for the human at <state> (gate #N)". The lead's instructions
then make it write to the human: LADO's own ("Talk to the human only when a decision is
needed (the question and your recommendation)", `runtime.SUPERVISOR_INSTRUCTIONS`) and
kit sdlc's supervisor paragraph "A gate opens…". Nothing ties that message to the gate, so
the UI can only show it as a second entry. The same happens with a worker's `ask_human`
question when the lead comments on it.

## What Changes

- **The lead recommends on every question to the human** (a core mechanism, the same with
  every kit and provider): when a flow gate opens (approval, choice, loop limit) or an
  agent other than the lead asks the human (`ask_human`), LADO asks the lead for its
  recommendation with one message from `lado` (the question, the options, the note or
  details, the artifacts) instead of today's "waiting for the human at …" line; when the
  lead's own `flow_advance` opened the gate, the request comes in the tool's `notices`.
- **A new MCP tool of the lead, `recommend(text, gate=N | question=N, choice=None,
  disagrees=False)`**: the lead's own view, Markdown, optionally the option it recommends,
  and whether it disagrees with the agent whose report led to the gate or who asks. It may
  be replaced until the human answers; after that it is refused. Given to the lead only
  (also a read-only one: it changes nothing in the repository). No length limit of its
  own (a message's, 8000 characters); the instructions ask for a short view.
- **Stored with the gate or the question** (schema 26: the recommendation's state, text,
  chosen option, time and the request's message id on `gates` and `messages`), so it
  reaches the UI through the existing change feed, in `GateInfo` and `MessageInfo` as
  `recommendation`.
- **Shown as one entry**: a "Supervisor's recommendation" block inside the gate's and the
  question's card (chat, Needs you, a run's page in Flows), between the question's text
  and the answer, shown whole; the recommended option's button is the primary (blue) one
  and the others quiet, with no extra label. A disagreement is marked in orange in the
  block's head, "disagrees with <agent>". While it is asked and not given: "Supervisor is
  preparing a recommendation…", and the human may answer at once; when the lead's turn
  ended without it, or the lead ended: "The supervisor gave no recommendation". A closed
  card keeps it as one quiet line naming the option, the text on a click. `lado answer`
  and the tmux popup print it with the gate.
- **Housekeeping of the request**: a request still in the lead's queue is dropped when its
  gate or question closes first; when the lead ends (`lado stop` too) an unanswered request
  counts as not given, and a resume asks the new lead again for each open gate without a
  given recommendation.
- **LADO's lead instructions**: for a gate or another agent's question, answer only with
  `recommend`, no separate message to the human; give an independent view (what it would
  choose and why, risks, where it disagrees with the step's report, what to check), not a
  retelling of the note.
- Docs: AGENTS.md, docs/design/ui.md, CHANGELOG.md.

## Scope

The core (`runs.py`, `runtime.py`, `state.py` with schema 26, `hooks.py`'s turn end,
`mcp_server.py`), the API models, the web UI's gate and question cards, `lado answer` and
the popup, LADO's lead instructions, docs.

## Out of scope

- **Kit sdlc's paragraph "A gate opens…"**: shortened in the kit's own repository as a
  separate change; until then the kit's role text and LADO's instructions say different
  things, and LADO's later, more specific instruction is the one the lead is told to
  follow for gates.
- **A switch to turn recommendations off** per session or kit: the human decided against
  one for now (only what is used).
- **The lead's own `ask_human` questions**: no request (it would recommend to itself); a
  "recommended choice" of `ask_human` is not added.
- **A history of replaced recommendations**: the latest replaces the earlier one in place.
- **Live refresh of `lado answer`'s prompt**: the recommendation is printed at each show of
  the gate (after `v` and after each answer), not redrawn while it waits for input.
- **A "recommended" label on the button** (the first mockup's variant A): the human found it odd;
  the blue button alone shows the recommendation, also when the lead disagrees.
- **The option named in the open card's block head ("→ Reject")**: the blue button says it
  already (the human's decision); the option is named only where no button is, the closed
  card's line and the terminal.
- **A length limit or Show more for the recommendation**: the human prefers a short text
  by instruction, shown whole; a second scroll inside the feed was rejected too.
- **Detecting a disagreement by itself**: LADO keeps no structured opinion of the step's
  agent (a note is text, a question has no preferred choice); only the lead knows, so it
  says so with `disagrees`.

## Acceptance criteria

- AC-1: When a flow gate opens (approval, choice or loop limit) while the lead runs, the
  lead gets one request from `lado` (or one notice in its own `flow_advance` result) that
  names the gate, its question, options and note and carries the note's artifacts; it no
  longer gets "waiting for the human at …".
- AC-2: When an agent other than the lead calls `ask_human`, the lead gets one request
  for that question; the lead's own question gets none.
- AC-3: `recommend` stores the text, the optional choice and `disagrees` on the open gate
  or question, replaces an earlier one, and is refused for a closed one, an unknown or
  another session's id, a choice that is not an option, both or neither of `gate` and
  `question`, an empty text or one over a message's limit, and the lead's own question; no
  worker has the tool.
- AC-4: A request still pending in the lead's queue is dropped when its gate or question
  closes (answered, dismissed, overridden, cancelled, closed by its agent's end).
- AC-5: When the lead's turn ends after it got a request and gave no recommendation (not
  a turn LADO will resume after a temporary error), or the lead ends, the gate or question
  shows "The supervisor gave no recommendation"; a later `recommend` still replaces that.
- AC-6: The open gate and question cards (chat, Needs you, Flows) show the block: the
  recommendation's whole text and time, "disagrees with <agent>" in orange when flagged,
  and the recommended option's button as the only primary one; "Supervisor is preparing a
  recommendation…" while asked; nothing when never asked. The human can answer in every
  state.
- AC-7: A closed card shows "Supervisor recommended: <option>" (or "Supervisor's
  recommendation" without an option) as one quiet line whose text opens on a click.
- AC-8: `lado answer` and the popup print the recommendation's line, mark the recommended
  option, and show the full text under `v`.
- AC-9: After `lado stop` and a resume, the new lead gets a request for each open gate
  without a given recommendation.
- AC-10: LADO's lead instructions name `recommend`, tell the lead not to write a separate
  message to the human for a gate or another agent's question, to keep the view short (no
  retelling) and to set `disagrees` when it disagrees.
- AC-11: AGENTS.md, docs/design/ui.md and CHANGELOG.md say so; the tests named in the
  plan pass.

## Impact

- `src/lado/state.py` (schema 26, migration, the turn-end check, drops), `runs.py`,
  `runtime.py`, `hooks.py`, `mcp_server.py`, `cli.py`, `server/models.py`,
  `web/openapi.json`, `web/src/api.gen.ts`, `web/src/GateCard.tsx`, `Question.tsx`, a new
  `web/src/Recommendation.tsx`, `styles.css`, tests at each layer, AGENTS.md,
  docs/design/ui.md, CHANGELOG.md, `tests/agent_helpers.previous_schema`.
- Minor version: an MCP tool and a schema migration; part of 0.37.0 (already the next
  minor). Running sessions must be restarted after the upgrade.

## Decisions for the record

- Scale full: new behaviour across the core, an MCP tool, a migration and the UI; review
  breadth first.
- Root cause, options and the chosen one are in `design.md` (Options); the human chose
  the core mechanism in the session's chat (#4002–#4030), the look in #4038, #4049.
- Engineering decisions D1–D12 in `design.md`: storage as columns of `gates` and
  `messages` (the feed carries them with no new table), the request as a message from
  `lado` through the usual queue, the turn-end check next to the reply check, the drops in
  the closing transactions, the tool outside `COMMAND_TOOLS`.
- Test layers: unit for state, runs, runtime, the MCP tool, the CLI and the API;
  integration with the fake agent for the request, its drop and the turn-end check (they
  cross hooks, `lado mcp` and the queue); vitest for the cards; UI e2e for the block in a
  real browser with screenshots.
