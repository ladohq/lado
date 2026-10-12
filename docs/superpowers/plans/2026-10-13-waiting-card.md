# One card for what waits: implementation plan

**Goal:** a session's open questions and gates are answered in one tabbed card above the
composer (a tab per agent, a tab per gate), an agent's tab sends its answers together and
the agent gets them in one hand-over; the feed shows open items as lines; Needs you shows
the same card (LAD-28).

**Architecture:** the core gets `runtime.answer_questions` (one transaction,
`state.reply_to_questions`, one `_deliver`) and the server `POST /api/sessions/{name}/answers`;
the UI gets `web/src/WaitingCard.tsx`, fed by the live list `waiting` (questions) and the
session's gates, placed by `Chat.tsx` between the feed and the composer and by
`NeedsYou.tsx` per session.

**Tech stack:** Python 3.10+ (FastAPI, pydantic, SQLite), React + TypeScript (vitest),
pytest (unit, integration with the fake agent, UI with Playwright).

**Spec:** `openspec/changes/waiting-card/` (proposal, deltas `question-answers` and
`chat-question-card`, `design.md` D1–D16). **Design doc:**
`docs/superpowers/specs/2026-10-13-waiting-card-design.md`. **Mockup:** run artifact
`task/lad-28/mockup-question-card-final.html` (interactive; its CSS is the look to build).

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-28)` at the end). Files are edited with the edit tools.

## Global constraints

- Texts (exact): `Send answer to <agent>`, `Send <n> answers to <agent>`, `<k> of <n>
  answered`, `Other…`, `Skip`, `Your own answer`, `Why you skip it (optional)`, `Comment for
  the next step (optional)`, `The session is stopped: resume it to answer.`, `<agent> asked:
  <summary>`, `Gate #<id> <run> · <state> waits: <question>`, `You · skipped`, `You skipped
  question #<id>`, the expand icon's name and tooltip `Expand the card`, the fold icon's
  `Collapse the card`, the dialog's name `What waits for you in <session>`, Needs you's
  link `In the chat`.
- Core refusals (exact): `no answers`; `question #<id> is answered twice`; `no question
  #<id> in session <s>`; `question #<id> is <state>`; `answers go to one agent at a time:
  #<a> is <x>'s, #<b> is <y>'s`; `question #<id>: skip takes no choice`; and today's texts
  of `answer_question` / `dismiss_question` for a bad choice, no answer, own words without
  a free answer, a body over the limit.
- The card's tab order: first item's `created_at`, then id. Tab keys `agent:<name>`,
  `gate:<id>`.
- Colours only through tokens (`--human`, `--human-ground`, `--avatar-<n>`, `--run-<n>`,
  `--raised`, `--muted`, `--ink`, `--action`, `--action-ground`, `--scrim`, `--line`,
  `--on-avatar`); no new token.
- Card height at most 50 % of `.chat`; expanded: fixed, 16 px from the window's edges.
- No schema change, no MCP change; version 0.37.0 (CHANGELOG `## 0.37.0 (unreleased)`).
- `make web-types` after the API models change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.

## Review focus

1. A question answered elsewhere (another tab, Needs you) while its tab has picks: the
   batch is refused whole, the refusal shows, and once `waiting` reloads the tab shows only
   what is open, with the remaining picks kept — Task 4's refusal test and Task 1's
   closed-meanwhile test.
2. An agent busy when the tab is sent: nothing is typed now; at its turn's end all the
   replies come in one hand-over, never one per turn — Task 1's busy-agent test.
3. Typing in an Other… field must not lose the caret or the focus when the card re-renders
   (the mockup re-rendered whole; the component must not) — Task 4's typing test.
4. Esc while the card is not expanded must do nothing to the card and must not reach the
   composer as a fold — Task 5's Esc test; Esc inside an expanded card's text field folds
   it too.
5. A gate of a run whose snapshot cannot be read (`problem`): its tab shows the problem
   line as the card did, and the buttons work as before — Task 3's problem test.

---

### Task 1: The core answers several questions together (D1–D4)

**Files:** modify `src/lado/state.py` (next to `reply_to_question`), `src/lado/runtime.py`
(next to `answer_question`); test `tests/test_state.py`, `tests/test_runtime.py`.

**Produces:** `state.Reply(question: int, summary: str, body: str, choice: str | None,
outcome: str)` (frozen dataclass); `state.QuestionClosed(Exception)` with `.question: int`,
`.question_state: str`; `state.reply_to_questions(session: str, replies:
Sequence[Reply]) -> list[int]`; `runtime.HumanReply(question: int, choice: str | None =
None, text: str | None = None, skip: bool = False)`; `runtime.answer_questions(session:
str, replies: Sequence[HumanReply]) -> str`. `state.reply_to_question` is removed (its
callers were `runtime._reply` only); `runtime.answer_question` and
`runtime.dismiss_question` keep their signatures and call `answer_questions`.

- [ ] **Step 1: Failing tests** in `tests/test_runtime.py` (tmux is the recorder there):

```python
def test_two_answers_reach_an_idle_agent_in_one_paste(session, sent):
    first = ask(session, "w1", "Short or long?", ["short", "long"])
    second = ask(session, "w1", "Which branch?")  # free answer
    runtime.answer_questions(
        "s", [runtime.HumanReply(first, "short"), runtime.HumanReply(second, None, "main, then rebase")]
    )
    pastes = [text for target, text in sent if target == ("s", "w1")]
    assert len(pastes) == 1
    assert f"[from human] Answer to #{first}: short" in pastes[0]
    assert f"[from human] Answer to #{second}: main, then rebase" in pastes[0]
    assert [state.get_message("s", q).question_state for q in (first, second)] == ["answered"] * 2


def test_a_skip_is_a_dismissal_with_its_comment(session, sent):
    first = ask(session, "w1", "Short or long?", ["short", "long"])
    second = ask(session, "w1", "Which branch?")
    runtime.answer_questions(
        "s", [runtime.HumanReply(first, "short"), runtime.HumanReply(second, text="later", skip=True)]
    )
    reply = state.list_messages("s")[-1]
    assert (reply.summary, reply.body, reply.reply_to) == (f"Dismissed #{second}", "later", second)


def test_a_batch_with_a_closed_question_changes_nothing(session, sent):
    first = ask(session, "w1", "Short or long?", ["short", "long"])
    second = ask(session, "w1", "Which branch?")
    runtime.answer_question("s", second, None, "main")
    before = state.list_messages("s")
    with pytest.raises(runtime.LadoError, match=f"question #{second} is answered"):
        runtime.answer_questions("s", [runtime.HumanReply(first, "short"), runtime.HumanReply(second, None, "x")])
    assert state.list_messages("s") == before
    assert state.get_message("s", first).question_state == "open"


@pytest.mark.parametrize(
    "replies, error",
    [
        ([], "no answers"),
        (lambda q, _: [runtime.HumanReply(q, "short"), runtime.HumanReply(q, "long")], "is answered twice"),
        (lambda q, other: [runtime.HumanReply(q, "short"), runtime.HumanReply(other, "yes")], "answers go to one agent at a time"),
        (lambda q, _: [runtime.HumanReply(q, "short", skip=True)], "skip takes no choice"),
        (lambda q, _: [runtime.HumanReply(q, "maybe")], 'has no choice "maybe"'),
    ],
)
def test_a_batch_the_core_refuses_changes_nothing(session, sent, replies, error):
    mine = ask(session, "w1", "Short or long?", ["short", "long"])
    other = ask(session, "w2", "Ship?", ["yes", "no"])  # another running worker
    before = state.list_messages("s")
    given = replies if isinstance(replies, list) else replies(mine, other)
    with pytest.raises(runtime.LadoError, match=re.escape(error)):
        runtime.answer_questions("s", given)
    assert state.list_messages("s") == before


def test_a_busy_agent_gets_the_batch_at_its_turns_end(session, sent):
    first = ask(session, "w1", "Short or long?", ["short", "long"])
    second = ask(session, "w1", "Which branch?")
    state.set_status("s", "w1", state.BUSY)
    runtime.answer_questions("s", [runtime.HumanReply(first, "short"), runtime.HumanReply(second, None, "main")])
    assert [t for t in sent if t[0] == ("s", "w1")] == []
    hooks.handle(turn_end("s", "w1"))  # the existing helper of a Stop hook in this file
    assert len([t for t in sent if t[0] == ("s", "w1")]) == 1
```

  `ask(session, agent, question, choices=None)` is a small helper in the test file:
  `runtime.ask_human("s", agent, question, None, choices)` and the new question's id
  (`state.list_messages("s")[-1].id`). Reuse the file's existing fixtures for a running
  session with workers `w1` and `w2` and for the tmux recorder (`sent`), and its helper for a
  turn-end hook; when the names differ, use the file's own. In `tests/test_state.py`:
  `reply_to_questions` writes all or nothing (a second reply's question closed between the
  check and the write raises `QuestionClosed`, and no row is added), and an asker that does
  not run raises `NotRunning` with nothing changed.

- [ ] **Step 2:** `uv run pytest -n0 tests/test_runtime.py -k "batch or paste or skip_is or turns_end" tests/test_state.py -k reply_to_questions` — FAIL (`answer_questions` is not defined).

- [ ] **Step 3: Implement.** `state.py`:

```python
@dataclass(frozen=True)
class Reply:
    """The human's reply to one open question, as the core writes it (lado.runtime)."""

    question: int
    summary: str
    body: str
    choice: str | None
    outcome: str  # ANSWERED or DISMISSED


class QuestionClosed(Exception):
    def __init__(self, question: int, question_state: str):
        super().__init__(f"question #{question} is {question_state}")
        self.question, self.question_state = question, question_state


def reply_to_questions(session: str, replies: Sequence[Reply]) -> list[int]:
    """Queue the human's replies to open questions of one agent and set each question's
    outcome, in one transaction; the replies' ids, in order. QuestionClosed or NotRunning,
    with nothing changed, when a question is not open or the agent that asked does not
    run."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        ids = []
        try:
            for reply in replies:
                row = db.execute(
                    "SELECT sender, question_state FROM messages"
                    " WHERE session = ? AND id = ? AND kind = ?",
                    (session, reply.question, QUESTION),
                ).fetchone()
                if row is not None:
                    _check_running(db, session, row["sender"])
                if row is None or row["question_state"] != OPEN_QUESTION:
                    raise QuestionClosed(reply.question, row["question_state"] if row else "gone")
                ids.append(
                    db.execute(
                        "INSERT INTO messages (session, sender, recipient, summary, body,"
                        " reply_to, choice, created_at) VALUES (?, ?, ?, ?, ?, ?, ?,"
                        " strftime('%Y-%m-%d %H:%M:%f', 'now'))",
                        (session, HUMAN, row["sender"], reply.summary, reply.body,
                         reply.question, reply.choice),
                    ).lastrowid
                )
                db.execute(
                    "UPDATE messages SET question_state = ?, answered_by = ? WHERE id = ?",
                    (reply.outcome, ids[-1], reply.question),
                )
        except BaseException:
            db.execute("ROLLBACK")
            raise
        db.execute("COMMIT")
    return ids
```

  (`_check_running` raises `NotRunning`; keep its use as `reply_to_question` had it, then
  delete `reply_to_question`.) `runtime.py`: `HumanReply` (frozen dataclass); `_reply_of(
  question: state.Message, reply: HumanReply) -> state.Reply` moves today's rules of
  `answer_question` (choice, own words with `_human_text(text, prefix)`) and
  `dismiss_question` (`Dismissed #<id>`, the stripped comment, the limit) into one place,
  plus `skip` with a choice refused; `answer_questions`:

```python
def answer_questions(session: str, replies: Sequence[HumanReply]) -> str:
    """The human's replies to open questions of one agent: each checked first, all written
    in one transaction, then the agent's queue taken once, so an idle agent gets them in
    one hand-over (one turn)."""
    if not replies:
        raise LadoError("no answers")
    seen: set[int] = set()
    questions = []
    for reply in replies:
        if reply.question in seen:
            raise LadoError(f"question #{reply.question} is answered twice")
        seen.add(reply.question)
        questions.append(_open_question(session, reply.question))
    asker = questions[0].sender
    for question in questions[1:]:
        if question.sender != asker:
            raise LadoError(
                f"answers go to one agent at a time: #{questions[0].id} is {asker}'s,"
                f" #{question.id} is {question.sender}'s"
            )
    written = [_reply_of(q, r) for q, r in zip(questions, replies)]
    try:
        with _to_running(session):
            ids = state.reply_to_questions(session, written)
    except state.QuestionClosed as closed:
        raise LadoError(str(closed)) from None
    return _deliver(session, asker, ids[-1])
```

  `answer_question(session, id, choice=None, text=None)` returns
  `answer_questions(session, [HumanReply(id, choice, text)])`; `dismiss_question(session,
  id, text=None)` returns `answer_questions(session, [HumanReply(id, text=text,
  skip=True)])`. Delete `_reply`.

- [ ] **Step 4:** the Step 2 run passes; then `make test` (all unit tests: the old
  `answer_question` / `dismiss_question` tests must still pass unchanged).

- [ ] **Step 5: Commit** `src/lado/state.py src/lado/runtime.py tests/test_state.py
  tests/test_runtime.py`: "The human's answers to one agent's questions are handed over
  together (LAD-28)".

### Task 2: The server takes a tab's answers (D5)

**Files:** modify `src/lado/server/models.py` (next to `Answer`), `src/lado/server/app.py`
(the question endpoints); `web/src/api.ts`; regenerate `web/openapi.json`,
`web/src/api.gen.ts`; test `tests/test_server_messages.py`,
`tests/integration/test_human_messages.py`.

**Consumes:** `runtime.answer_questions`, `runtime.HumanReply`.
**Produces:** `POST /api/sessions/{name}/answers` with `models.Replies {answers:
list[models.Reply]}`, `models.Reply {question: int, choice: str | None, text: str | None,
skip: bool}`, answering `Sent`; `api.ts`: `export type Reply = components["schemas"]["Reply"]`
and `answerQuestions(session: string, answers: Reply[]) => Promise<Sent>`. Removed here:
`Answer`, `Dismissal`, the two endpoints; in Task 4: `answerQuestion`, `dismissQuestion`.

- [ ] **Step 1: Failing tests** (`tests/test_server_messages.py`): replace
  `test_the_human_answers_and_dismisses_questions` and `test_a_dismissal_takes_the_humans_comment` by

```python
ANSWERS = "/api/sessions/s/answers"


def test_the_human_answers_a_tab_in_one_request(client, session):
    runtime.ask_human("s", "w1", "Ship?", None, ["yes", "no"])
    runtime.ask_human("s", "w1", "Port?")
    ship, port = state.list_messages("s")
    answered = client.post(
        ANSWERS,
        json={"answers": [{"question": ship.id, "choice": "yes"}, {"question": port.id, "skip": True, "text": "not now"}]},
    )
    assert answered.status_code == 200
    _, _, answer, dismissal = state.list_messages("s")
    assert (answer.summary, answer.reply_to) == (f"Answer to #{ship.id}: yes", ship.id)
    assert (dismissal.summary, dismissal.body) == (f"Dismissed #{port.id}", "not now")
    again = client.post(ANSWERS, json={"answers": [{"question": ship.id, "text": "no"}]})
    assert again.status_code == 400
    assert again.json()["detail"] == f"question #{ship.id} is answered"


def test_an_empty_tab_is_refused(client, session):
    answer = client.post(ANSWERS, json={"answers": []})
    assert (answer.status_code, answer.json()["detail"]) == (400, "no answers")


def test_the_old_question_endpoints_are_gone(client, session):
    assert client.post("/api/sessions/s/questions/1/answer", json={"choice": "yes"}).status_code in (404, 405)
```

  and replace the two old paths in the guard's parametrized tests (`MESSAGES,
  "/api/sessions/s/questions/1/answer", "/api/sessions/s/questions/1/dismiss"`) with
  `ANSWERS`. In `tests/integration/test_human_messages.py`,
  `test_the_agents_question_is_answered_through_the_api` posts to `…/answers`, and a new
  test asks two questions (`askhuman Ship it? | yes, no`, then `askhuman Which port?`),
  waits for both open and the agent idle, posts both replies in one request, and waits for
  both `[from human] Answer to #…` lines in `inputs()` and both questions `answered`.

- [ ] **Step 2:** `uv run pytest -n0 tests/test_server_messages.py` — FAIL (404 on `…/answers`).

- [ ] **Step 3: Implement.** `models.py`:

```python
class Reply(BaseModel):
    """The human's reply to one open question: a choice, own words, or a skip (a
    dismissal, `text` its comment)."""

    question: int
    choice: str | None = None
    text: str | None = None
    skip: bool = False


class Replies(BaseModel):
    answers: list[Reply]
```

  `app.py`, in place of the two question endpoints:

```python
@app.post("/api/sessions/{name}/answers", dependencies=[Depends(guard.changes)])
def answers(name: str, given: Replies, has_db: bool = Depends(database)) -> Sent:
    """The human's replies to open questions of one agent (a tab of the waiting card),
    handed over together."""
    known(name, has_db)
    replies = [runtime.HumanReply(r.question, r.choice, r.text, r.skip) for r in given.answers]
    return Sent(result=core(runtime.answer_questions, name, replies))
```

  `api.ts`: add `answerQuestions`
  (`post<Sent>(\`${sessionPath(session)}/answers\`, { answers })`). Run `make web-types`.

- [ ] **Step 4:** `uv run pytest -n0 tests/test_server_messages.py`; `uv run pytest -m
  integration -n auto tests/integration/test_human_messages.py` (the marker is required);
  `make web` (stale-types check). `api.ts`'s `answerQuestion` / `dismissQuestion` stay
  until Task 4 removes the open form that calls them (they only build URLs, so the build
  stays green; their endpoints are gone from here on).

- [ ] **Step 5: Commit** the models, app, api.ts, both generated files and tests: "The
  server takes a tab's answers in one request (LAD-28)".

### Task 3: The gate's panel is shared (D8)

**Files:** modify `web/src/GateCard.tsx`; test `web/src/Flows.test.tsx` (the compact card),
`web/src/GateCard.test.tsx` (new, the panel).

**Produces:** `export function GatePanel({session, gate, stopped}: {session: string; gate:
GateInfo; stopped: boolean})` (question, `Note`, the problem line, `Reads`, comment, option
buttons, the stopped line, the refusal); `export function Note`, `export function Reads`;
`GateCard` (compact, Flows) unchanged in what it shows. `GateRow` goes in Task 6 (Needs
you, its last user) and the chat's `Gate` draws only `GateLine` from Task 5 on.

- [ ] **Step 1:** vitest: the compact card on a run's page still answers (existing
  `Flows.test.tsx` cases keep passing); a new `GatePanel` test: a gate with `problem` shows
  "Artifacts it reads cannot be shown: <problem>" and its buttons answer; stopped, its
  buttons are off and "The session is stopped: resume it to answer." shows.
- [ ] **Step 2:** `cd web && npx vitest run src/Flows.test.tsx src/GateCard.test.tsx` — FAIL.
- [ ] **Step 3:** split `GateCard` into `GatePanel` (the form) used by `GateCard`,
  `GateRow` (until Task 6) and Task 4; export `Note`, `Reads`.
- [ ] **Step 4:** `make web`.
- [ ] **Step 5: Commit**: "The gate's form is one panel the cards share (LAD-28)".

### Task 4: The waiting card (D6, D7, D9)

**Files:** create `web/src/WaitingCard.tsx`, `web/src/WaitingCard.test.tsx`; modify
`web/src/Question.tsx` (D13, D12), `web/src/icons.tsx` (`ExpandIcon`, `CollapseIcon`),
`web/src/styles.css`.

**Consumes:** `answerQuestions`, `GatePanel`, `avatar` (FeedRow), `runColours` (Team),
`Body`, `Attachments`, `Tooltip`.
**Produces:**

```ts
export type WaitingTab =
  | { key: `agent:${string}`; agent: string; questions: MessageInfo[]; since: string }
  | { key: `gate:${number}`; gate: GateInfo; since: string };
export function waitingTabs(questions: MessageInfo[], gates: GateInfo[]): WaitingTab[];
export type Focus = { key: string; item: number; at: number } | null;
export function WaitingCard(props: {
  session: string;
  questions: MessageInfo[]; // open questions of this session
  gates: GateInfo[]; // open gates of this session
  runs: RunInfo[] | null; // for runColours; null while loading
  stopped: boolean;
  focus: Focus;
}): JSX.Element | null;
export const tabKeyOf: (item: { question?: MessageInfo; gate?: GateInfo }) => string;
```

- [ ] **Step 1: Failing tests** (`WaitingCard.test.tsx`, `fetch` mocked as in
  `Chat.test.tsx`): `waitingTabs` groups by sender and orders by first item (the "Three
  things wait" scenario); no items renders nothing; tab shows letter, name and count, a
  gate's tab the Flows icon and `data-kind="gate"`; a click shows the tab and new items on
  another tab do not switch it; when the shown tab empties the first shows; Send is off
  until all answered and "1 of 2 answered" shows; a choice unpicks on a second click;
  Other… and Skip exclude a choice; Other… with blank text does not count; typing in Other…
  keeps focus and caret (type two characters, `document.activeElement` is the field and its
  value has both); Send posts one request with `[{question, choice}, {question, text}]` and
  `{question, skip: true, text}` for a skip; a 400 shows its detail and keeps the picks; a
  question without `free_answer` has no Other…; the question's body renders as Markdown and
  its attachments as chips; `focus` selects the tab and marks the item.
- [ ] **Step 2:** `cd web && npx vitest run src/WaitingCard.test.tsx` — FAIL.
- [ ] **Step 3: Implement.**
  - `Question.tsx`: drop the open form (`act`, `submit`, the `<form>`), keep the closed
    card; remove `answerQuestion` and `dismissQuestion` from `api.ts`; `Given`'s head and the dismissal words "skipped" (D12; `LateReply` and `Answer`
    in `Chat.tsx` likewise in Task 5).
  - `WaitingCard.tsx`: `waitingTabs` (pure); the component keeps `shown: string | null`,
    `picks: Record<number, Pick>`, `busy`, `problem`, `expanded`, `marked: number | null`;
    tabs as `<div role="tablist">` of `<button role="tab" aria-selected>` with
    `style={{"--who": colour}}`; the panel `role="tabpanel"`; an agent's panel is an `<ol>`
    of questions (number only when more than one), each `<li data-question={id}>` with
    `Body`, `Attachments`, the choice buttons (`aria-pressed`), Other… (when
    `free_answer`), Skip, and the field when Other… or Skip is on (a controlled
    `<textarea>` whose element is not re-created on input: keep it keyed by question id);
    the Send row; a gate's panel is `GatePanel`.
  - `styles.css`: the look of D9, copied from the mockup's `final_css` rules
    (`.qcard`→`.waiting-card`, `.qtabs`→`.waiting-tabs`, `.qtab`→`.waiting-tab`,
    `.qpanel`→`.waiting-panel`, `.tq*`→`.waiting-question*`, `.opt`→`.waiting-option`,
    `.qsend`→`.waiting-send`, `.expand`→`.waiting-expand`), with `.chat > .waiting-card`
    taking the chat column's side margins as `.chat > .composer` does.
- [ ] **Step 4:** `make web`.
- [ ] **Step 5: Commit**: "One card with a tab per agent answers what waits (LAD-28)".

### Task 5: The card in the chat, expanded, and the feed's lines (D10, D11)

**Files:** modify `web/src/Chat.tsx`, `web/src/WaitingCard.tsx` (expanded), test
`web/src/Chat.test.tsx`, `web/src/WaitingCard.test.tsx`.

**Consumes:** `WaitingCard`, `Focus`, `tabKeyOf`, `useLive().waiting`, `live.watch("runs",
session)`.

- [ ] **Step 1: Failing tests.** `Chat.test.tsx`: an open question is the line
  "supervisor asked: Which branch should the PR target?" with a button "Answer question
  #<id>", and no `.chat-question.open`; an open gate is the line "Gate #<id> <run> ·
  <state> waits: <question>"; the card stands between the feed and the composer; no
  `.gate-hint`; the line's button shows that item's tab and marks it; `#message-<id>` of an
  open question in the address selects its tab instead of scrolling; a closed question is
  its closed card; a dismissal reads "You · skipped" / "You skipped question #<id>".
  `WaitingCard.test.tsx`: the expand button (name "Expand the card") opens a dialog named
  "What waits for you in s" in `document.body`; Esc and "Collapse the card" close it and
  focus returns to the expand button; Esc with the card not expanded changes nothing; the
  dialog closes by itself when the last item goes.
- [ ] **Step 2:** `cd web && npx vitest run src/Chat.test.tsx src/WaitingCard.test.tsx` — FAIL.
- [ ] **Step 3: Implement.** `Chat.tsx`: watch `waiting` and `runs`; `questions =
  waiting.items.filter(i => i.session === session && i.question).map(i => i.question)`,
  `gates = loaded.gates.filter(g => g.answer === null)`; render `<WaitingCard … focus>`
  between the feed and the composer; `Rows`: an open question → `OpenLine`, an open gate →
  `OpenLine` (the `Gate` component only for closed gates); remove `GateHint`; `go()` sets
  `focus` for an open item's anchor; "skipped" in `LateReply` and `Answer`. `WaitingCard`:
  `expanded` renders through `createPortal(…, document.body)` with `role="dialog"
  aria-modal="true"`, a `keydown` listener for Esc only while expanded, focus moved to the
  shown tab on open and back to the expand button on close.
- [ ] **Step 4:** `make web`.
- [ ] **Step 5: Commit**: "The chat answers in the waiting card and shows open items as
  lines (LAD-28)".

### Task 6: Needs you shows each session's card (D14)

**Files:** modify `web/src/NeedsYou.tsx`, `web/src/GateCard.tsx`, `web/src/styles.css`; test
`web/src/NeedsYou.test.tsx`.

- [ ] **Step 1: Failing tests:** two sessions with items show two cards with their own
  tabs, each under the session's name and "In the chat"; an agent in `waiting` is still a
  row with "Open terminal"; answering a tab on Needs you posts to that session's
  `…/answers`.
- [ ] **Step 2:** `cd web && npx vitest run src/NeedsYou.test.tsx` — FAIL.
- [ ] **Step 3:** remove `GateRow` from `GateCard.tsx` (Needs you was its last user); per
  session section: `<h2>` with the name and `In the chat`, then `WaitingCard` from its items (`stopped={false}`, `focus={null}`, its runs watched with
  `live.watch("runs", session)`), then its waiting agents.
- [ ] **Step 4:** `make web`.
- [ ] **Step 5: Commit**: "Needs you shows each session's waiting card (LAD-28)".

### Task 7: In a browser

**Files:** modify `tests/ui/test_chat.py`, `tests/ui/test_needs_you.py`.

- [ ] **Step 1:** `test_chat.py`: `test_the_supervisor_asks_and_the_human_answers_in_a_card`
  becomes: the fake supervisor asks two questions; the card shows one tab "supervisor 2";
  the human picks a choice, writes Other… for the second, Send; both lines reach the agent
  (its inputs); the feed shows both closed cards; no card is left. A new test: a worker's
  question and a gate besides → three tabs, switching, the gate's Approve moves the run;
  the expand button shows the dialog over the window, Esc folds it. Update
  `test_the_question_and_gate_cards_buttons_are_one_height_in_light_and_dark` and
  `test_each_message_says_its_text_once_runs_are_groups_and_replies_are_in_the_card` to the
  card's buttons and the feed's lines. `test_needs_you.py`:
  `test_the_human_answers_what_waits_in_place_and_it_goes` answers through the card. Each
  test calls `shot` on each screen it checks: the card with three tabs, the expanded card
  (light and dark), the feed after the answers, Needs you.
- [ ] **Step 2:** `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_needs_you.py`
  (the marker is required).
- [ ] **Step 3: Commit**: "UI tests of the waiting card (LAD-28)". Attach the screenshots
  as run artifacts listed in `build-report`.

### Task 8: Docs

- [ ] `docs/design/ui.md`: The human in the session — "Flow gates" (an open gate is a line
  and a tab; the hint over the composer is gone), "A question" and "Answer in the question
  card" ("skipped"), "The open question's card" replaced by "The waiting card" (decided
  2026-10-13, LAD-28, mockup `task/lad-28/mockup-question-card-final.html`: tabs, colours,
  picks, Send, the gate's tab, half height, expanded over the window, stopped), the feed's
  lines; Structure: Needs you (a card per session); Look: the card's tokens. AGENTS.md:
  Layout (`POST …/answers` in `app.py`'s endpoints, the two question endpoints gone), How
  agents talk (the human's replies to one agent's questions are handed over together).
  CHANGELOG.md under `## 0.37.0 (unreleased)`: one line for the card, one for the API.
- [ ] `openspec validate waiting-card --strict`, `make lint`, `make test`.
- [ ] Commit: "The design, AGENTS.md and the changelog describe the waiting card (LAD-28)".

## Regression run (before the review)

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_human_messages.py tests/integration/test_session_start.py`; `make
web`; `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_needs_you.py`; `openspec
validate --specs --strict` after the archive. CI runs the rest (`make check`, the smoke).
