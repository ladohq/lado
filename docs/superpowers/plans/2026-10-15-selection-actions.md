# Selected text and copy buttons Implementation Plan

**Goal:** A selection bar (Copy, Quote in reply) over text selected in the UI's readable
areas, and copy buttons on code blocks and messages shown on hover.

**Architecture:** One `SelectionBar` mounted in the shell reacts to selections whose ends
share one area marked `data-quote` by the component that renders it; `quote.ts` builds the
quote's text, `quotes.ts` hands it to the page's composer or opens the session's chat. The
copy buttons reuse `Copy.tsx`'s `useCopy`; their hover rule is CSS.

**Tech Stack:** React + TypeScript (Vite), vitest, pytest-playwright (Chromium).

**Spec:** `openspec/changes/selection-actions/` (proposal, `specs/selection-actions/spec.md`,
`design.md` D1–D8) and `docs/superpowers/specs/2026-10-15-selection-actions-design.md`.
Mockup: run artifact `task/lad-67/mockup-selection.html`, the quote icon of variant 1.

## Global Constraints

- The UI's strings are English: tooltips/accessible names "Copy", "Quote in reply", "Copy
  code", "Copy message"; notes "Copied" and "Press ⌘C / Ctrl+C to copy".
- The note lasts `COPIED_MS` (2000 ms, `Copy.tsx`).
- No server, API, schema or CLI change; `web/openapi.json` and `web/src/api.gen.ts` untouched.
- Quote never changes a composer's recipient.
- An artifact's lead line: `In <full name>:`, `In <full name>, an earlier record:`, with
  ` (lines a–b)` (en dash) or ` (line a)` before the colon for a text or code artifact.
- CHANGELOG.md: one line under `## 0.39.0 (unreleased)`.

## Review Focus

- A selection from one message into the next: no bar, and nothing breaks (Ctrl+C works) —
  test in Task 4's e2e.
- A text artifact line that holds backticks (```` ``` ````): the fence must be longer —
  test in Task 1.
- Quote while the composer already has text and trailing blank lines: exactly one blank
  line between — test in Task 1.
- Quote on Needs you for a card of a session other than the one last opened: the chat of
  the card's session opens — test in Task 4's e2e via `data-quote-session`.
- Pressing a bar button must not collapse the selection (the selection is still there after
  Copy) — test in Task 4's e2e.

---

### Task 1: The quote's text (`quote.ts`)

**Files:** Create `web/src/quote.ts`, `web/src/quote.test.ts`.

**Interfaces — Produces:**
`blockquote(text: string): string`; `fenced(lines: string[]): string`;
`artifactLead(fullName: string, earlier: boolean, lines?: [number, number]): string`;
`withQuote(current: string, quote: string): string`.

- [ ] Step 1: tests

```ts
import { describe, expect, it } from "vitest";
import { artifactLead, blockquote, fenced, withQuote } from "./quote";

describe("quote", () => {
  it("prefixes each line, an empty one with a bare >", () => {
    expect(blockquote("A\n\nB\n\n")).toBe("> A\n>\n> B");
  });
  it("names the artifact and its lines", () => {
    expect(artifactLead("task/x/design", false)).toBe("In task/x/design:");
    expect(artifactLead("task/x/notes.py", false, [12, 13])).toBe("In task/x/notes.py (lines 12–13):");
    expect(artifactLead("task/x/notes.py", false, [7, 7])).toBe("In task/x/notes.py (line 7):");
    expect(artifactLead("task/x/design", true)).toBe("In task/x/design, an earlier record:");
  });
  it("fences with more backticks than the lines hold", () => {
    expect(fenced(["  a = 1"])).toBe("```\n  a = 1\n```");
    expect(fenced(["x = '```'"])).toBe("````\nx = '```'\n````");
  });
  it("appends after one blank line and ends on a new line", () => {
    expect(withQuote("", "> A")).toBe("> A\n");
    expect(withQuote("Почему?\n\n\n", "> A")).toBe("Почему?\n\n> A\n");
  });
});
```

- [ ] Step 2: `cd web && npx vitest run src/quote.test.ts` fails (no module).
- [ ] Step 3: implement.

```ts
// The text a quote puts into the composer (docs/design/ui.md, Selected text and copy
// buttons): a Markdown quote, an artifact's lead line, a text artifact's lines fenced.
export function blockquote(text: string): string {
  const lines = text.replace(/\r\n?/g, "\n").replace(/\s+$/, "").split("\n");
  return lines.map((line) => (line.trim() ? `> ${line}` : ">")).join("\n");
}

export function fenced(lines: string[]): string {
  const longest = Math.max(0, ...lines.map((line) => Math.max(0, ...(line.match(/`+/g) ?? []).map((run) => run.length))));
  const fence = "`".repeat(Math.max(3, longest + 1));
  return [fence, ...lines, fence].join("\n");
}

export function artifactLead(fullName: string, earlier: boolean, lines?: [number, number]): string {
  const where = lines ? (lines[0] === lines[1] ? ` (line ${lines[0]})` : ` (lines ${lines[0]}–${lines[1]})`) : "";
  return `In ${fullName}${earlier ? ", an earlier record" : ""}${where}:`;
}

export function withQuote(current: string, quote: string): string {
  const before = current.replace(/\s+$/, "");
  return before ? `${before}\n\n${quote}\n` : `${quote}\n`;
}
```

- [ ] Step 4: the test passes. Step 5: commit `The quote's text for the selection bar (LAD-67)`.

### Task 2: Composers take a quote (`quotes.ts`, `Composer.tsx`)

**Files:** Create `web/src/quotes.ts`, `web/src/quotes.test.ts`; modify `web/src/Composer.tsx`,
`web/src/Composer.test.tsx`, `web/src/WaitingCard.tsx` (fold on quote).

**Interfaces — Consumes:** `withQuote` (Task 1), `chatPath` (`paths.ts`).
**Produces:** `registerComposer(session: string, insert: (quote: string) => void): () => void`;
`sendQuote(session: string, quote: string, navigate: (path: string) => void): void`;
`takePending(session: string): string | null`;
`onQuote(session: string, listener: () => void): () => void`.

- [ ] Step 1: tests — `quotes.test.ts`: with a registered composer `sendQuote` calls its
  `insert` and not `navigate`; without one it calls `navigate(chatPath(session))` and
  `takePending(session)` returns the quote once, then null; `onQuote` listeners of that
  session run on each `sendQuote`, others not. `Composer.test.tsx`: after the composer
  mounts, `sendQuote("s", "> A", nav)` makes the field `Почему?\n\n> A\n` from `Почему?`,
  the field focused, `selectionStart === value.length`, the "to" line unchanged; a pending
  quote is in the field on mount.
- [ ] Step 2: run `cd web && npx vitest run src/quotes.test.ts src/Composer.test.tsx`: fail.
- [ ] Step 3: implement `quotes.ts` (a `Map<string, Set<insert>>` of mounted composers — the
  latest registered wins when two are mounted —, a `Map<string, string>` of pending quotes,
  a `Map<string, Set<listener>>`); in `Composer` a `useEffect` that registers an `insert`
  doing `setText((t) => withQuote(t, quote))`, then focuses the field and moves the cursor to
  the end after the render (`requestAnimationFrame`), and on mount takes `takePending`.
  `WaitingCard` subscribes with `onQuote(session, () => setExpanded(false))`.
- [ ] Step 4: tests pass; `make web`. Step 5: commit `Composers take a quote (LAD-67)`.

### Task 3: Icons and the readable areas

**Files:** modify `web/src/icons.tsx` (`CopyIcon`, `QuoteIcon`), `Chat.tsx`, `Agents.tsx`,
`Flows.tsx`, `NeedsYou.tsx`, `WaitingCard.tsx`, `GateCard.tsx`, `Recommendation.tsx`,
`ArtifactView.tsx`; tests `Chat.test.tsx`, `ArtifactView.test.tsx`.

**Produces:** the attributes of D1: `data-quote="text" | "markdown" | "code"`,
`data-quote-session`, `data-quote-artifact`, `data-quote-earlier` (present only for an
earlier record), `data-line` on each row of the code view.

- [ ] Step 1: tests — `Chat.test.tsx`: a message's `.feed-main` has `data-quote="text"` and
  `data-quote-session`; `ArtifactView.test.tsx`: a Markdown record's article has
  `data-quote="markdown"` and `data-quote-artifact`, a text record's table `data-quote="code"`
  with `data-line` on each row, an older record `data-quote-earlier`, an HTML record none.
- [ ] Step 2: fail. Step 3: add the attributes where the table of the design doc says; the
  icons as in the mockup:

```tsx
export const CopyIcon = () => (
  <Icon>
    <rect x="8" y="8" width="12" height="12" rx="2" />
    <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
  </Icon>
);

// A speech bubble with two quote marks: Quote in reply.
export const QuoteIcon = () => (
  <Icon>
    <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-9l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
    <path d="M8.5 13v-2.2c0-1 .5-1.6 1.6-1.8M13.5 13v-2.2c0-1 .5-1.6 1.6-1.8" />
  </Icon>
);
```

- [ ] Step 4: pass; `make web`. Step 5: commit `Readable areas say what a quote needs (LAD-67)`.

### Task 4: The selection bar (`SelectionBar.tsx`)

**Files:** create `web/src/SelectionBar.tsx`, `web/src/SelectionBar.test.tsx`; modify
`web/src/Shell.tsx` (mount once), `web/src/styles.css` (`.selection-bar`); create
`tests/ui/test_selection.py`.

**Consumes:** Task 1's functions, `sendQuote` (Task 2), the attributes (Task 3), `Tooltip`,
`COPIED_MS`, `CopyIcon`, `QuoteIcon`.

- [ ] Step 1: vitest — `SelectionBar.test.tsx` for its pure helper
  `areaOf(selection): HTMLElement | null` (same closest `[data-quote]` for both ends; null
  inside `input`, `textarea`, `[contenteditable]`, `.xterm`, or for two areas) and
  `quoteOf(area, range): string` (text area → `blockquote(range.toString())`; markdown →
  lead + blockquote; code → lead with the rows' `data-line` span + `fenced` of the rows'
  `td.line` text, the first cut at the range's start offset, the last at its end).
- [ ] Step 2: UI e2e `tests/ui/test_selection.py` (marker `ui`, `wide` fixture as in
  `test_chat.py`), selecting by `page.evaluate` of a `Range` over a text node, then a
  `mouseup`; each test with `shot(page)`:
  - `test_the_bar_shows_over_a_message_and_esc_hides_it` (both icons, tooltip "Quote in
    reply" on hover, Esc hides);
  - `test_copy_copies_the_selection_and_keeps_it` (grant clipboard; `readText()` equals the
    fragment; `getSelection().toString()` unchanged; "Copied");
  - `test_quote_appends_to_the_chat_composer` (prefilled "Почему?"; value
    `Почему?\n\n> …\n`; recipient line still "to supervisor");
  - `test_quote_on_an_agent_page_goes_to_its_composer`;
  - `test_quote_from_flows_opens_the_chat`;
  - `test_quote_from_a_text_artifact_names_its_lines` (a `.py` artifact, rows 2–3);
  - `test_quote_from_a_markdown_artifact_in_the_panel`;
  - `test_no_bar_in_the_composer_html_or_across_two_messages`;
  - `test_quote_folds_an_expanded_card` (`gated_session` or a question);
  - `test_the_bar_stands_below_on_a_touch_screen` (a new context `has_touch=True,
    is_mobile=True`, viewport 390×844: bar's top > the range's bottom).
- [ ] Step 3: run `uv run pytest -m ui tests/ui/test_selection.py`: fail.
- [ ] Step 4: implement: listen to `selectionchange` (rAF-throttled), `keydown` Esc,
  `pointerdown` outside, `scroll` (capture) — hide; place by `range.getBoundingClientRect()`
  (fixed; 8 px gap; above, or below when `matchMedia("(hover: none)")`; clamped to the
  window); `role="toolbar"` `aria-label="Selection"`; each button `onPointerDown` and
  `onMouseDown` `preventDefault()`. Copy: `document.execCommand("copy")`, else
  `navigator.clipboard.writeText(sel.toString())`, else the hand note. Quote:
  `sendQuote(area.dataset.quoteSession, quoteOf(area, range), navigate)`, then collapse the
  selection and hide.
- [ ] Step 5: vitest and e2e pass; `make web`, `make lint`. Step 6: commit `The selection
  bar copies and quotes selected text (LAD-67)`.

### Task 5: Copy code and Copy message on hover

**Files:** modify `web/src/ChatText.tsx` (`pre` in `COMPONENTS`), `web/src/FeedRow.tsx`
(`copy?: string`), `web/src/Chat.tsx` (`messageText`, pass `copy`), `web/src/Agents.tsx`
(its messages), `web/src/styles.css`; tests `Body.test.tsx`, `Chat.test.tsx`; add to
`tests/ui/test_selection.py`.

**Produces:** `messageText(message: MessageInfo): string` (D7); a small `CopyIconButton({
label, text })` in `Copy.tsx` reusing `useCopy` and `CopyField` (as `CopyButton`, with
`CopyIcon`).

- [ ] Step 1: tests — `Chat.test.tsx`: `messageText` of the human's (`body || summary`), of
  an agent's with a body ("Раунд 1\n\n1. Какие действия?"), with a body that repeats the
  summary (the body only), without a body (the summary). `Body.test.tsx`: a fenced block
  renders a button "Copy code". e2e: `test_copy_buttons_show_on_hover` (Copy message not
  visible — `to_have_css("opacity", "0")` — then visible after `hover()`; Copy code copies
  exactly), `test_copy_buttons_always_show_on_a_touch_screen`.
- [ ] Step 2: fail. Step 3: implement; CSS:

```css
@media (hover: hover) {
  .code-block .copy-icon-button,
  .feed-row .copy-icon-button {
    opacity: 0;
  }
  .code-block:hover .copy-icon-button,
  .feed-row:hover .copy-icon-button,
  .copy-icon-button:focus-within {
    opacity: 1;
  }
}
```

- [ ] Step 4: pass; `make web`, `uv run pytest -m ui tests/ui/test_selection.py
  tests/ui/test_chat.py tests/ui/test_artifacts_tab.py`. Step 5: commit `Copy code and Copy
  message show on hover (LAD-67)`.

### Task 6: Docs

**Files:** `docs/design/ui.md` (the new section "Selected text and copy buttons (decided
2026-10-15, LAD-67)" after "Report a bug", its content as named in the design doc's "Change
to docs/design/ui.md"), `CHANGELOG.md` (under 0.39.0: "Selecting text in the UI shows a
small bar to copy it or quote it into the composer; a quote from an artifact names it and
its lines. Code blocks and messages have a copy button that shows on hover.").

- [ ] Commit `Document the selection bar and copy buttons (LAD-67)`.

## Regression run

`make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_selection.py
tests/ui/test_chat.py tests/ui/test_artifacts_tab.py tests/ui/test_agents_tab.py
tests/ui/test_flows_tab.py tests/ui/test_needs_you.py`, `openspec validate --specs --strict`.
No integration, smoke or live test applies (nothing crosses processes; no provider).
