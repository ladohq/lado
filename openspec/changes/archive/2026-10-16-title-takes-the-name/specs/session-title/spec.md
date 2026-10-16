## ADDED Requirements

### Requirement: Tab takes the session's name into the title field

The title field SHALL offer the session's name as a suggestion while its text is a
proper start of the name, compared case-sensitively, the empty text included, with the
caret at the text's end, nothing selected, no save in flight and no input method
composing: the empty field SHALL show the name grey as its placeholder, and a start typed
SHALL show the rest of the name grey after it. While the suggestion shows, Tab without
modifiers and → without modifiers SHALL make the name the field's text with the caret at
its end, keep the focus in the field and send nothing. Otherwise Tab, Shift+Tab and →
SHALL do what they do in any field (Tab leaves the field, which saves it). While the
suggestion shows, the hint under the field SHALL read `Tab takes the name · Enter to save
· Esc to cancel` in the head and `<name> · Tab takes the name · Enter to save · Esc to
cancel` in a row; otherwise it SHALL read as without this rule. A session with a title
SHALL open the field with the title selected and no suggestion.

#### Scenario: Tab takes the name in an empty field
- **WHEN** the human presses the pencil in the head of the session `lad-84`, which has
  no title, presses Tab, types ` (имя сессии)` and presses Enter
- **THEN** after Tab the field holds `lad-84` with the caret at its end and nothing was
  sent, and after Enter the title is `lad-84 (имя сессии)` and the focus is on the pencil

#### Scenario: A start of the name in a row
- **WHEN** the human chooses Rename… in the row of `lad-84` and types `la`
- **THEN** `d-84` shows grey after `la`, the hint reads `lad-84 · Tab takes the name ·
  Enter to save · Esc to cancel`, and → or Tab makes the text `lad-84`

#### Scenario: Tab with other text leaves the field
- **WHEN** the human types `zz` (or `LA`, or the whole `lad-84`) into the field of
  `lad-84` and presses Tab
- **THEN** no grey shows, the hint is the one without the suggestion, and the focus
  leaves the field, which saves it

#### Scenario: → inside the text moves the caret
- **WHEN** the field holds `la` with the caret between `l` and `a`, and the human
  presses →
- **THEN** no grey shows and the caret moves after `a`; the text stays `la`

#### Scenario: A session with a title
- **WHEN** the human opens the field of a session titled `lad-84 (имя сессии)`
- **THEN** the field holds the title selected, no grey shows, and Tab leaves the field
