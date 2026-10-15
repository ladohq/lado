## MODIFIED Requirements

### Requirement: A session has an optional title over its name

A session SHALL have an optional title, a label for the human, stored with the session
(`sessions.title`, schema 28), while its name SHALL stay its identifier: setting or
clearing a title SHALL NOT change the session's name, its address in the UI, its tmux
session, its agents' environment, its branches or its worktrees. A title SHALL be set
and cleared only through the core's one rule (`runtime.set_title`), for a session of any
status, running or stopped. The rule SHALL trim white space at both ends of the text; a
text that is then empty or equal to the session's name SHALL clear the title (store
none). It SHALL refuse, with its reason and nothing changed, a text that holds a hidden
character (the rule of capability visible-text: Unicode categories Cc, Zl, Zp and Cf but
U+200D ZERO WIDTH JOINER; a line break, a tab, a line separator, a bidi control, a
zero-width space among them), naming the first one (`a title is one line of visible
text: U+202E RIGHT-TO-LEFT OVERRIDE is not allowed`), or is longer than
`runtime.MAX_TITLE` (80) characters after the trim, and a session that does not exist.
Two sessions MAY have the same title. A stop and a resume SHALL keep the title;
`lado forget` SHALL delete it with the session, and a new session of that name SHALL
start without one.

#### Scenario: A title is set on a running session
- **WHEN** the human sets the title `Rename sessions (LAD-66)` on the running session
  `lado-2`
- **THEN** the session keeps the name `lado-2`, its page stays at `/sessions/lado-2`, its
  agents keep running, and its title is `Rename sessions (LAD-66)`

#### Scenario: Trimmed, empty and equal to the name
- **WHEN** the human sets `  Ревью kit-sdlc  `, then `   `, then `lado-2` on the session
  `lado-2`
- **THEN** its title is first `Ревью kit-sdlc`, then none, then none

#### Scenario: A refused title
- **WHEN** the human sets a title of 81 characters, or one with a line break
- **THEN** the core refuses it with the reason (`a title is at most 80 characters`,
  `a title is one line of visible text: U+000A is not allowed`) and the session's title
  is what it was

#### Scenario: Invisible and bidi characters are refused
- **WHEN** the human sets a title holding U+2028, U+202E or U+200B
- **THEN** the core refuses it naming that character (`a title is one line of visible
  text: U+2028 LINE SEPARATOR is not allowed`), the UI and `lado title` show that text,
  and the session's title is what it was

#### Scenario: An emoji joined by a zero width joiner is a title
- **WHEN** the human sets the title `Семья 👨‍👩‍👧` (its emoji joined by U+200D)
- **THEN** it is stored as given

#### Scenario: Stop, resume and forget
- **WHEN** a session with a title is stopped and resumed, then stopped and forgotten, and
  a new session of the same name is started
- **THEN** the title is there after the resume, and the new session has none
