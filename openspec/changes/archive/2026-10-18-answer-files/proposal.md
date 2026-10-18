Task: LAD-86

## Why

The human can answer a gate or an agent's question only with text. The composer under the
chat takes files (the paperclip, paste, drop, chips above the field), but the waiting
card's fields do not, so a screenshot or a log that explains a rejection or an answer has
to go as a second message to the supervisor, away from the answer it belongs to, and the
next step of a run never gets it with the gate's comment.

Root cause: the composer's file handling lives inside `Composer.tsx` alone, and the two
answer paths carry no files end to end: `POST …/answers` (`Reply`) and
`POST …/gates/{id}/answer` (`GateAnswer`) have no artifacts, `runtime.answer_questions`
queues its replies without attachments (`state.reply_to_questions`), and `runs.answer`
keeps the next step's note without them. The store can already hold both: a message's
attachments (the reply is a message to the agent) and a note's (the gate's answer is the
next step's note), and both already reach the agent the way the composer's files and a
step's artifacts do.

## What Changes

Chosen with the human (mockups `task/lad-86/mockup-answer-files.html` option A,
`mockup-gate-files.html`, `mockup-feed-files.html`):

- **A gate's tab**: its comment for the next step takes files as the composer does: the
  paperclip at the field's left, the files' chips above the text with ×, paste of a file
  or a long text, drop of files on the field; the number and size of the files beside the
  gate's buttons. Each button uploads the files not yet uploaded and answers with the
  comment and the files; the next step's note carries them as artifacts.
- **An agent's tab** (option A): the fields of **Other…** (own answer) and **Skip**
  (its comment) take files the same way; a picked choice has no field and takes none.
  An own answer of files only (no text) is an answer, as a composer message of files only
  is a message.
- A gate's comment of files only is an answer too: the note is the outcome and the files.
- **Drop**: files dropped on a field of the card go to that field; dropped anywhere else in
  the chat, to the composer, as now. Today a drop on the card goes to the composer.
- **Where**: the waiting card in the chat and on Needs you, and the gate's card on a run's
  page in Flows (one `GatePanel`).
- **Limits**: the composer's, from the server (`GET /api/limits`): up to 10 files of
  25 MB each per answer (per question, per gate).
- **After the answer, in the feed**, as the human's own message shows its files (image
  previews up to 240 × 180, then a chip per file):
  - the closed question card's reply block ("You · answered", "You · skipped") and the
    human's row of an answer to a question not in the window: previews and chips;
  - the quiet line of a late answer ("You answered question #N ↑ · …"): "· N files"
    at its end;
  - a gate: under the human's move line, with the comment: previews and chips; in the
    opened closed gate's card, in its answer block: chips only.
- **At a loop limit**, Cancel run with files: the files go with LADO's message to the
  supervisor about the cancel (there is no next step).
- API: `Reply.artifacts` and `GateAnswer.artifacts` (full names of the uploads, as
  `MessageText.artifacts`); `GateInfo.answer_attachments`. Schema 31: `gates.answer_note`.
- Docs: `docs/design/ui.md` (The human in the session: Flow gates; A question; The waiting
  card: Fields), `docs/design/modules.md` where the composer's files are described,
  CHANGELOG.md.
- A minor release: an API change and a schema migration. The open heading
  `## 0.40.1 (unreleased)` becomes `## 0.41.0 (unreleased)`.

## Scope

- Core: `runtime.HumanReply`, `runtime.answer_questions` / `_reply_of`, `state.Reply`,
  `state.reply_to_questions`; `runs.answer`, `runs.answer_text`, the loop cancel's message;
  `state` schema 31 (`gates.answer_note`), `state.update_run`, `GATE_COLUMNS`.
- Server: `models.Reply`, `models.GateAnswer`, `models.GateInfo`, `app.answers`,
  `app.answer_gate`; `web/openapi.json`, `web/src/api.gen.ts`.
- Web: the composer's file handling shared (`Composer.tsx` → a shared module), the waiting
  card's fields (`WaitingCard.tsx`), `GatePanel` (`GateCard.tsx`), the feed (`Question.tsx`,
  `Chat.tsx`: the answer row, the late line, the run's move, `GateLine`), `api.ts`,
  `styles.css`.
- Tests: unit (runtime, runs, state migration, server), vitest, integration with the fake
  agent, UI e2e with screenshots.

## Out of scope

- **Files with a picked choice** (mockup option B, a paperclip per question): the human
  chose option A; a choice takes no comment today, and a file with it would be one.
- **`lado answer` and the tmux popup**: a terminal has no file picker and nobody asked;
  they keep text only. The API takes files from the UI only.
- **A question's own answer or a gate's comment from the composer**: the composer stays a
  plain message to its recipient (capability chat-question-card).
- **Image previews in the opened closed gate's card**: the card is compact, and the move's
  line shows them (the human's choice).
- **Telling the supervisor about the files of a worker's answer**: the supervisor's line
  "human answered … at …" stays as it is; the files reach the step's agent, who acts on
  them.
- **Other limits for answers**: one set of limits for every upload of the human.

## Impact

- API: two request models gain an optional field (old clients send none); `GateInfo`
  gains a field. Schema 31 with a migration. No MCP tool, CLI or provider change.
- Agents get the files as they get a composer message's (the reply message's artifacts)
  and a step's note's artifacts (`Note from the previous step: …` with its `Artifacts:`
  line), with every provider the same.
