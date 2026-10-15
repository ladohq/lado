## ADDED Requirements

### Requirement: One rule of hidden characters

LADO SHALL have one rule of which characters may not stand in a one-line text: a
character is hidden when its Unicode category is Cc (control characters, line breaks and
tabs among them), Zl (U+2028), Zp (U+2029) or Cf (format characters: bidi controls such
as U+202A–U+202E and U+2066–U+2069, zero-width characters such as U+200B and U+FEFF),
except U+200D ZERO WIDTH JOINER. Every check of a one-line text SHALL use this rule
(`lado.text`), and no other copy of it SHALL exist. A refusal SHALL name the first hidden
character as `U+XXXX` followed by its Unicode name when it has one.

#### Scenario: Hidden and visible characters
- **WHEN** the rule looks at a tab, `\n`, U+2028, U+2029, U+202E, U+2066, U+200B and U+FEFF
- **THEN** each is hidden
- **WHEN** it looks at `Ревью`, `代码`, `👨‍👩‍👧` (joined by U+200D) and a space
- **THEN** none is hidden

#### Scenario: A hidden character is named
- **WHEN** a refusal names U+202E, then a tab
- **THEN** it reads `U+202E RIGHT-TO-LEFT OVERRIDE`, then `U+0009`

### Requirement: Agents' one-line texts are refused with a hidden character

LADO SHALL refuse, with nothing written and the first hidden character named, an agent's
one-line text that holds a hidden character: `send_message`'s `summary`, `ask_human`'s
`question` and each of its choices, `flow_advance`'s `note_summary`, `flow_start`'s
`human_language`, and `write_artifact`'s `title` and `summary`. The error SHALL keep its
first words and, where it has one, its pointer to where the details go (`summary must be one line of visible text: U+2028 LINE
SEPARATOR is not allowed; put the details in body`).

#### Scenario: A summary with a line separator
- **WHEN** an agent calls `send_message` with the summary `done` U+2028 `tests pass`
- **THEN** the call fails with `summary must be one line of visible text: U+2028 LINE
  SEPARATOR is not allowed; put the details in body` and no message is queued

#### Scenario: A choice with a bidi override
- **WHEN** an agent calls `ask_human` with a choice holding U+202E
- **THEN** the call fails naming `U+202E RIGHT-TO-LEFT OVERRIDE` and no question is asked

#### Scenario: A note summary and an artifact title
- **WHEN** an agent calls `flow_advance` with a `note_summary` holding U+200B, or
  `write_artifact` with a title holding U+FEFF
- **THEN** the call fails naming the character, and the run and the store are as they were

### Requirement: The human's longer texts are cleaned for their one-line form

Where LADO takes one line from a longer text of the human, it SHALL NOT refuse the text
for a hidden character but SHALL clean the line: a hidden character of category Cc, Zl or
Zp SHALL become a space and one of category Cf SHALL be removed (U+200D stays). This
SHALL hold for the summary of the human's chat message and of an own answer to a
question, the next step's note made from a gate's comment, the note made from a
`lado flow-set` reason and the reason a loop limit's cancel stores, and the title of the
artifact of an uploaded file. Whenever the one-line form is not exactly the text (cleaned,
cut, or the text has more lines), the whole text as the human wrote it SHALL be kept in
the body (the message's or the note's), so nothing of it is lost; an uploaded file's
name is kept in its artifact's record as before.

#### Scenario: A chat message with a line separator and a bidi override
- **WHEN** the human writes `fix it` U+2028 `now` U+202E `please` to the supervisor
- **THEN** the message is sent, its summary is `fix it now please` with no U+2028 or
  U+202E in it, and its body is the text as written

#### Scenario: A flow-set reason
- **WHEN** the human runs `lado flow-set` with a reason holding U+200B
- **THEN** the run moves, the note reads `set by the human: <the reason without U+200B>`,
  and the note's body holds the reason as given

#### Scenario: An uploaded file's name
- **WHEN** the human uploads a file named `report` ESC `[31m` U+202E `.pdf`
- **THEN** the upload is stored, and its artifact's title has no ESC and no U+202E
