# Files in the answers to gates and questions Implementation Plan

**Goal:** The human answers a gate or an agent's question with files, as from the composer,
and the files reach the agent that acts on the answer.

**Architecture:** Both answer paths gain the full names of the human's uploads: a reply's
names go onto its message's attachments (`state.reply_to_questions`), a gate answer's onto
the note it keeps for the next step (`state.update_run`), which a new column
`gates.answer_note` (schema 31) ties to the gate for the feed. The web UI takes the
composer's file handling out into one shared module, used by the composer and by the
waiting card's fields; the feed draws the files with the existing `ImagePreviews` and
`Attachments`.

**Tech Stack:** Python 3.10+ (standard library, FastAPI/pydantic models), SQLite, React +
TypeScript (vitest), pytest (unit, integration with the fake agent, UI e2e with Playwright).

**Spec:** `openspec/changes/answer-files/` (proposal, `design.md` D1–D10, delta specs
`question-answers`, `gate-answer-files`, `chat-question-card`, `closed-gate-card`) and
`docs/superpowers/specs/2026-10-18-answer-files-design.md` (AC-1..AC-15, test layers).
Mockups: run artifacts `task/lad-86/mockup-answer-files.html` (option A),
`mockup-gate-files.html`, `mockup-feed-files.html`.

## Global Constraints

- Limits: `artifacts.MAX_HUMAN_FILES` (10) files per reply and per gate answer; the size
  limit is the store's (25 MB); the web reads both from `GET /api/limits`, never a copy.
- Core texts, verbatim: too many files `<n> files, the limit is 10` (as
  `write_as_human`); a files-only own answer's summary `Answer to #<id>: ` +
  `runtime._files_line(names)`; "choose one of the choices or write an answer" only when a
  reply has neither text nor files.
- UI texts, verbatim, the composer's: `Attach files: up to <n> files, <size> each (or paste,
  or drop them here)` (the clip's title), `Drop to attach · up to <n> files, <size> each`,
  `<name> was not attached: …`, `<name> was not uploaded: <reason>. Remove it, or Send again
  to try it again.` (for a gate: "or answer again"), beside a gate's buttons
  `<n> file(s), <size>`; a late answer's line ends `· <n> file(s)`.
- API: `Reply.artifacts: list[str] = []`, `GateAnswer.artifacts: list[str] = []`,
  `GateInfo.answer_attachments: list[AttachmentInfo]`.
- Schema: `SCHEMA_VERSION = 31`, `MIGRATIONS[30] = [GATES_ANSWER_NOTE]`,
  `GATES_ANSWER_NOTE = "ALTER TABLE gates ADD COLUMN answer_note INTEGER REFERENCES notes(id)"`,
  also appended to `SCHEMA`; `tests/agent_helpers.previous_schema` unchanged in shape
  (`schema_before(state.SCHEMA_VERSION)` undoes the last step: check it handles a dropped
  column, as for `GATES_CLOSED_EVENT`).
- Commits: English, a plain sentence, `(LAD-86)` at the end; edit with edit tools.
- CHANGELOG: rename `## 0.40.1 (unreleased)` to `## 0.41.0 (unreleased)` and add the line.

## Review Focus

- A file attached, then the item closed elsewhere (another tab answered it): its chips
  and thumbnail URLs must go with it, not reappear on a later question of the same id
  space — Task 6 tests that a closed question's files are dropped and the object URLs
  revoked.
- Other… with files, then switched to Skip: the files stay with the question (D2) and are
  sent as the skip's — Task 6 tests the switch keeps the chips.
- A drop on the card but not on a field (the tabs, the question text): the browser must not
  open the file and the composer must not get it — Task 6 tests a drop on a question's
  text attaches nowhere and calls `preventDefault`.
- A gate answered with only files by the popup or `lado answer` cannot happen, but an
  API client may send `artifacts` with Cancel at a loop limit: they must reach the
  supervisor, not vanish — Task 2 tests it.
- A gate closed before schema 31 opened in the feed: `answer_attachments` empty, no error
  — Task 2 tests a migrated database's old closed gate.

---

### Task 1: A reply carries the human's files (core)

**Files:**
- Modify: `src/lado/runtime.py` (`HumanReply`, `_reply_of`, `answer_questions`)
- Modify: `src/lado/state.py` (`Reply`, `reply_to_questions`)
- Test: `tests/test_runtime.py`

**Interfaces:**
- Produces: `runtime.HumanReply(question, choice=None, text=None, skip=False, attached=())`
  with `attached: tuple[str, ...]` full names; `state.Reply(..., attachments: Attached = ())`.

- [ ] **Step 1: Write the failing tests** (fixture and helper names below such as
  `session_with_questions`, `to_gate`, `PNG` stand for the set-up of the neighbouring tests;
  use theirs) (next to the existing `answer_questions` tests,
  ~line 4360; upload with `artifacts.upload(session, "shot.png", PNG)` as other tests of
  human files do):

```python
def test_a_reply_carries_the_files_the_human_attached(session_with_questions):
    session, first, second = session_with_questions
    shot = artifacts.upload(session, "shot.png", PNG).full_name
    runtime.answer_questions(
        session,
        [
            runtime.HumanReply(first, "short"),
            runtime.HumanReply(second, text="like this", attached=(shot,)),
        ],
    )
    reply = state.get_message(session, state.get_message(session, second).answered_by)
    assert [artifacts.attached(state.message_attachments(reply.id))[0].artifact.full_name] == [shot]


def test_an_own_answer_of_files_only_names_them():
    ...
    runtime.answer_questions(session, [runtime.HumanReply(second, attached=(log,))])
    assert reply.summary == f"Answer to #{second}: 1 file: {log}" and reply.body == ""


def test_a_skip_takes_files_without_a_comment(): ...  # outcome dismissed, attachment kept


def test_a_reply_naming_a_missing_file_refuses_the_whole_call():
    ...
    # LadoError, both questions still open, no message queued


def test_a_reply_with_eleven_files_is_refused():
    ...
    # LadoError "11 files, the limit is 10", nothing changed
```

Fill the `...` with the same set-up as the test above (two open questions of one agent,
one with a free answer); every assertion is written out in the test, none left as a
comment.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_runtime.py -n0 -k "files or eleven" -v`
Expected: FAIL (`HumanReply` has no `attached`).

- [ ] **Step 3: Implement**

```python
@dataclass(frozen=True)
class HumanReply:
    question: int
    choice: str | None = None
    text: str | None = None
    skip: bool = False
    attached: tuple[str, ...] = ()  # full names of the human's uploads (artifacts.upload)
```

In `_reply_of(question, reply, session)`: first
`if len(reply.attached) > artifacts.MAX_HUMAN_FILES: raise LadoError(f"{n} files, the limit is {MAX}")`,
`attachments = artifacts.resolve_attachments(session, None, list(reply.attached))`; the
own-answer branch: `elif not text and not attachments: raise LadoError("choose one of the
choices or write an answer")`; with no text and files:
`summary, body = runtime.cut_summary(prefix + _files_line(list(reply.attached))), ""`
(the free-answer check stays first); every `state.Reply(...)` gets `attachments`.
In `state.Reply` add `attachments: Attached = ()`; in `reply_to_questions` after the
INSERT: `_attach(db, "message", message, reply.attachments)`. Resolve all replies before
the transaction (they already are built in `written = [...]`). Update the docstrings.

- [ ] **Step 4: Run them to see them pass**, then `uv run pytest tests/test_runtime.py -n auto`.

- [ ] **Step 5: Commit** — `git add src/lado/runtime.py src/lado/state.py tests/test_runtime.py`;
  `git commit -m "A reply to a question carries the files the human attached (LAD-86)"`.

### Task 2: A gate's answer carries the files; schema 31 (core)

**Files:**
- Modify: `src/lado/state.py` (`GATES_ANSWER_NOTE`, `SCHEMA`, `MIGRATIONS[30]`,
  `SCHEMA_VERSION`, `Gate.answer_note`, `update_run`)
- Modify: `src/lado/runs.py` (`answer`, `answer_text`, `_cancel` path's
  `_tell_supervisor`, new `gate_answer_attachments`)
- Modify: `tests/agent_helpers.py` if `schema_before` needs the new step
- Test: `tests/test_runs.py`, `tests/test_state.py`

**Interfaces:**
- Produces: `runs.answer(session, gate, option, comment=None, by=HUMAN, attached=None)`,
  `runs.answer_text(session, gate, option, comment=None, attached=None) -> str`,
  `runs.gate_answer_attachments(gate: state.Gate) -> list[artifacts.Attachment]`,
  `state.Gate.answer_note: int | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_gates_answer_gives_its_files_to_the_next_steps_note(session):  # tests/test_runs.py
    gate = to_gate(session)  # the helper the reject tests use, ~line 400
    log = artifacts.upload(session, "server.log", b"boom\n").full_name
    runs.answer(session, str(gate.id), "reject", "the form is too big", attached=[log])
    assert f"Artifacts: /{log}" in first_input("analyst")  # the step's text the worker got
    closed = state.get_gate(gate.id)
    assert [a.artifact.full_name for a in runs.gate_answer_attachments(closed)] == [log]


def test_a_gate_answered_with_files_only_has_the_outcome_as_its_note(session): ...
def test_a_gates_answer_naming_a_missing_file_leaves_it_open(session): ...
def test_cancel_at_a_loop_limit_sends_the_files_to_the_supervisor(session): ...
def test_a_gate_closed_by_a_cancel_has_no_answer_files(session): ...
```

In `tests/test_state.py`: a migration test from 30 (`previous_schema()`, then
`state.connect()`): an old closed gate has `answer_note is None` and the version is 31.
Each `...` gets its full body with its own assertions.

- [ ] **Step 2: Run to see them fail** — `uv run pytest tests/test_runs.py tests/test_state.py -n0 -k "files or answer_note or 31" -v`.

- [ ] **Step 3: Implement**

`state.py`:

```python
# The note a gate's answer kept for the next step, from version 31 on: the feed shows
# its files under the answer (runs.gate_answer_attachments). NULL for a gate closed
# otherwise and for every gate closed before.
GATES_ANSWER_NOTE = "ALTER TABLE gates ADD COLUMN answer_note INTEGER REFERENCES notes(id)"
SCHEMA += GATES_ANSWER_NOTE + ";\n"
MIGRATIONS[30] = [GATES_ANSWER_NOTE]
SCHEMA_VERSION = 31
```

In `update_run`, after `_attach(db, "note", note, attachments)`:
`if closed: db.execute("UPDATE gates SET answer_note = ? WHERE id = ?", (note, closed))`.
`Gate` gets `answer_note: int | None = None`, read by its row builder.

`runs.py`: in `answer`, before `closes = ...`:

```python
    names = list(attached or [])
    if len(names) > artifacts.MAX_HUMAN_FILES:
        raise LadoError(f"{len(names)} files, the limit is {artifacts.MAX_HUMAN_FILES}")
    attachments = artifacts.resolve_attachments(session, None, names)
```

pass `attachments=attachments` to `_commit`; on the loop cancel call
`_tell_supervisor(run, ..., comment, attachments=attachments)`, and `_tell_supervisor`
passes them to `runtime.post(..., attachments=attachments)` (notices path: none, a human
never takes it). `answer_text` takes `attached` and passes it. Add:

```python
def gate_answer_attachments(gate: state.Gate) -> list[artifacts.Attachment]:
    """The files the gate's answer gave the next step: the attachments of the note it
    kept (state.GATES_ANSWER_NOTE); none for a gate closed otherwise or before."""
    if not gate.answer_note:
        return []
    return artifacts.attached(state.note_attachments(gate.answer_note))
```

- [ ] **Step 4: Run to see them pass**, then `uv run pytest tests/test_runs.py tests/test_state.py -n auto`.

- [ ] **Step 5: Commit** — `git commit -m "A gate's answer gives the human's files to the next step (LAD-86)"`.

### Task 3: The server takes the files (API)

**Files:**
- Modify: `src/lado/server/models.py` (`Reply`, `GateAnswer`, `GateInfo`, the gate builder
  ~line 1384), `src/lado/server/app.py` (`answers`, `answer_gate`)
- Modify (generated): `web/openapi.json`, `web/src/api.gen.ts` by `make web-types`
- Test: `tests/test_server_messages.py`, `tests/test_server_gates.py`

**Interfaces:**
- Consumes: Task 1's `HumanReply.attached`, Task 2's `runs.answer_text(..., attached)`,
  `runs.gate_answer_attachments`.
- Produces: `POST …/answers` reply field `artifacts`; `POST …/gates/{id}/answer` field
  `artifacts`; `GateInfo.answer_attachments`.

- [ ] **Step 1: Failing tests** — a posted reply with `"artifacts": [name]` is 200 and its
  message's `attachments` lists it; a gate answer with `"artifacts": [name]` is 200 and
  `GET …/gates` gives it `answer_attachments` with that name; a missing name is 400.
- [ ] **Step 2: Run** `uv run pytest tests/test_server_messages.py tests/test_server_gates.py -n0 -k artifacts -v` → FAIL.
- [ ] **Step 3: Implement** — `artifacts: list[str] = []` on both models (docstrings say
  "full names of the files uploaded for it (POST …/artifacts)"); `app.answers`:
  `runtime.HumanReply(r.question, r.choice, r.text, r.skip, tuple(r.artifacts))`;
  `answer_gate`: `core(runs.answer_text, name, str(gate), given.option, given.comment, given.artifacts)`;
  `GateInfo.answer_attachments=[attachment_info(a) for a in runs.gate_answer_attachments(gate)]`.
  Then `make web-types`.
- [ ] **Step 4: Run** the two files with `-n auto`, then `make web` (stale-types check).
- [ ] **Step 5: Commit** both generated files with the models —
  `git commit -m "The server takes files with the answers to questions and gates (LAD-86)"`.

### Task 4: Integration: the agents get the files (fake agent)

**Files:**
- Test: `tests/integration/test_human_messages.py`, `tests/integration/test_flow_runs.py`

- [ ] **Step 1: Write the tests** — (a) a worker asks a question with a free answer
  (`ask_human` through `lado mcp`), the test uploads a file and answers it through
  `runtime.answer_questions` with `attached`; the fake agent's pasted input holds
  `[from human] Answer to #<id>: …` and its artifacts line, and its `read_artifact` of the
  name returns the content. (b) A run waiting at a gate; `runs.answer(..., attached=[name])`;
  the next step's agent's pasted step text holds `Artifacts: /<name>`. Reuse the helpers
  of the existing tests there (the composer-files test of `test_human_messages.py`).
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_human_messages.py tests/integration/test_flow_runs.py` → PASS (Tasks 1–2 done).
- [ ] **Step 3: Commit** — `git commit -m "Integration tests: agents get the files of the human's answers (LAD-86)"`.

### Task 5: The composer's file handling shared (web)

**Files:**
- Create: `web/src/attachFiles.tsx`, `web/src/attachFiles.test.tsx`
- Modify: `web/src/Composer.tsx`

**Interfaces:**
- Produces:
  - `type Attached` (moved as it is), `mediaTypeOf(name, limits)` (moved; re-export from
    `Composer.tsx` only if a test imports it there), `useLimits(): Limits | null`;
  - `useFiles(limits, initial?: Attached[], onChange?: (files: Attached[]) => void)` →
    `{ files, attach(files: File[]), remove(key), upload(session): Promise<string[] | null>, problem, setProblem, paste(event) }`
    — `upload` uploads what is not uploaded, marks failures, sets the problem text and
    returns the full names, or null when any failed; with `onChange` the files live in the
    caller (the waiting card, D2);
  - `useDropZone(ref, attach, { ignoreInside?: string })` → `dropping: boolean`;
  - `<FileChips files locked limits remove />`, `<ClipButton disabled limits attach />`;
  - `<AnswerBox label text change off files…>` the card's field: the `composer-box`
    frame, chips, clip, the textarea grown by `useGrow(field, text, CARD_LINES, MOST_LINES)`,
    its own drop zone.
- [ ] **Step 1:** vitest of the module: attach over the limits names the refused file;
  `upload` with one failing `uploadFile` returns null and keeps the uploaded name for the
  retry; the drop zone ignores a drop inside `ignoreInside`.
- [ ] **Step 2:** `cd web && npx vitest run attachFiles` → FAIL.
- [ ] **Step 3:** move the code out of `Composer.tsx` unchanged in behaviour; the composer
  calls `useDropZone(area, attach, { ignoreInside: ".waiting-card" })` on its
  `.chat, .agent-page` area (D3).
- [ ] **Step 4:** `cd web && npx vitest run attachFiles Composer` → PASS, `Composer.test.tsx`
  not edited.
- [ ] **Step 5: Commit** — `git commit -m "The composer's file handling is one module the answer fields can use (LAD-86)"`.

### Task 6: The card's fields take files (web)

**Files:**
- Modify: `web/src/WaitingCard.tsx` (`AnswerField` → `AnswerBox`, files per question in
  the card's state next to `picks`, `answered`, `send`), `web/src/GateCard.tsx`
  (`GatePanel`: `files` / `onFiles`, the comment as `AnswerBox`, upload then
  `answerGate(session, id, option, comment, names)`, "<n> files, <size>" in the Send row),
  `web/src/api.ts` (`answerGate` and `Reply` take `artifacts`), `web/src/styles.css`
  (`.waiting-card .composer-box` sizing; the textarea inside the box without its own frame)
- Test: `web/src/WaitingCard.test.tsx`, `web/src/Flows.test.tsx`

- [ ] **Step 1: Failing vitest** — Other… with one file and no text: Send on, the request
  holds `artifacts`; a choice shows no clip; switching Other… → Skip keeps the chips;
  a question closed elsewhere drops its files and revokes its object URL; a drop on a
  question's text attaches nowhere and is `preventDefault`ed; a gate's Reject uploads,
  then posts `{option: "reject", comment, artifacts}`; a failed upload leaves the gate
  open with the red chip; "2 files, 196 KB" beside the gate's buttons.
- [ ] **Step 2:** `cd web && npx vitest run WaitingCard Flows` → FAIL.
- [ ] **Step 3:** implement per D1–D4; `answered(pick, files)` counts an own answer with
  files; `toReply` adds `artifacts`.
- [ ] **Step 4:** the same run → PASS; `make web`.
- [ ] **Step 5: Commit** — `git commit -m "The waiting card's answer fields take files as the composer does (LAD-86)"`.

### Task 7: The feed shows the answers' files (web)

**Files:**
- Modify: `web/src/Question.tsx` (`Given`: `ImagePreviews` + `Attachments` of the answer;
  pass `session`), `web/src/Chat.tsx` (`Answer` row and skip line, `LateReply` "· n
  file(s)", `RunEvents` after the comment: `gate.answer_attachments` previews and chips,
  shown also with no comment), `web/src/GateCard.tsx` (`GateLine`'s opened card: chips after
  the comment)
- Test: `web/src/Chat.test.tsx`

- [ ] **Step 1: Failing vitest** — a closed question whose answer has a PNG and a log shows
  one preview and two chips in its reply block; a late answer with two files ends "· 2
  files"; a closed gate with `answer_attachments` shows them under the move (preview and
  chips) and, opened, two chips and no preview; the folded line shows none.
- [ ] **Step 2:** `cd web && npx vitest run Chat` → FAIL. **Step 3:** implement.
  **Step 4:** PASS, `make web`.
- [ ] **Step 5: Commit** — `git commit -m "The chat shows the files of the human's answers (LAD-86)"`.

### Task 8: UI e2e with screenshots

**Files:**
- Test: `tests/ui/test_gates.py`, `tests/ui/test_chat.py`

- [ ] **Step 1:** `test_gates.py`: paste an image into a gate's comment, attach a log with
  the clip, Reject; the run's move shows the comment, the preview and two chips; the
  opened gate card shows two chips; screenshots of the tab before Reject and of the feed
  after (the `shot` fixture). A drop of a file on the comment attaches it there and the
  composer shows no chip.
- [ ] **Step 2:** `test_chat.py`: Other… with a file only, Send; the closed card's reply
  block shows the preview and the chip; a drop on the feed while the card shows goes to
  the composer; screenshots.
- [ ] **Step 3:** `uv run pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py` → PASS.
- [ ] **Step 4: Commit** — `git commit -m "UI tests: files in the answers to gates and questions (LAD-86)"`;
  attach the screenshots as run artifacts listed in `build-report`.

### Task 9: Docs and CHANGELOG

**Files:**
- Modify: `docs/design/ui.md` (the sections the design doc's Docs lists), `docs/design/modules.md`
  (schema 31 if listed, the web module), `CHANGELOG.md`

- [ ] **Step 1:** write each section true to the code; CHANGELOG: rename the heading to
  `## 0.41.0 (unreleased)` and add: "The human can answer a gate or an agent's question
  with files: the comment for the next step and the fields of Other… and Skip take files
  as the composer does (paperclip, paste, drop), the agent gets them with the answer, and
  the chat shows them under the answer. Schema 31."
- [ ] **Step 2: Commit** — `git commit -m "Docs: files in the answers to gates and questions (LAD-86)"`.

### Regression run (before the build report)

`make lint`; `make test`; `make web`; `uv run pytest -m integration -n auto
tests/integration/test_human_messages.py tests/integration/test_flow_runs.py`;
`uv run pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py`;
`openspec validate --specs --strict`; check off `openspec/changes/answer-files/tasks.md`.
