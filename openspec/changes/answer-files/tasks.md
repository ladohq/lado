## 1. Core: a reply carries the human's files (D5)

- [x] 1.1 `runtime.HumanReply.attached`, `_reply_of` checks the count and resolves the
  names, a files-only own answer's summary; `state.Reply.attachments`,
  `reply_to_questions` attaches them. Check: `uv run pytest tests/test_runtime.py -n auto`
  (a reply with a file, files only, a skip with a file, a missing name, 11 files).

## 2. Core: a gate's answer carries the files; schema 31 (D6, D7)

- [x] 2.1 Schema 31 `gates.answer_note`, set by `update_run` in the closing's
  transaction; `Gate.answer_note`; `tests/agent_helpers.previous_schema` still undoes the
  last step. Check: `uv run pytest tests/test_state.py -n auto` (migration from 30, an
  old gate with no answer note).
- [x] 2.2 `runs.answer` / `answer_text` take `attached`, resolved before any write, on the
  answer's note; Cancel at a loop limit sends them to the supervisor;
  `runs.gate_answer_attachments`. Check: `uv run pytest tests/test_runs.py -n auto` (the
  next step's `Artifacts:` line, files only, a missing name leaves the gate open, the loop
  cancel, a cancel by the supervisor has none).

## 3. Server (D9)

- [ ] 3.1 `Reply.artifacts`, `GateAnswer.artifacts`, `GateInfo.answer_attachments`;
  `app.answers`, `app.answer_gate`; `make web-types`, both generated files committed.
  Check: `uv run pytest tests/test_server_messages.py tests/test_server_gates.py -n auto`,
  `make web`.

## 4. Integration (the fake agent)

- [ ] 4.1 An answer with a file reaches the asking agent with its artifact, and
  `read_artifact` reads it; a gate's answer with a file reaches the next step's agent
  with `Artifacts: /<name>`. Check: `uv run pytest -m integration -n auto
  tests/integration/test_human_messages.py tests/integration/test_flow_runs.py`.

## 5. Web: the shared file handling (D1, D3)

- [ ] 5.1 The composer's file handling moves into one module (`attachFiles.tsx`); the
  composer uses it, its drop ignoring the waiting card. Check: `cd web && npx vitest run
  attachFiles Composer` with `Composer.test.tsx` unchanged.

## 6. Web: the card's fields (D2, D3, D4)

- [ ] 6.1 Other… and Skip fields and a gate's comment take files (clip, paste, drop on the
  field), kept per question and per gate in the card; Send and a gate's buttons upload,
  then answer with `artifacts`; files-only answers count; "<n> files, <size>" beside a
  gate's buttons; `GatePanel` alone on Flows keeps its own. Check: `cd web && npx vitest
  run WaitingCard Flows`, `make web`.

## 7. Web: the feed (D8)

- [ ] 7.1 A closed question's reply block and the row of an answer not in the window show
  previews and chips; a late answer's line ends "· N files"; the gate's move shows the
  answer's previews and chips after the comment, the opened gate's card chips only.
  Check: `cd web && npx vitest run Chat`, `make web`.

## 8. UI e2e

- [ ] 8.1 `tests/ui/test_gates.py`: paste and clip in a gate's comment, Reject, the move's
  preview and chips, the opened card's chips, a drop on the comment; screenshots.
  Check: `uv run pytest -m ui tests/ui/test_gates.py`.
- [ ] 8.2 `tests/ui/test_chat.py`: Other… with a file only, the closed card's preview and
  chip, a drop on the feed goes to the composer; screenshots. Check: `uv run pytest -m ui
  tests/ui/test_chat.py`.

## 9. Docs and release notes

- [ ] 9.1 `docs/design/ui.md` (Flow gates, the API of the chat task, A question, The
  waiting card's Fields, Composer), `docs/design/modules.md` (schema 31, the web module),
  CHANGELOG.md: `## 0.40.1 (unreleased)` renamed `## 0.41.0 (unreleased)` with the
  change's line. Check: read against the code.

## 10. Regression

- [ ] 10.1 `make lint`, `make test`, `make web`, the changed integration and UI files with
  their markers, `openspec validate --specs --strict`; grep `openspec/specs/` for
  "comment for the next step", "own answer", "attachments" against the delta.
