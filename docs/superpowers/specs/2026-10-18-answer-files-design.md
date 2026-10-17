# Files in the answers to gates and questions: design

Task: LAD-86. Change: `openspec/changes/answer-files/` (proposal, `design.md` D1–D10,
delta specs `question-answers`, `gate-answer-files`, `chat-question-card`,
`closed-gate-card`). Mockups (run artifacts): `task/lad-86/mockup-answer-files.html`
(option A chosen; screens 1, 2A, 3, 4), `task/lad-86/mockup-gate-files.html` (a gate's tab
before and after), `task/lad-86/mockup-feed-files.html` (the feed after the answer).

## Goal

The human answers a gate or an agent's question with files as they write to an agent from
the composer: the same paperclip, paste, drop and chips, the same limits, and the files
reach the agent that acts on the answer.

## What the human sees and does

- **A gate's tab** (chat, Needs you; the gate's card on a run's page in Flows): the
  comment for the next step is a composer frame: chips above the text, the paperclip at
  its left; beside the gate's buttons "<n> files, <size>". A button uploads and answers.
- **An agent's tab**: the fields of Other… and Skip are the same frame. A picked choice
  has no field and no files. Other… with files and no text counts as answered.
- **Drop**: on a field of the card, into that field (its frame turns into the drop zone);
  elsewhere in the chat, into the composer.
- **Feed**: a closed question's reply block, and the human's row of an answer to a
  question not in the window, show image previews and chips; a late answer's quiet line
  ends with "· N files"; under the human's move of a gate, after the comment, previews
  and chips; in the opened closed gate's card, chips only.

## Acceptance criteria

- AC-1 A gate's comment takes files by the paperclip, by paste and by a drop on it; its
  chips show above the text with ×, and "<n> files, <size>" beside the buttons.
- AC-2 A gate's button uploads the comment's files and answers with them; the next step's
  agent gets them in `Note from the previous step: …` with `Artifacts: /<name>, …`.
- AC-3 A gate answered with files and no comment moves on; its note is the outcome and
  the files.
- AC-4 At a loop limit, Cancel run with files sends them with LADO's message to the
  supervisor.
- AC-5 Other… and Skip fields take files the same way; a picked choice shows no field and
  takes no files.
- AC-6 Other… with files and no text counts as answered; the agent gets
  `Answer to #N: 1 file: <name>` with the file attached.
- AC-7 Send of an agent's tab uploads every reply's files and sends all replies in one
  request; the agent gets each reply with its files in one hand-over.
- AC-8 A file dropped on a field of the card attaches to that field and never to the
  composer; one dropped elsewhere in the chat attaches to the composer.
- AC-9 A failed upload stops the answer; the chip is red with its reason, picks, text and
  the other files stay, and the next try uploads only what failed.
- AC-10 The limits are the server's: an 11th file or a file over 25 MB is refused at the
  field with the composer's words; the core refuses more than 10 or a name not found, with
  nothing changed.
- AC-11 A closed question card's reply block, and the row of an answer to a question not
  in the window, show image previews and chips; a late answer's line ends with
  "· N files".
- AC-12 Under the human's move of a gate stand the comment, previews and chips; the opened
  closed gate's card shows chips only; the folded line shows none.
- AC-13 Files are kept per field across tab switches and the expanded view until sent or
  removed; the files of an item that closed elsewhere go.
- AC-14 Schema 31 migrates an older database; old gates show no answer files.
- AC-15 The composer behaves exactly as before.

## Test layers (AGENTS.md, Testing)

| Requirement | Layer | Where |
|---|---|---|
| A reply carries the files (question-answers) | unit; integration (the agent gets the reply with its artifact and reads it over `lado mcp`) | `tests/test_runtime.py`, `tests/test_server_messages.py`; `tests/integration/test_human_messages.py` |
| The server takes a tab's replies (question-answers) | unit | `tests/test_server_messages.py` |
| A gate's answer carries the files (gate-answer-files) | unit; integration (the next step's text with its `Artifacts:` line reaches the fake agent) | `tests/test_runs.py`; `tests/integration/test_flow_runs.py` |
| A closed gate keeps its answer's note | unit (migration, `answer_note`, `answer_attachments`) | `tests/test_state.py`, `tests/test_server_gates.py` |
| The server takes a gate's answer with files | unit | `tests/test_server_gates.py` |
| The card's answer fields take files | vitest; UI e2e (paste, clip, drop on the card and on the feed, failed upload) | `web/src/WaitingCard.test.tsx`, a test of the shared module, `Composer.test.tsx` unchanged; `tests/ui/test_gates.py`, `tests/ui/test_chat.py` |
| An agent's tab sends its answers together (modified) | vitest; UI e2e | `WaitingCard.test.tsx`; `tests/ui/test_chat.py` |
| A gate's tab answers the gate at once (modified) | vitest; UI e2e | `WaitingCard.test.tsx` / `Flows.test.tsx`; `tests/ui/test_gates.py` |
| A closed question card shows the reply's files | vitest; UI e2e screenshot | `Chat.test.tsx`; `tests/ui/test_chat.py` |
| The answer's files show with its comment (closed-gate-card) | vitest; UI e2e screenshot | `Chat.test.tsx`; `tests/ui/test_gates.py` |

Regression: `make lint`, `make test`, `make web` (stale types), the changed integration
files with `-m integration`, the changed UI files with `-m ui`, `openspec validate --specs
--strict`. No change to `providers/`, `hooks.py`, `mcp_server.py` or `agent_env.py`;
`runtime.py` changes (the reply's attachments): the reviewer names it.

## Docs

- `docs/design/ui.md`: The human in the session — Flow gates (a gate's answer takes files,
  `POST …/answer {option, comment, artifacts}`, `answer_attachments`, the move's files, the
  opened card's chips); Built in the chat task, API (`artifacts` of a reply); A question
  (the reply's files, the late line); The waiting card, Fields (the composer frame, drop,
  files kept per field); Composer (its file handling shared, its drop ignoring the card).
- `docs/design/modules.md`: the web module of the shared file handling, if it lists web
  modules; `state` schema 31.
- CHANGELOG.md: under `## 0.41.0 (unreleased)` (renamed from 0.40.1): files in the
  answers to gates and questions.

## Decided with the human (2026-10-18)

1. A gate's comment takes files as the composer (mockup `mockup-gate-files.html`).
2. Questions: option A, files only in Other… and Skip.
3. An answer of files only is an answer.
4. A drop on a field goes to that field; elsewhere in the chat, to the composer.
5. Also on Needs you and the Flows tab; `lado answer` and the popup stay text only.
6. The feed as in `mockup-feed-files.html`: previews and chips; the opened closed gate
   chips only; "· N files" on a late answer's line.
