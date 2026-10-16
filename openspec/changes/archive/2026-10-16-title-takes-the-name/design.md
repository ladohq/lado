## Context

`TitleEdit.tsx` is the one field that edits a session's title, in the head and in a list
row (LAD-66). It holds the title (empty without one) with the name as its placeholder;
Enter and blur save, Esc cancels. The change adds the name as a suggestion that Tab or →
takes (proposal, What Changes).

## Decisions

### D1. When the suggestion shows

The suggestion shows when the field's text is a proper start of the session's name,
compared as typed (case and all, the empty text included), the field is not saving, no
IME composition runs, and the caret is at the text's end with nothing selected. Names
are slugs (`runtime.slug`), so a case-sensitive start is what the human types; one rule,
no folding. The name typed whole shows nothing: there is nothing left to take.

### D2. How it is drawn

Empty: the input's placeholder, as today, so assistive technology reads the name as
before. A start typed: a layer over the input (`aria-hidden`, no pointer events) with the
typed text transparent and the rest of the name in `var(--muted)`, in the input's font,
size and padding, so the rest begins where the caret is. It is shown only while the
input is not scrolled (`scrollLeft === 0`); a start of a name of at most the field's
width never scrolls it. No new colour or token.

### D3. The keys

On keydown with the suggestion shown (D1): Tab without Shift, Ctrl, Alt or Meta, and →
without modifiers, call `preventDefault`, set the text to the name and put the caret at
its end; nothing is sent. In every other case Tab, Shift+Tab and → do what they do today
(Tab leaves the field, and the blur saves it). Keys during an IME composition
(`nativeEvent.isComposing`) are never taken.

### D4. The hint

The caller passes two hints: the one of today and the one while the suggestion shows
(`Tab takes the name · Enter to save · Esc to cancel` in the head; `<name> · Tab takes
the name · Enter to save · Esc to cancel` in the row). The head's suggestion hint drops
`empty shows the name`, which is what the grey says; the rest is the caller's as today,
so the field knows nothing of where it stands. A problem under the field (too long, the
server's refusal) shows in place of either, as today.

### D5. Tests

The rules are the field's own logic: vitest in `TitleEdit.test.tsx` (jsdom keydown,
caret and selection set by the test). A real Tab's focus move and the blur's save need
a browser: one UI e2e in the head (the pencil, Tab, typing on, Enter) and one in a row
(a start typed, Tab, Enter), each with a screenshot; and one that Tab with other text
still leaves and saves.
