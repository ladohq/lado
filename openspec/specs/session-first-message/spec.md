# session-first-message Specification

## Purpose
The human's first message to a session's supervisor, given when the session starts or is
resumed: `lado start --prompt` / `--prompt-file` and the New session window's First
message row, queued by the core as a message from the human that the supervisor gets with
its first hook.

## Requirements

### Requirement: A session starts with the human's first message

`runtime.start_session` SHALL take the human's first message (`prompt`) for a new session
and for a resume alike. Given, it SHALL be queued for the session's supervisor before the
supervisor starts, as a message from `human` whose summary is the fixed line
`runtime.FIRST_MESSAGE` (`the human's first message`) and whose body is the whole text,
stripped. Without `prompt` the start SHALL queue nothing
new.

#### Scenario: A new session with a first message
- **WHEN** a new session starts with `prompt` "Take LAD-19\nAsk me about the scope first"
- **THEN** its supervisor's queue holds one message from `human`, summary
  `the human's first message`, body that text, and the supervisor reads it with
  `read_messages` after its first hook

#### Scenario: No first message
- **WHEN** a session starts without `prompt`
- **THEN** its supervisor's queue is what it is today

#### Scenario: A start that fails
- **WHEN** a start with `prompt` fails after the session was taken (e.g. its window does
  not start)
- **THEN** the message is dropped with the rest of the supervisor's queue, as the start's
  other queued messages are

### Requirement: The first message comes after LADO's own messages of the start

The human's first message SHALL come after every message LADO queues for that start (a resume's
`session resumed: …` and the supervisor's own steps; a supervisor-started session's
brief), and SHALL be handed over as any queued message: with the supervisor's first hook,
through the same confirmation and retries.

#### Scenario: A resumed session with a first message
- **WHEN** a stopped session with one open run is resumed with `prompt` "Continue the
  review"
- **THEN** the supervisor gets `session resumed: 1 open run` from `lado` first and the
  human's message after it

### Requirement: The first message is checked before anything changes

The core SHALL refuse a `prompt` that is empty after stripping (`the first message is
empty`) or longer than `runtime.MAX_MESSAGE` characters (`the first message is <n>
characters, the limit is <limit>`), before the session is stored, resumed or launched and
before any clone. The check SHALL be one function the CLI calls before a clone and
`start_session` calls itself.

#### Scenario: An empty first message
- **WHEN** `start_session` gets `prompt` "  \n "
- **THEN** it refuses with `the first message is empty`, and no session is stored and no
  tmux session made

#### Scenario: A first message over the limit
- **WHEN** `prompt` has 8001 characters
- **THEN** the start is refused with `the first message is 8001 characters, the limit is
  8000` and nothing changes

### Requirement: The human's text never goes on an agent's command line

The human's first message SHALL reach the supervisor only through its queue: the line a
CLI is given at launch (Kilo and OpenCode take their queue's lines on `--prompt`) SHALL
carry the fixed summary `runtime.FIRST_MESSAGE` and never the text, and the text SHALL be
read with `read_messages` as any body.

#### Scenario: Kilo or OpenCode launched with a first message
- **WHEN** a session of provider `opencode` starts with `prompt` "Take LAD-19"
- **THEN** the supervisor's argv holds `[from human] the human's first message (#<id>, 1
  line: call read_messages)` and not "Take LAD-19"

#### Scenario: Codex with a first message
- **WHEN** a session of provider `codex` starts with `prompt`
- **THEN** its supervisor's first input is the human's message line and LADO queues no
  `runtime.FIRST_INPUT`

### Requirement: lado start takes a first message

`lado start` SHALL take `--prompt TEXT` or `--prompt-file FILE`, not both (argparse's exit
2); `--prompt-file -` SHALL read the text from stdin, a file SHALL be read as UTF-8. With a message queued, `lado start`
SHALL print `first message: queued for the supervisor` after its `Started session` or
`Resumed session` line. It SHALL work for a folder, a git URL and a resume alike.

#### Scenario: Text on the command line
- **WHEN** `lado start ~/app --prompt "Take LAD-19" --no-attach` runs
- **THEN** the session starts, the output has `first message: queued for the supervisor`,
  and the supervisor gets the message

#### Scenario: Text from stdin
- **WHEN** `printf 'Line one\nLine two\n' | lado start ~/app --prompt-file - --no-attach`
  runs
- **THEN** the supervisor's message body is `Line one\nLine two`

#### Scenario: Both options
- **WHEN** `lado start ~/app --prompt a --prompt-file b` runs
- **THEN** it exits 2 with argparse's "not allowed with" error and nothing starts

#### Scenario: A resume with a first message
- **WHEN** `lado start ~/app --prompt "Continue"` runs for a stopped session of that
  folder
- **THEN** the session is resumed and the supervisor gets the message after LADO's
  `session resumed` message

### Requirement: lado start checks the first message before anything starts

`lado start` SHALL read and check the first message's text before anything else starts: before a git URL's clone and
before `start_session`; a file it cannot read SHALL be `lado: cannot read the first message
from <FILE>: <reason>` with exit 1 and nothing changed.

#### Scenario: A file that cannot be read
- **WHEN** `lado start ~/app --prompt-file missing.md` runs
- **THEN** it exits 1 with `lado: cannot read the first message from missing.md: …` and
  nothing starts

#### Scenario: A git URL with a bad first message
- **WHEN** `lado start file:///srv/app.git --prompt ""` runs
- **THEN** it is refused with `the first message is empty` and no clone starts

### Requirement: The New session window takes a first message

The New session window SHALL show, in its New and its Resume mode, for a folder and a
clone alike, a row **First message to the supervisor (optional)** above Advanced, folded
each time the window opens; opened, a text field (`aria-label` "First message") with the
note "sent to the supervisor as your message once it starts; its answer comes in the
chat". Folded with text in it, the row SHALL read `First message to the supervisor:
<the text's first line>`, cut to one line.

#### Scenario: Folded by default
- **WHEN** the human opens the New session window
- **THEN** the First message row is folded and the window shows no text field for it

#### Scenario: Folded with text
- **WHEN** the human types two lines and folds the row
- **THEN** the row reads `First message to the supervisor: <first line>`

### Requirement: The New session window sends the first message as prompt

The New session window SHALL send the First message field's text as
`prompt` of `POST /api/sessions` or `POST /api/sessions/{name}/resume`, and no `prompt`
when the field holds only white space. A text longer than `Limits.max_message` SHALL show
`<n> characters, the limit is <limit>` under the field and keep the start button off.

#### Scenario: A first message sent
- **WHEN** the human opens the row, types "Take LAD-19" and presses Start session
- **THEN** the request carries `prompt: "Take LAD-19"`, and the session's Activity shows
  the message as the human's

#### Scenario: Over the limit
- **WHEN** the field holds 8001 characters
- **THEN** the note says `8001 characters, the limit is 8000` and Start session is off

#### Scenario: Resume with a first message
- **WHEN** the human resumes a stopped session from the Resume window with a first message
- **THEN** the resume request carries `prompt`, and the resumed supervisor gets it after
  LADO's `session resumed` message

#### Scenario: Clone and start with a first message
- **WHEN** the human clones from a URL with a first message
- **THEN** the start after the clone carries the same `prompt`
