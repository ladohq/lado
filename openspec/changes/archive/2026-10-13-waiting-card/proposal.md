Task: LAD-28

## Why

When an agent asks the human a question, or a flow run waits at a gate, the session's chat
shows two places to type: the field in the question's (or the gate's) card and the
composer under the chat ("Write to the supervisor…"). The two look alike, each with its own
Send, and nothing tells the human which one answers. Text typed into the composer goes to
the supervisor as a plain message: the question stays open, in the chat and on Needs you,
and a gate does not move. With several questions open at once (the supervisor's, a
worker's, gates of two runs) the chat has three or four such fields, the open cards float
up as the chat goes on, and each answer the human gives starts the agent's next turn on its
own, which brings the next questions.

The root cause is two facts of today's design (docs/design/ui.md, The human in the
session): an open question or gate is answered only in its own card, which stands where it
was asked and copies the composer's shape; and the core hands each answer to an idle agent
at once (`runtime._deliver`), so two answers to one agent are two turns.

## What Changes

- **UI: one card for what waits** (`web/src/WaitingCard.tsx`, new). Above the composer of
  a session's chat stands one card while anything waits for the human there: the open
  questions of the session's agents and its open gates. It has a tab per agent (all its
  open questions) and a tab per open gate (by its run); each tab in that agent's avatar
  colour or that run's colour, with its number of open items. The card's ground is the UI's
  "waits for you" orange. Tabs switch for real; the human answers one tab when ready; the
  others wait. With nothing waiting there is no card. Approved mockup:
  `task/lad-28/mockup-question-card-final.html`.
- **An agent's tab**: its open questions, numbered when more than one; per question its
  choices (one is picked, a second click unpicks), **Other…** (an own answer, only for a
  question that takes one) and **Skip** (a dismissal, with an optional comment). One button,
  **Send answer to <agent>** / **Send <n> answers to <agent>**, on once each question of the
  tab has a choice, an own answer or Skip ("<k> of <n> answered" beside it until then).
- **A gate's tab**: the gate's question, the note that led to it and the artifacts it reads
  (as its card shows them today), the comment for the next step and the gate's own buttons,
  which answer at once, as today.
- **The card is at most half the chat's height**: its questions scroll inside, its tabs and
  its Send row always show. An icon at the right of the tabs expands it over the whole
  window (the rest dimmed); the other icon or Esc folds it back; it folds itself once
  nothing waits.
- **The chat's feed**: an open question or gate is one quiet line where it was asked
  ("supervisor asked: <question> ↓", "Gate #N <run> · <state> waits: <question> ↓"), whose
  arrow selects its tab and marks the question. Answered, the question is its closed card
  as today; a closed gate its line as today. The hint over the composer ("Gate #id waits:
  answer on its card") goes.
- **Needs you**: each session's open questions and gates as the same card, answered in
  place, the session's name and "In the chat" over it; agents waiting in their terminal
  stay rows as today.
- **A stopped session**: its gates stay in the card with their buttons off and "The session
  is stopped: resume it to answer."
- **Skipped**: a question skipped in the card is a dismissal in the core; the UI calls it
  "skipped" everywhere (the closed card's "You · skipped", the late line "You skipped
  question #N").
- **Core and API: the answers of a tab are handed over together.** A new
  `runtime.answer_questions(session, replies)` answers several open questions of one agent
  in one transaction and hands them to the agent once, so an idle agent gets them in one
  batch and starts one turn. `POST /api/sessions/{name}/answers` takes the tab's replies.
  It replaces `POST …/questions/{id}/answer` and `…/dismiss`, which nothing calls once the
  card sends a tab; `runtime.answer_question` and `runtime.dismiss_question` stay as
  one-reply calls of it.
- New minor release (0.37.0, already the next version): an API change. No schema
  migration, no MCP tool change.

## Scope

- `web/src/WaitingCard.tsx` and its tests; `Chat.tsx` (feed lines, the card above the
  composer, the hint removed, links to an open item select its tab), `Question.tsx` (the
  open card's form removed; "skipped"), `GateCard.tsx` (its note and reads shared with the
  gate's tab; the open gate's row in the chat removed; the compact card of a run's page in
  Flows kept), `NeedsYou.tsx`, `waiting.ts`, `api.ts`, `styles.css`, `tokens.css` if a
  token is added (none planned).
- `runtime.answer_questions`, `state.reply_to_questions`; `runtime.answer_question` and
  `runtime.dismiss_question` become one-reply calls of them.
- `POST /api/sessions/{name}/answers` (`models.Replies`, `models.Reply`); the two old
  endpoints removed; `make web-types`.
- Docs: `docs/design/ui.md` (The human in the session: Flow gates, A question, The open
  question's card, Answer in the question card; Structure: Needs you; Look), AGENTS.md
  (Layout: the server's endpoints; How agents talk: the human's answers), CHANGELOG.md.

## Out of scope

- Several questions in one `ask_human` call (the research's "questions in a batch at the
  source"): the card groups an agent's open questions whatever calls asked them, so no MCP
  change is needed now; an agent asking its questions one after another in one turn gets
  them answered together already.
- A comment with a choice: the approved card picks a choice or an own answer, not both
  (the human approved the mockup without it); the API keeps `text` with `choice` for later
  use and the core's rule is unchanged.
- Holding an answer until the agent's other questions are answered (discussed, refused:
  hidden behaviour, and labels to explain it confused).
- Blocking the composer while something waits (discussed, refused: the human must be able
  to write "stop" or ask back at any time).
- Folding the card to its tabs (discussed, refused as crude; expanding replaces it).
- The composer of an agent's page in Agents: it shows no questions; unchanged.
- Agents waiting in their terminal: not in the card (they are answered in the terminal);
  Needs you and the team's chips show them as today.
- `lado answer`, the tmux popup and the gate card of a run's page in Flows: unchanged.

## Acceptance criteria

- AC-1: While one or more questions or gates are open in a session, its chat shows exactly
  one card above the composer, with a tab per agent that asked and a tab per open gate, in
  the order their first item was asked; with nothing open there is no card.
- AC-2: A tab shows the agent's avatar letter and colour (a gate's tab the Flows icon and
  its run's colour, its top dashed), the agent's name (the run's), and the number of its
  open items in a muted badge; the card's ground is the "waits for you" orange.
- AC-3: Clicking a tab shows its items; the shown tab stays when items come or go on other
  tabs; when it empties, the first tab shows.
- AC-4: On an agent's tab, Send is off until each question has a choice, an own answer
  (Other…, not blank) or Skip; with more than one question "<k> of <n> answered" stands
  beside it.
- AC-5: Send answers every question of the tab in one request; the agent, idle, gets all
  the answers in one hand-over (one paste or one hook output), each as `Answer to #<id>: …`
  or `Dismissed #<id>`, and starts one turn.
- AC-6: If any question of the tab was closed meanwhile (answered elsewhere, its agent
  gone), the request changes nothing and the card says why; the tab then shows only what
  is still open.
- AC-7: A gate's tab answers the gate with its buttons and comment at once, through the
  same core as today; the run moves on and the tab goes.
- AC-8: The card is at most half the chat's height, its list scrolls inside, and its tabs
  and Send row stay in view; the expand icon shows it over the whole window, Esc or the
  fold icon brings it back, and it folds itself when the last item is answered.
- AC-9: In the feed, each open question and gate is one quiet line whose arrow selects its
  tab and marks the item; answered, the question shows its closed card ("You · answered",
  or "You · skipped" with the comment), and no hint stands over the composer.
- AC-10: Needs you shows, per session, the same card with the same behaviour; a link to an
  open question or gate (Needs you, a notification) opens the chat with its tab selected.
- AC-11: In a stopped session the card keeps its gates' tabs with the buttons off and "The
  session is stopped: resume it to answer."
- AC-12: docs/design/ui.md, AGENTS.md and CHANGELOG.md say so; vitest, the unit, the
  integration (fake agent) and the UI e2e tests named in tasks.md pass, with screenshots of
  the card, its expanded view, the feed and Needs you.

## Impact

- `src/lado/runtime.py`, `src/lado/state.py`, `src/lado/server/app.py`,
  `src/lado/server/models.py`; `web/src/WaitingCard.tsx` (new), `Chat.tsx`, `Question.tsx`,
  `GateCard.tsx`, `NeedsYou.tsx`, `waiting.ts`, `api.ts`, `styles.css`; `web/openapi.json`,
  `web/src/api.gen.ts`.
- Tests: `tests/test_runtime.py`, `tests/test_state.py`, `tests/test_server_messages.py`,
  `tests/integration/test_human_messages.py`, `web/src/WaitingCard.test.tsx` (new),
  `web/src/Chat.test.tsx`, `web/src/NeedsYou.test.tsx`, `tests/ui/test_chat.py`,
  `tests/ui/test_needs_you.py`.
- `runtime.py` changes: the reviewer names it; the change touches no provider, so the live
  tests are not needed for it.

## Decisions for the record

- Scale full: new behaviour across the core, the API and the UI, with the design settled
  in seven rounds with the human (mockups `mockup-answer-fields.html`,
  `mockup-held-answers.html`, `mockup-two-concepts.html`, `mockup-questions-in-input.html`,
  `mockup-question-tabs.html`, `mockup-question-card-details.html`,
  `mockup-question-card-final.html`; research `research-answer-ux.md`).
- The card's items come from what already says "waits for you": open questions from the
  live list `waiting` (`state.waiting_items`, the one source of Needs you), open gates from
  the session's gates list (whole, also in a stopped session). No second list.
- One endpoint for a tab's replies, all or nothing: a partial batch would hand the agent
  half the answers and start the turn this change is to avoid.
- The two old question endpoints go: nothing calls them once the card sends a tab ("Only
  what is used"); the two runtime functions stay as one-reply calls, one path for both.
- The design doc is `docs/superpowers/specs/2026-10-13-waiting-card-design.md`; the plan
  `docs/superpowers/plans/2026-10-13-waiting-card.md`.
