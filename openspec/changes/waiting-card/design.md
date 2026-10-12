## Context

The human answers an agent's question (`ask_human`, a message of kind `question` to
`human`) in the question's card in the chat (`web/src/Question.tsx`: choices, a field, Send,
Dismiss) and a gate in the gate's card (`web/src/GateCard.tsx`: a comment field and the
options). Each card stands in the feed where it was asked. Under the feed the composer
(`Composer.tsx`) writes a plain message to the supervisor; over it, `Chat.tsx`'s
`GateHint` names the first open gate only. Needs you (`NeedsYou.tsx`) shows the same two
cards, answered in place, from the live list `waiting` (`state.waiting_items`, served as
`GET /api/waiting`, reloaded whole on each change, `live.ts`).

Answers go through `POST …/questions/{id}/answer` and `…/dismiss` (`server/app.py`) to
`runtime.answer_question` / `runtime.dismiss_question`, which queue the reply and set the
question's outcome in one transaction (`state.reply_to_question`) and then hand the agent
its queue at once if it is idle (`runtime._deliver` → `hand_over`). Gates go through
`POST …/gates/{id}/answer` to `runs.answer_text`.

Root causes: the open card copies the composer's shape and stands where it was asked, so
the chat has as many answer fields as open items and they float up; and each reply is
handed over on its own, so two replies to one idle agent start two turns.

## Options

1. **One waiting card above the composer, a tab per agent and per gate, a tab's replies
   handed over together** (chosen, the human's design after seven rounds). The cards in the
   feed become lines and closed cards; the composer stays a plain message. Long-term cost:
   one new component and one new core call; the old open-card form and two endpoints go.
2. **Hints only** (a band over the composer naming what waits, the card's field labelled
   with its question). Cheap, but the chat keeps one field per open item and one turn per
   answer. Refused by the human ("labels confuse more").
3. **The composer answers** (cards without fields; the composer in a reply mode, or a
   message to an agent closes its open questions). One field, but a choice and its text sit
   in two places, Needs you would need a second way to answer, and a message that asks back
   would close the questions. Refused by the human.
4. **Hold replies in the core until the agent's last question is answered.** Hidden
   behaviour that needs labels to explain; refused by the human.

Held against ROADMAP.md: Stage 7 (the desktop app runs the same UI; the card is a plain
component of it), Stage 8 (an ACP runtime's questions would be the same `question`
messages and land on the same tabs), Stage 9 (trackers: nothing). Design principles:
*Neutral core*: the batch is the queue's own hand-over, the same for every provider (typed,
or a turn-end hook's output); *One source of truth*: open questions from `waiting_items`
(Needs you's list), gates from the session's gates, the run colour from `Team.runColours`,
the avatar colour from `FeedRow.avatar`; *No silent drops*: a batch with one closed
question is refused whole with the core's reason, nothing half sent; *Only what is used*:
no MCP change, no schema change, the two endpoints nothing calls any more are removed.

## Decisions

- **D1. `runtime.answer_questions(session, replies) -> str`.** `replies` is a sequence of
  `runtime.HumanReply(question: int, choice: str | None = None, text: str | None = None,
  skip: bool = False)`. Refused with `LadoError`, before anything changes: an empty list
  (`no answers`), a question twice (`question #<id> is answered twice`), a question that is
  no question of the session (`no question #<id> in session <s>`) or not open (`question
  #<id> is <state>`), questions of two agents (`answers go to one agent at a time:
  #<a> is <x>'s, #<b> is <y>'s`), and per reply the rules `answer_question` and
  `dismiss_question` have today (a choice the question lacks, no choice and no text, own
  words for a question without a free answer, a body over `MAX_MESSAGE`, `skip` with a
  choice: `question #<id>: skip takes no choice`). Each reply's summary and body are built
  as today (`Answer to #<id>: <choice>` and `text` as its body; own words by
  `_human_text(text, prefix)`; `Dismissed #<id>` and the comment as its body), by one helper
  `_reply_of(question, reply) -> state.Reply`. The session must run (`running_session`).
- **D2. `state.reply_to_questions(session, replies: Sequence[state.Reply]) -> list[int]`**,
  `state.Reply(question: int, summary: str, body: str, choice: str | None, outcome: str)`:
  one `BEGIN IMMEDIATE` transaction that checks the asker runs (`_check_running`, as
  `reply_to_question` does) and each question is still open, inserts each reply (as
  `reply_to_question` does) and sets each outcome and `answered_by`. A question that is no
  longer open raises `state.QuestionClosed(question, question_state)` after a rollback;
  `runtime` turns it into `question #<id> is <state>`. `state.reply_to_question` becomes
  `reply_to_questions` with one reply (one writer).
- **D3. One hand-over.** After the transaction `answer_questions` calls
  `_deliver(session, asker, last_reply_id)` once and returns its result. `hand_over` takes
  every pending message of the agent (`state.take_pending`), so an idle agent with no
  unconfirmed batch gets all the replies in one paste (`tmux.send_text` once) or one
  turn-end hook output. A busy agent gets them together at its turn's end, as any queue.
- **D4. `runtime.answer_question` and `runtime.dismiss_question` stay as one-reply
  wrappers** of `answer_questions` (`answer_questions(session, [HumanReply(question,
  choice, text)])`, `[HumanReply(question, text=text, skip=True)]`), so there is one path
  and their many tests keep their meaning. The endpoints `POST
  /api/sessions/{name}/questions/{id}/answer` and `…/dismiss` and `api.ts`'s
  `answerQuestion` / `dismissQuestion` are removed: nothing calls them once the card sends
  a tab; their server tests move to `POST …/answers`.
- **D5. `POST /api/sessions/{name}/answers`**, body `models.Replies {answers:
  list[models.Reply]}`, `models.Reply {question: int, choice: str | None = None, text: str |
  None = None, skip: bool = False}`, under `Guard.changes`, through `core(...)` (400 with the
  core's text, 503 under another schema, 404 for an unknown session), answers `Sent`.
  `make web-types`; `api.ts` gets `answerQuestions(session, answers: Reply[])`.
- **D6. `web/src/WaitingCard.tsx`**: `WaitingCard({session, questions, gates, runs,
  stopped, focus})`. `questions`: the session's open questions (`MessageInfo`, kind
  `question`, state `open`); `gates`: its open gates (`GateInfo`, `answer === null`);
  `runs`: the session's runs for `runColours`; `focus`: `{key: string, item: number, at:
  number} | null`, set by the feed's arrows and by links. Tabs (`waitingTabs(questions,
  gates)`, a pure function, exported for tests): one per question sender, holding its
  questions by id, and one per gate, keyed `agent:<name>` / `gate:<id>`, ordered by their
  first item's `created_at` (then id). The shown tab is component state: kept while it
  exists, else the first; `focus` selects its tab and marks its item (`.marked`, 1.5 s,
  scrolled into view in the list).
- **D7. Picks.** Component state `picks: Record<number, Pick>` with `Pick = {choice:
  string} | {own: string} | {skip: string}` (the text of Other… or Skip's comment), kept
  per question id across tab switches and dropped for ids no longer open. A tab is ready
  when each question has a choice, an `own` that is not blank, or `skip`. Send posts
  `answerQuestions` with `{question, choice}`, `{question, text}` or `{question, skip:
  true, text}` (no `text` when the comment is blank); while it runs the tab's controls are
  off; a refusal shows as `.field-problem` on the panel and the picks stay. Nothing shows
  ahead of the server: the tab goes when `waiting` brings the questions closed.
- **D8. The gate's tab** reuses `GateCard.tsx`'s pieces: `Note` and `Reads` are exported,
  and a new `GatePanel({session, gate, stopped})` holds the question, the note, the reads,
  the comment field and the option buttons (`LABELS`, `answerGate`) — what `GateCard` drew
  for an open gate. `GateCard` with `compact` (a run's page in Flows) stays and uses
  `GatePanel`'s form. `GateRow` (the open gate's row in the chat and on Needs you) is
  removed; the closed gate's `GateLine` stays.
- **D9. Look** (`styles.css`, tokens only; mockup `mockup-question-card-final.html`):
  `.waiting-card` in the chat's column (the `.chat > *` side margins), `flex: none`,
  `max-height: 50%` of `.chat`, a column of `.waiting-tabs` and `.waiting-panel`; the panel
  `--human-ground` with a 1 px `--human` frame, radius `0 10px 10px 10px`, padding 14×16;
  its list `overflow: auto`, the Send row (`.waiting-send`, a `--line`-like top rule) always
  shown. A tab: 36 px, a 3 px top in `--who` (solid; dashed for a gate), 9 px top radius,
  `--raised` and `--muted` when not shown; shown: `--human-ground` tinted with 10 % of
  `--who`, `--ink`, 600, its sides `--human`. `--who` is `var(--avatar-<n>)` (FeedRow's
  `avatar(name).colour`) or `var(--run-<n>)` (`runColours`, `--line` until the runs load).
  The avatar 20 px, radius 6, `--on-avatar` letter; the gate's Flows icon in `--who`; the
  badge 18 px, `--muted` on 18 % `--muted`. Options: 32 px buttons, picked `--action` on
  `--action-ground`; Other… and Skip `--muted`. The expand and fold buttons: 36 px, a 20 px
  icon (two new icons in `icons.tsx`, `ExpandIcon`, `CollapseIcon`), the UI's Tooltip.
- **D10. Expanded.** Component state `expanded`. Expanded, the card renders through a
  portal into `document.body` as `role="dialog" aria-modal="true" aria-label="What waits
  for you in <session>"`, fixed at 16 px from the window's edges over a `--scrim` ground,
  its list filling the height; focus moves to the shown tab; Esc and the fold icon set it
  back and return focus to the expand icon; it is set back when no tab is left.
- **D11. The feed** (`Chat.tsx`): `Rows` draws an open question as `OpenLine` (a
  `.chat-quiet` line: mini avatar, "<agent> asked: <summary>", a `↓` button "Answer
  question #<id>", time) and an open gate as the same line ("Gate #<id> <run> · <state>
  waits: <question>"). The arrow sets `focus`. `go(anchor)` for `#message-<id>` or
  `#gate-<id>` of an open item sets `focus` instead of scrolling. `GateHint` is removed.
  The card sits between the feed and the composer, built from `waiting` (this session's
  questions) and `loaded.gates` (open ones); Chat watches `waiting` and `runs`.
- **D12. Skipped.** The UI words a dismissal "skipped": `Given`'s head "You · skipped",
  `LateReply` "You skipped question #N", `Answer`'s quiet line "You skipped question #N";
  the core's `Dismissed #<id>` and `question_state: dismissed` are unchanged.
- **D13. `Question.tsx`** keeps the closed card only: the open form (choices, field, Send,
  Dismiss) and its `act` / `submit` go; the component is drawn only for questions not open.
- **D14. Needs you**: per session, the session's name, "In the chat" and a `WaitingCard`
  from that session's items in `waiting` (`stopped={false}`: `waiting_items` has no stopped
  session), each section watching its session's `runs` for the colours; agents in `waiting`
  stay `WaitingAgent` rows under the card. `waiting.ts`'s targets stay `#message-<id>` /
  `#gate-<id>`, which D11 turns into a selected tab.
- **D15. Version.** 0.37.0 (already the next minor): an API change. No schema change, no
  MCP tool change; no provider code changes, so no live test is needed.
- **D16. Test layers.** Unit (`tests/test_state.py`, `tests/test_runtime.py`): the batch's
  checks, its one transaction, its one `send_text` with both lines; in process
  (`tests/test_server_messages.py`): the endpoint; integration
  (`tests/integration/test_human_messages.py`, `-m integration`, fake agent): two
  questions asked by the agent, answered through the endpoint, both lines reach it and both
  questions are answered; vitest (`WaitingCard.test.tsx`, `Chat.test.tsx`,
  `NeedsYou.test.tsx`): tabs, order, colours, picks, Send, refusals, gate tab, stopped,
  expand, focus, feed lines; UI e2e (`tests/ui/test_chat.py`, `tests/ui/test_needs_you.py`,
  `-m ui`): the card in a browser, its expanded view, Needs you, screenshots.

## Risks / Trade-offs

- A question the card shows but the window of messages has not loaded: its feed line is
  missing until its page loads, the tab is there (it comes from `waiting`). Accepted.
- `waiting` reloads whole on each change: a busy session reloads it often. Already so for
  Needs you and the rail's count.
- Removing the two endpoints breaks a page of an older UI kept open across an upgrade;
  `lado update` restarts the server and the page reloads its bundle. Accepted.
- The comment with a choice is no longer offered (Out of scope in the proposal).
