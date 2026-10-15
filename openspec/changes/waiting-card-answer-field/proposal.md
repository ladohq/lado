Task: LAD-70

## Why

The field where the human writes an own answer in the waiting card is too small to write
in. It opens one line high, so an answer longer than a line shows one line at a time. Its
corner handle makes it taller only downwards, and the card's list of questions scrolls
inside the card under its fixed Send row: the field's lower edge, with the handle and the
caret, goes under the Send row and off the bottom of the screen (the task's screenshot:
the card expanded, the field cut by the window's edge).

Root cause: the card's text fields (`WaitingCard.tsx`'s `waiting-field`, one row;
`GateCard.tsx`'s comment for the next step, two rows) have a fixed number of rows and
`resize: vertical`, inside a list that scrolls (`.waiting-list`, `overflow: auto`). A
manual resize grows the field inside that scrolling list, which does not follow it, and
nothing sizes the field by its text. The field is as wide as its question already; only
its height is wrong. The composer below the card does not have the problem: its field
grows with its text up to 8 lines, then scrolls inside (`Composer.tsx`, `grow`).

## What Changes

Chosen with the human (mockup `task/lad-70/mockup-answer-field.html`, option A):

- The waiting card's text fields, **Your own answer** (Other…), **Why you skip it
  (optional)** (Skip) and a gate's **Comment for the next step (optional)**, open 3 lines
  high, grow with their text up to 8 lines, then scroll inside. They have no resize
  handle. Their width stays the question's full width.
- While the human types in one of them and it grows, the field's lower edge with the caret
  stays in view: the card's list scrolls by as much as the field grew past it.
- The gate's comment field is one component (`GatePanel`), so it grows the same way where
  the gate's panel shows outside the card too (the Flows tab).
- The composer keeps its own range (1 to 8 lines); its height rule becomes the one shared
  rule of all these fields.
- Docs: `docs/design/ui.md` (The waiting card: its fields), CHANGELOG.md.
- A patch-level fix (no API, CLI, MCP or schema change); its CHANGELOG line goes under the
  open heading `## 0.40.0 (unreleased)`.

## Scope

- `web/src/`: a shared height rule for text fields (taken out of `Composer.tsx`), used by
  the composer, `WaitingCard.tsx`'s field and `GateCard.tsx`'s comment; `styles.css`
  (`.waiting-field`, `.answer textarea`: no resize handle, a line height to count by).
- Tests: vitest of the height rule and of the card's fields; UI e2e in
  `tests/ui/test_chat.py` (an own answer) and `tests/ui/test_gates.py` (a gate's
  comment) with screenshots.

## Out of scope

- **A fixed 4-line field** (mockup option B): a short answer takes room it does not need
  and a long one shows in pieces; the human chose option A.
- **The field in the Send row, outside the scrolling list**: a tab with several questions
  has a field per question and one Send row.
- **A manual resize handle that grows the field upwards**: a field that sizes itself by
  its text needs no handle; a handle in a scrolling list is what broke.
- **A larger range in the expanded card**: 8 lines, as the composer, in every view; the
  expanded card shows more of the question around the field, which is what it is for.
- **Other text fields of the UI** (the New session window's first message, the link
  popover, the artifact panel's): not in the task, and none sits in a scrolling list
  under a fixed row.

## Impact

- UI only: the waiting card's fields and the gate's comment field size themselves; no
  API, CLI, schema or provider change.
