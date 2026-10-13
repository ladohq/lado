# One card for what waits for the human: design

Task: LAD-28. Change: `openspec/changes/waiting-card/`. Mockup: run artifact
`task/lad-28/mockup-question-card-final.html` (interactive, seven situations). Research:
run artifact `task/lad-28/research-answer-ux.md`.

## Problem

An open question or gate is answered in its own card, which has a field and a Send like
the composer under the chat, so the chat shows two or more places to type and nothing
says which answers. Text in the composer goes to the supervisor as a plain message: the
question stays open, a gate does not move. Several open items mean several fields, the
cards float up as the chat goes on, and each answer starts the agent's next turn on its
own. Root causes: the open card copies the composer and stands where it was asked; the
core hands each reply to an idle agent at once.

## What other products do (research, summarised)

- The asker groups questions that belong together and gets one answer for all (Claude
  Code's `AskUserQuestion`: 1–4 questions per call; LangGraph: several action requests in
  one interrupt, one "Submit all decisions"; parallel interrupts resumed together, as
  answering one by one fails).
- Answering part of what waits is normal (OpenAI Agents SDK: the rest stays pending).
- Everything that waits is in one place (agent inboxes; orchestrators' Idle/Busy/Waiting).
- Interruptions cost least when batched at a natural break (Horvitz; Iqbal & Bailey).

LADO takes the grouping and the one place, by agent, in the UI: an agent's open questions,
whatever calls asked them, are answered together.

## What the user sees after the change

**In a session's chat**

1. While anything waits, one card stands above the composer: a tab per agent with open
   questions and a tab per open gate, in the order they were asked. Each tab: the agent's
   avatar letter in its colour (a gate's tab: the Flows icon in its run's colour, the
   colour of the run's frame in the team above the chat), the name, the number of open
   items in a muted badge, its top edge in that colour (dashed for a gate). The card's
   ground is the UI's "waits for you" orange. With nothing waiting there is no card.
2. A click shows a tab. The shown tab stays while other tabs change; a new question adds
   to its agent's tab, or adds a tab, without switching.
3. An agent's tab lists its open questions, numbered when more than one: the question,
   its details and files, its choices, **Other…** (own words, when the question takes
   them) and **Skip** (with an optional comment). One click picks a choice, a second
   unpicks it. **Send answer to supervisor** / **Send 2 answers to supervisor** is off
   until each question has an answer or Skip, with "1 of 2 answered" beside it. Sent, the
   agent gets all the answers at once and starts one turn; the tab goes.
4. A gate's tab: the gate's question, the note before it and the artifacts it reads, a
   comment for the next step and the gate's buttons, which answer at once as today.
5. The card is at most half the chat's height; its questions scroll inside, its tabs and
   Send stay in view. The icon at the right of the tabs shows the card over the whole
   window, the rest dimmed; the other icon or Esc brings it back; it comes back by itself
   when nothing waits.
6. In the feed, each open question or gate is one quiet line where it was asked
   ("supervisor asked: Which branch should the PR target? ↓"); the arrow shows its tab and
   marks it. Answered, the question is its closed card as today ("You · answered", "You ·
   skipped" with the comment). The orange hint over the composer is gone; the composer is
   a plain message.
7. A stopped session keeps its gates' tabs, buttons off: "The session is stopped: resume
   it to answer."

**On Needs you**

8. Each session's name, "In the chat", and the same card, answered in place; agents
   waiting in their terminal stay rows as today. A link to an open item (here or in a
   notification) opens the chat with its tab shown.

**Not changed**: `lado answer`, the tmux popup, the gate card on a run's page in Flows, an
agent's page in Agents, the closed question card (LAD-25), the MCP tools.

## Design

The decisions are D1–D16 in `openspec/changes/waiting-card/design.md`. In short:

- Core: `runtime.answer_questions(session, [HumanReply...])` checks every reply, writes them
  all in one transaction (`state.reply_to_questions`) and hands the agent its queue once.
  `answer_question` / `dismiss_question` stay as one-reply calls of it; their two
  endpoints go.
- API: `POST /api/sessions/{name}/answers {answers: [{question, choice, text, skip}]}`.
- UI: `web/src/WaitingCard.tsx` (tabs, picks, Send, gate panel, expand), fed by `waiting`
  (questions) and the session's gates; `Chat.tsx` (feed lines, focus, no hint);
  `Question.tsx` (closed card only, "skipped"); `GateCard.tsx` (`GatePanel` shared;
  `GateRow` gone); `NeedsYou.tsx` (a card per session).

## Docs to change

- `docs/design/ui.md`, The human in the session: "Flow gates" (an open gate is a line and
  a tab of the waiting card; the hint over the composer is gone), "A question", "The open
  question's card" (replaced by "The waiting card", decided 2026-10-13, LAD-28, mockup
  `task/lad-28/mockup-question-card-final.html`), "Answer in the question card"
  ("skipped"); Structure: Needs you; Look: the card's tokens.
- AGENTS.md: Layout (the server's `POST …/answers` in place of the two question
  endpoints); How agents talk ("The human is a participant": the human's replies to one
  agent's questions are handed over together).
- CHANGELOG.md under `## 0.37.0 (unreleased)`.

## Version

0.37.0, the next minor: an API change. No schema migration, no MCP change.
