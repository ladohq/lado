## MODIFIED Requirements

### Requirement: Where the UI shows a title it shows the name too

Where the UI shows a session's title,
it SHALL also show the name: in the row, first in its grey line (`lado-2 · 3 agents ·
1h 12m`); in the session's details, as `id <name>`; in the cards, after the title. The
head's line SHALL show the title alone. A session without a title SHALL look as it does
without this change, but for the `id <name>` the details show for every session.

#### Scenario: The list and the head
- **WHEN** the session `lado-2` has the title `Rename sessions (LAD-66)`
- **THEN** its row reads `Rename sessions (LAD-66)` over `lado-2 · …`, its head reads
  `Rename sessions (LAD-66)`, its details `id lado-2`, and the browser tab's title names
  `Rename sessions (LAD-66)`

### Requirement: The human sets the title in place, in the head and in the list

**Rename** in the session's details (capability session-head) SHALL turn the title in the
head into a text field holding the title (empty without one, the name as its placeholder). The list row's ⋯ menu SHALL hold
**Rename…** first, which turns the row's title into the same field.

#### Scenario: Rename in the head
- **WHEN** the human presses Rename in the details of `lado-2`, types `Review`, and
  presses Enter
- **THEN** the title is saved, the head and the row show `Review`, and the focus is on
  the head's title

### Requirement: The title field saves on Enter and on leaving, cancels on Esc

In the title field, Enter
and leaving it SHALL save through `PUT /api/sessions/{name}/title`, Esc SHALL cancel and
change nothing, and an empty field SHALL clear the title. After a
save or a cancel the focus SHALL go to the head's title when the field is in the head, and
back to the row's ⋯ when it is in a row.

#### Scenario: Rename from the row's menu and cancel
- **WHEN** the human chooses Rename… in the ⋯ of the row of `lado-2`, types `x`, and
  presses Esc
- **THEN** nothing is sent, the row shows what it showed before, and the focus is on ⋯

### Requirement: On a phone the title is renamed from the session's details

In the phone layout (capability phone-layout) the session's title SHALL open the session's
details, as on a computer, whose **Rename** SHALL turn
the sheet's title into the same field, the focus going back to Rename.

#### Scenario: Rename on a phone
- **WHEN** in the phone layout the human taps the session's title in the top bar, then
  Rename, types `Review` and presses Enter
- **THEN** the title is saved as `Review` and the focus is on Rename

### Requirement: Tab and → take the suggested name, else they do as in any field

While the suggestion shows, Tab without
modifiers and → without modifiers SHALL make the name the field's text with the caret at
its end, keep the focus in the field and send nothing. Otherwise Tab, Shift+Tab and →
SHALL do what they do in any field (Tab leaves the field, which saves it).

#### Scenario: Tab takes the name in an empty field
- **WHEN** the human presses Rename in the details of the session `lad-84`, which has
  no title, presses Tab, types ` (имя сессии)` and presses Enter
- **THEN** after Tab the field holds `lad-84` with the caret at its end and nothing was
  sent, and after Enter the title is `lad-84 (имя сессии)` and the focus is on the head's title

#### Scenario: Tab with other text leaves the field
- **WHEN** the human types `zz` (or `LA`, or the whole `lad-84`) into the field of
  `lad-84` and presses Tab
- **THEN** no grey shows, the hint is the one without the suggestion, and the focus
  leaves the field, which saves it

#### Scenario: → inside the text moves the caret
- **WHEN** the field holds `la` with the caret between `l` and `a`, and the human
  presses →
- **THEN** no grey shows and the caret moves after `a`; the text stays `la`
