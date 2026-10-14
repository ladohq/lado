## Context

What the web UI has now (main at 0.38.0, 0.39.0 unreleased):

| Piece | Where | What it gives |
|---|---|---|
| Copying | `web/src/Copy.tsx`: `useCopy` (Clipboard API, then `execCommand`), `CopyButton`, `CopyField` | copies a given string with a note for `COPIED_MS` (2 s); used by Copy link, Copy address, Copy text |
| Markdown | `ChatText.tsx`: `Body` (react-markdown, `COMPONENTS` with a `table` override), `Preview` | every message, note, card and Markdown artifact |
| Text artifacts | `ArtifactView.tsx`: `Text`, a `table` of `td.line-number` (`user-select: none`) and `td.line` | the viewer of the panel and of the Artifacts tab |
| Composer | `Composer.tsx`, its text in local state; `Chat.tsx` (to the supervisor), `Agents.tsx` (to `to`) | the human's message; a page without one: Artifacts, Flows, Needs you |
| Feed rows | `FeedRow.tsx`, `Chat.tsx`'s `Message`/`MessageText` | a message's head (who, aside, time) and its text |
| Hover rule | `styles.css`: one `@media (hover: none)` block | where the UI already tells touch from pointer |

Nothing in the UI reacts to a selection; copying a part relies on Ctrl+C, quoting on
retyping. Root cause: read-only text has no actions, and nothing connects a selection to
the clipboard or to a composer, or says where a fragment came from.

## Options

1. **A menu per message only** (hover: Copy message, Reply). Cost: least code. But no
   fragment: the human still cuts the part they mean by hand, and artifacts, where long
   texts live, get nothing.
2. **Chosen: one selection bar for every readable area, plus copy buttons on hover.** Cost:
   one component mounted once, a small quote module, the areas marked in the components that
   render them, two copy buttons. No server change.
3. **Replace the browser's context menu** (right click) with LADO's. Cost: as option 2, and
   it takes away the browser's own menu (search, translate, spell), is not discoverable, and
   does not exist on touch screens. Rejected.

Held against AGENTS.md's Design principles and ROADMAP:

- **Neutral core**: the UI only, no provider involved; quotes reach any agent as text
  through the existing composer and queue.
- **One source of truth**: an area declares itself readable by a data attribute where it
  is rendered (D1), never a list of selectors in the bar; one copy path (`Copy.tsx`, D2);
  one builder of a quote's text (D3); a message's copied text from the same rule the chat
  shows it by (D7).
- **No silent drops**: a copy that fails says how to copy by hand (D2); a quote for a page
  without a composer opens the chat rather than being lost (D4).
- **Only what is used**: two actions on the bar, two buttons, no settings.
- ROADMAP: stage 7 (the web UI). Nothing coming depends on it; a later review of artifacts
  (comments on a fragment) can reuse the areas and the bar.

## Decisions

### D1. One bar, areas that declare themselves

`SelectionBar.tsx` is mounted once in the shell (`Shell.tsx`) and listens to the document's
`selectionchange` (and `pointerup`, `keyup`). It shows only when the selection is not
blank and lies in one area: the closest `[data-quote]` ancestor of its start, not inside
`input`, `textarea`, `[contenteditable]` or `.xterm`, holding its end too, or the
selection takes no text past that area (a triple click on an area's last line ends at the
next block's start, which is another area or the composer). The area's attributes say
what a quote needs: `data-quote="text"` (a message, note, card), `data-quote="markdown"`
plus `data-quote-artifact="<full name>"` and `data-quote-earlier` when the record is not the
latest, `data-quote="code"` with the same artifact attributes on the text viewer (each row
`data-line="<n>"`), and `data-quote-session="<name>"` on every area (Needs you shows many
sessions). The bar is positioned by the selection range's `getBoundingClientRect()`, fixed,
above it (below with `(hover: none)`), kept inside the window. **Why:** the components that
render text know what they render; a list of selectors in the bar would drift.

### D2. Copy copies the live selection

Copy runs `document.execCommand("copy")` while the selection is still there, so the
clipboard gets what Ctrl+C gives (plain text and the browser's HTML). When that returns
false or throws, `navigator.clipboard.writeText(selection.toString())`; when both fail, the
bar says "Press ⌘C / Ctrl+C to copy". The bar's buttons call `preventDefault` on
`pointerdown`/`mousedown`, so pressing them does not collapse the selection. The note uses
`COPIED_MS` from `Copy.tsx`. **Why:** the human expects the same result as Ctrl+C; the
existing `useCopy` copies a given string and stays as it is for the copy buttons (D5).

### D3. The quote's text in one module

`quote.ts` holds pure functions: `blockquote(text)` (`> ` per line, `>` for an empty one,
trailing blank lines dropped), `artifactLead(fullName, earlier, lines?)` (`In <name>:`,
`In <name>, an earlier record:`, ` (lines a–b)` / ` (line a)` before the colon) and
`fenced(lines)` (a fence one backtick longer than the longest run of backticks in the lines,
at least three). For the text viewer the lines come from the rows between the range's
first and last `data-line`, the first cut at the range's start offset and the last at its
end, never from `selection.toString()` (a table's string has tabs and depends on the
browser). `withQuote(current, quote)` appends: `quote + "\n"` to an empty composer, else
`current` with its trailing whitespace trimmed, `"\n\n"`, `quote`, `"\n"`. **Why:** the text
is what agents read; one place makes it testable in vitest.

### D4. A quote reaches a composer through a small store

`quotes.ts` keeps the mounted composers (`register(session, to | null, insert)` from
`Composer`, returning its unregister) and one pending quote per session. `sendQuote(session,
text, navigate)`: when a composer of that session is mounted on the page, it gets the text
(`insert`), which sets its text by `withQuote`, focuses the field and puts the cursor at the
end; otherwise the quote is kept pending and the page goes to `chatPath(session)`, whose
composer takes it on mount. The waiting card subscribes to `onQuote(session, fold)` and
folds when expanded. An artifact panel over a page with a composer leaves the panel open.
**Why:** the composer's text stays its own state; no global draft store for one action.

### D5. Copy code and Copy message reuse `useCopy`

`ChatText.tsx`'s `COMPONENTS` gets a `pre` override: the block in a `div.code-block` with an
icon button "Copy code" (`useCopy` with the code's `textContent`). `FeedRow` takes an
optional `copy` text and shows an icon button "Copy message" at the end of its head (also in
a continued row, at its top right). The note "Copied" shows in a `role="status"` beside the
button for `COPIED_MS`; a failed copy shows the `CopyField` as `CopyButton` does. CSS: under
`@media (hover: hover)` the buttons have `opacity: 0` and show on `.code-block:hover`,
`.feed-row:hover` and `:focus-visible` (opacity, not `display`, so Tab reaches them).
**Why:** the existing copy path and its fallback, no second one.

### D6. Two icons

`icons.tsx` gets `CopyIcon` (two overlapping sheets) and `QuoteIcon` (a speech bubble with
two quote marks), drawn on the 24-unit grid with 1.6 strokes like the others; the shapes of
the mockup's variant 1 (`task/lad-67/mockup-selection.html`). `ClipboardIcon` stays where it
is used. **Why:** the human chose the bubble; the two sheets are the copy sign people know.

### D7. A message's copied text follows the chat's rule

`messageText(message)` beside `MessageText` in `Chat.tsx`: the human's `body || summary`;
an agent's `summary` and `body` separated by a blank line, the summary left out when
`repeatsSummary(summary, body)`, the body left out when empty. **Why:** what is copied is
what the human sees, by the same rule.

### D8. Touch screens

`matchMedia("(hover: none)")` decides where the bar stands; the copy buttons' visibility is
CSS only (D5). **Why:** the system shows its own copy menu above a selection on touch.

## Risks

- `execCommand("copy")` is deprecated but kept by every browser; the Clipboard API is the
  fallback (D2), as in `Copy.tsx` the other way round.
- A selection that starts in one message and ends in another has different closest areas:
  no bar, Ctrl+C still works. Accepted: a quote of two messages has no single source.
