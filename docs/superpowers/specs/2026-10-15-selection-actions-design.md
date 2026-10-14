# Selected text and copy buttons: design

Task: LAD-67. openspec change: `selection-actions` (proposal, delta spec, `design.md` with
decisions D1–D8). Research: run artifact `task/lad-67/research`. Mockup:
`task/lad-67/mockup-selection.html` (sections 1, quote icon variant 1 chosen; 2; 3; 4).

## What the human gets

1. Select text in a message, note, card or artifact: a small bar of two icons shows above
   it. **Copy** copies it as Ctrl+C would. **Quote in reply** puts it into the composer as
   a Markdown quote; from an artifact with a first line naming it (and its lines for a text
   or code artifact, the lines then as a code block).
2. Code blocks and messages get a copy icon that shows when the pointer is over them.

Decided with the human (2026-10-15): Copy and Quote only, no "Explain"; a small bar of icons
without labels, the quote icon a speech bubble with quote marks; everywhere text is read
(chat, agent pages, cards, Flows notes, Needs you, Markdown and text artifacts); the
recipient never changes on Quote; pages without a composer open the session's chat; Copy
code and Copy message both, hidden until hover, always shown on touch screens.

## How it works

- **Areas** (D1). Each component that renders readable text marks its root with
  `data-quote` (`text`, `markdown`, `code`) and `data-quote-session`; an artifact's body
  also `data-quote-artifact` and, for an older record, `data-quote-earlier`; the text
  viewer's rows `data-line`. The bar shows only for a selection whose both ends have the
  same closest area.

  | Component | Area |
  |---|---|
  | `Chat.tsx` `Message`, run groups, closed gate lines | each message's `.feed-main`; each run event; each closed gate's line (`text`) |
  | `WaitingCard.tsx`, `GateCard.tsx`, `Recommendation.tsx` | each question's, gate note's and recommendation's text (`text`) |
  | `Agents.tsx` | each message on the agent's page (`text`) |
  | `Flows.tsx` | each note (`text`) |
  | `NeedsYou.tsx` | each card's texts (`text`), with its session |
  | `ArtifactView.tsx` `Text` | `article.artifact-markdown` (`markdown`), the code view's table (`code`) |

  HTML artifacts (an iframe), images, the composer, inputs and terminals are not areas.
- **Bar** (D1, D2, D8): `SelectionBar.tsx` in the shell; fixed, above the selection (below
  on `(hover: none)`), inside the window; hidden on Esc, a click outside it, a scroll of the
  feed or panel, an empty selection. Copy: `execCommand("copy")` on the live selection,
  then the Clipboard API with the selection's string, then "Press ⌘C / Ctrl+C to copy".
- **Quote** (D3, D4): `quote.ts` builds the text; `quotes.ts` hands it to the page's
  composer, or keeps it and opens `chatPath(session)`; the waiting card folds.
- **Copy buttons** (D5, D7): `pre` in Markdown → `.code-block` with Copy code; `FeedRow`'s
  `copy` → Copy message; visibility by CSS under `(hover: hover)`.

## Change to docs/design/ui.md

A new section after "Report a bug": **Selected text and copy buttons (decided 2026-10-15,
LAD-67)**, holding: the readable areas and the ones that are not; the bar (two icons,
tooltips, where it stands, what hides it); Copy's result and fallback; Quote's text (the
`> ` quote, the artifact's lead line, the fenced lines of a text artifact), which composer
takes it and the chat opened for pages without one, the waiting card folding; Copy code and
Copy message, hidden until hover, shown on touch; the mockup's name. The Tasks list gets no
new item (this is not a roadmap task).

## Tests per requirement

| Requirement | Layer | Tests |
|---|---|---|
| Selected text in a readable area shows the selection bar | UI e2e (needs a real selection, layout and tooltips) | `tests/ui/test_selection.py`: bar on a message, tooltip, Esc, none in the composer, none in an HTML artifact, below the selection on a touch context (`has_touch`, `is_mobile`) |
| Copy on the selection bar copies the selection as Ctrl+C would | UI e2e | copy a fragment, read the clipboard (granted), selection kept, "Copied" |
| Quote … into a composer as a Markdown quote | vitest + UI e2e | `quote.test.ts` (`blockquote`, `withQuote`); `quotes.test.ts` (mounted composer, pending + navigate, fold subscriber); `Composer.test.tsx` (insert: text, cursor, focus); e2e: chat, agent page, Flows → chat, expanded card folds |
| A quote from an artifact names the artifact | vitest + UI e2e | `quote.test.ts` (`artifactLead`, `fenced` with backticks inside, one line, earlier record, cut first/last line); e2e: Markdown artifact in the panel, two lines of a text artifact |
| Code blocks and messages have copy buttons shown on hover | vitest + UI e2e | `ChatText.test.ts`/`Body.test.tsx` (`pre` gets a Copy code button), `Chat.test.tsx` (`messageText` cases); e2e: hidden then shown on hover, copies exactly, always shown on a touch context |

No server, integration, plugin, smoke or live test: nothing crosses processes and no
provider changes. Regression: `make web` (tsc, vitest, build), `make lint`, `make test`,
`uv run pytest -m ui tests/ui/test_selection.py tests/ui/test_chat.py
tests/ui/test_artifacts_tab.py`.
