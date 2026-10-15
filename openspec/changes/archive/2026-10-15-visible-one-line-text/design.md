## Context

Scale: tweak. The human approved the scale and these choices with the design: the human's
longer texts are cleaned, agents' one-line texts and the title are refused, and the
refusal names the character.

## Decisions

- **D1. One module, `lado/text.py`.** `runtime` imports `artifacts`, and `artifacts` only
  `state`, `flows`, `images`: the rule must sit below both. A module of the standard
  library alone (like `mcp_exec.py`) is cheap to import from hooks. It holds:
  `hidden(char) -> bool` (Cc, Zl, Zp, Cf, but U+200D); `first_hidden(text) -> str | None`;
  `named(char) -> str`, `U+XXXX NAME` by `unicodedata.name`, `U+XXXX` alone for a
  character without a name (the Cc ones); `one_line(text) -> str`, the cleaned form (Cc,
  Zl, Zp to a space, Cf removed, then runs of white space kept as they are, ends
  stripped). No list of code points: categories are Python's `unicodedata`, so a newer
  Unicode keeps the rule.
- **D2. Refuse where the writer gives one field, clean where LADO takes a line from a
  longer text.** A title or an agent's summary is meant as one line: a refusal with the
  character named lets the writer fix it. The human's chat message, gate comment and
  flow-set reason are free text; refusing them for an invisible character pasted from a
  browser would puzzle the human, and the whole text survives in the body.
- **D3. The body keeps the whole text whenever the line is not exactly it.** Today
  `_human_text` puts the text in the body only when it has more lines or was cut; a
  cleaned line now counts too, and `force` gets the same rule (its note was cut with no
  body). No silent drop.
- **D4. Error texts keep their first words** (`a title is one line`, `summary must be one
  line`, `note_summary must be one line`, `title must be one line`), adding `of visible
  text: <U+XXXX NAME> is not allowed`, then the existing pointer to where the details go.
  Agents and tests that match the start still match.
- **D5. Cf is removed, not made a space.** Zero-width and bidi characters sit inside
  words; a space there would split the word. Cc, Zl and Zp separate text, so a space.
- **D6. No escape at print and no migration** (proposal, Out of scope).

## Test layers

Unit only: the rule and each caller are pure functions over strings and `lado.db`; no
process boundary changes (the typed line is the same summary as before).
