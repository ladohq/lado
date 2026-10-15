Task: LAD-67

## Why

The web UI shows a lot of text the human reads and acts on: the agents' messages in the
chat, notes of flow steps, questions and gates, Markdown and text artifacts (designs,
plans, reports). Today the only way to take a part of it is the browser's own Ctrl+C, which
a mouse user does not see, and the only way to answer an agent about one place in a long
report or design is to retype or paste that place by hand and say where it came from. Chat
applications solve both with a small bar over the selected text (copy, reply with a quote)
and copy buttons on code blocks and messages (the research: run artifact
`task/lad-67/research`).

Root cause: the UI treats read-only text as inert; nothing connects a selection to the
clipboard or to the composer, and nothing marks where a quoted fragment came from.

## What Changes

- **A selection bar.** When the human selects text in a readable area of the UI, a small
  bar of two icon buttons shows above the selection (below it on a touch screen, where the
  system shows its own menu above): **Copy** (two sheets) and **Quote in reply** (a speech
  bubble with quote marks), each named by the UI's tooltip. Esc, a click elsewhere, a
  scroll of the area or an empty selection hide it.
- **Copy** copies the selection as Ctrl+C would and says "Copied" in place of the bar for
  2 seconds.
- **Quote** appends the selection to a composer as a Markdown quote (`> ` lines), the
  cursor on a new line under it; the composer's recipient does not change. The composer is
  the one of the page the selection is on (the session's chat: the supervisor; an agent's
  page: that agent). A page without a composer (the Artifacts tab, Flows, Needs you, an
  artifact panel over them) opens the session's chat with the quote in its composer. A
  quote from an artifact starts with the line `In <full name>:`; from a text or code
  artifact, `In <full name> (lines a–b):` and the lines as a fenced code block, so the
  agent can find the place with `read_artifact` and indentation survives.
- **Copy buttons shown on hover**: **Copy code** in the corner of each code block of a
  Markdown text (messages, notes, cards, Markdown artifacts), and **Copy message** in the
  head of each message of the chat and of an agent's page (the message's Markdown text).
  Both are hidden until the pointer is over the block or the message, or the keyboard's
  focus reaches them; on a touch screen, which has no hover, they are always shown.
- Docs: `docs/design/ui.md` (a new section "Selected text and copy buttons"),
  CHANGELOG.md under 0.39.0. Part of a minor release (a UI feature); 0.39.0 is already
  the next version on main.

## Scope

- The web UI only (`web/src/`): the selection bar, the quote's text, the composer taking a
  quote, the copy buttons, two icons; their unit tests (vitest) and UI e2e tests.
- `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- **"Explain" or other prepared questions on a selection.** The human's decision: a quote
  plus the human's own words covers it, and a third button makes the bar larger.
- **Changing the recipient on Quote** (e.g. to the worker whose message was quoted). In the
  chat the composer writes to the supervisor; a recipient that changes by itself would go
  unnoticed. The human's decision.
- **Comments anchored to a fragment of an artifact, links to a fragment, highlights.** That
  is reviewing artifacts, a feature of its own that must keep anchors; the browser already
  offers a link to a highlight.
- **Selections in the agent's terminal** (xterm and tmux have their own selection and copy),
  **in input fields** (the browser's own menu), **inside an HTML artifact** (a sandboxed
  frame without the UI's origin: the page cannot see its selection) and **on images**.
- **A quote's author line for a message** (`<agent> wrote:`): not agreed; the human writes
  their own words around the quote.
- **Server, API, schema, CLI, providers**: nothing changes there.

## Acceptance criteria

- AC-1: Selecting text in a message of the session's chat shows a bar with two icon
  buttons, Copy and Quote, above the selection; hovering each shows its tooltip ("Copy",
  "Quote in reply"). Esc, a click elsewhere, scrolling the feed or clearing the selection
  hides it.
- AC-2: The bar shows for selections in: the chat's messages, the waiting card's questions,
  gates and recommendations, closed gates and run events, an agent's page's messages, Flows'
  notes, Needs you's cards, a Markdown or text artifact in the panel and in the Artifacts
  tab. It does not show for a selection in an input field, the composer, a terminal, an
  HTML artifact or the UI's chrome (rail, tabs, head).
- AC-3: Copy puts the selected text on the clipboard as Ctrl+C would and shows "Copied" for
  2 seconds; the selection stays.
- AC-4: Quote in the chat appends `> <line>` for each selected line to the composer's text
  (after a blank line when the composer is not empty), puts the cursor on a new line under
  it and focuses the composer; the recipient stays the supervisor. On an agent's page it is
  that agent's composer.
- AC-5: Quote from a Markdown artifact starts with `In <full name>:`; from a text or code
  artifact with `In <full name> (lines a–b):` (`(line a)` for one line) followed by the
  selected lines as a fenced code block, without the line numbers.
- AC-6: Quote on the Artifacts tab, Flows, Needs you or an artifact panel over them opens
  the session's chat with the quote in the composer. Quote from an expanded waiting card
  folds the card so the composer shows.
- AC-7: A code block shows Copy code in its corner only while the pointer is over it or the
  focus is on the button; it copies the code exactly and says "Copied".
- AC-8: A message of the chat or of an agent's page shows Copy message in its head only
  while the pointer is over it or the focus is on the button; it copies the message's
  Markdown text and says "Copied".
- AC-9: On a touch screen (no hover) Copy code and Copy message are always shown, and the
  selection bar shows below the selection.
