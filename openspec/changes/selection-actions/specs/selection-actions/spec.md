## ADDED Requirements

### Requirement: Selected text in a readable area shows the selection bar

When the human selects text whose start and end both lie in one readable area of the web
UI, the UI SHALL show the selection bar: two icon buttons with no visible label, Copy (two
sheets) and Quote in reply (a speech bubble with quote marks), each named by its
accessible name and the UI's tooltip ("Copy", "Quote in reply"). The readable areas SHALL
be: the messages of the session's chat and of an agent's page, the waiting card's
questions, gates and recommendations, the chat's closed gates and run events, the notes of
the Flows tab, the cards of Needs you, and the body of a Markdown or text artifact in the
artifact panel and in the Artifacts tab. A selection in an input field, the composer, an
agent's terminal, an HTML artifact, an image or the UI's chrome (rail, tabs, heads,
buttons) SHALL show no bar. With a pointer that can hover the bar SHALL stand above the
selection; on a touch screen (no hover) below it, clear of the system's own menu. Esc, a
click outside the bar, a scroll of the area that holds the selection, or a selection that
becomes empty SHALL hide it. Pressing a button of the bar SHALL keep the selection.

#### Scenario: A sentence in the supervisor's message
- **WHEN** the human selects "the bar hides on Esc" in the body of the supervisor's
  message in session lad-67's chat
- **THEN** a bar with the Copy and Quote in reply icons shows above the selection, and
  hovering the second shows the tooltip "Quote in reply"

#### Scenario: Esc
- **WHEN** the bar shows and the human presses Esc
- **THEN** the bar is gone

#### Scenario: The composer
- **WHEN** the human selects a word they typed in the composer
- **THEN** no selection bar shows

#### Scenario: An HTML artifact
- **WHEN** the human selects text inside the HTML artifact `task/lad-67/mockup-selection.html`
  in the artifact panel
- **THEN** no selection bar shows

#### Scenario: A phone
- **WHEN** the human selects text in a message on a touch screen 390 px wide
- **THEN** the bar shows below the selection

### Requirement: Copy on the selection bar copies the selection as Ctrl+C would

Copy SHALL put the selected text on the clipboard as the browser's own copy of that
selection would, and SHALL say "Copied" in place of the bar for 2 seconds; the selection
SHALL stay. When the browser refuses every way of copying, the bar SHALL say "Press ⌘C /
Ctrl+C to copy" and keep the selection.

#### Scenario: Copy a fragment
- **WHEN** the human selects "make lint" in an agent's message and clicks Copy
- **THEN** the clipboard holds "make lint", the bar's place says "Copied", and the text is
  still selected

### Requirement: Quote on the selection bar puts the selection into a composer as a Markdown quote

Quote SHALL append the selected text to a composer as a Markdown quote, each of its lines
prefixed with `> ` (an empty line as `>`), after a blank line when the composer already
holds text, then a new empty line with the cursor on it, and SHALL focus that composer.
The composer's recipient SHALL NOT change. The composer SHALL be the one on the page the
selection is on: the session's chat (to the supervisor), or an agent's page (to that
agent), also under an artifact panel opened over that page. On a page with no composer
(the Artifacts tab, the Flows tab, Needs you, or an artifact panel over one of them) Quote
SHALL open the session's chat with the quote in its composer. An expanded waiting card
SHALL fold so the composer shows.

#### Scenario: Quote in the chat
- **WHEN** the composer holds "Почему так?" and the human selects the two lines "A" and
  "B" of the supervisor's message and clicks Quote
- **THEN** the composer holds "Почему так?", an empty line, "> A", "> B" and an empty last
  line with the cursor on it, and its recipient is still the supervisor

#### Scenario: Quote on an agent's page
- **WHEN** the human selects a line of the developer's message on the developer's page and
  clicks Quote
- **THEN** that page's composer, to the developer, holds the quote

#### Scenario: Quote from the Flows tab
- **WHEN** the human selects a line of a note in the Flows tab of session lad-67 and clicks
  Quote
- **THEN** session lad-67's chat opens with the quote in its composer, to the supervisor

#### Scenario: Quote from an expanded card
- **WHEN** the waiting card is expanded and the human quotes a line of a question in it
- **THEN** the card folds and the composer under it holds the quote

### Requirement: A quote from an artifact names the artifact

A quote from a Markdown artifact SHALL start with the line `In <full name>:` followed by
the quote. A quote from a text or code artifact SHALL start with `In <full name> (lines
a–b):`, or `(line a)` for a single line, by the line numbers the viewer shows, followed by
the selected lines, without their numbers and cut at the selection's ends, as a fenced code
block instead of `> ` lines. When the record shown is not the artifact's latest, the first
line SHALL say so: `In <full name>, an earlier record:` (with its lines as above).

#### Scenario: A Markdown artifact
- **WHEN** the human quotes "AC-2. Quote puts the selection…" from `task/lad-67/design` in
  the panel over the chat
- **THEN** the chat's composer gets "In task/lad-67/design:" and the `> ` quote under it

#### Scenario: Lines of a code artifact
- **WHEN** the human selects lines 12 and 13 of a Python artifact `task/lad-67/notes.py`
  and clicks Quote
- **THEN** the composer gets "In task/lad-67/notes.py (lines 12–13):" and the two lines
  in a fenced code block, indentation kept, no line numbers

#### Scenario: An earlier record
- **WHEN** the human quotes from a record of `task/lad-67/design` older than its latest
- **THEN** the first line is "In task/lad-67/design, an earlier record:"

### Requirement: Code blocks and messages have copy buttons shown on hover

Each code block of a Markdown text the UI renders (messages, notes, cards, recommendations,
Markdown artifacts) SHALL have an icon button Copy code in its top right corner that copies
the block's code exactly. Each message of the session's chat and of an agent's page SHALL
have an icon button Copy message in its head that copies the message's Markdown text: for
the human's message its text, for an agent's message its summary (when the chat shows it)
and its body separated by a blank line. Both SHALL say "Copied" for 2 seconds after a copy.
With a pointer that can hover, both SHALL be hidden until the pointer is over the code
block or the message, or the keyboard's focus is on the button; on a touch screen they
SHALL always be shown.

#### Scenario: A command in a report
- **WHEN** the human moves the pointer over a code block `uv run pytest -m ui` in the
  developer's message and clicks Copy code
- **THEN** the clipboard holds exactly `uv run pytest -m ui` and the button says "Copied"

#### Scenario: Hidden without the pointer
- **WHEN** the pointer is not over a message
- **THEN** its head shows no Copy message button, and moving the pointer over the message
  shows it

#### Scenario: A message's text
- **WHEN** the human copies the analyst's message "Раунд 1" whose body is "1. Какие
  действия?"
- **THEN** the clipboard holds "Раунд 1", an empty line and "1. Какие действия?"

#### Scenario: A touch screen
- **WHEN** the chat is shown on a touch screen
- **THEN** every message shows Copy message and every code block Copy code without a hover
