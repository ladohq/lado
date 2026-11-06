## ADDED Requirements

### Requirement: A server's refusal for context reads in LADO's words

A turn of OpenCode or Kilo that ends on a server's refusal with `exceed_context_size_error` (LM Studio,
llama.cpp), which both CLIs report as `UnknownError`, SHALL end on the error `ContextOverflowError: the
model's context is too small for the agent's request`, followed by the server's own `request (<n> tokens)
exceeds the available context size (<m> tokens)` when its text holds that. The message's body SHALL hold
the error's whole text as the CLI gave it.

#### Scenario: LM Studio on a small context

- **WHEN** a turn ends on `UnknownError` whose message holds `exceed_context_size_error` and `request
  (21556 tokens) exceeds the available context size (16384 tokens)`
- **THEN** the chat's line reads `turn of supervisor ended on an error: ContextOverflowError: the
  model's context is too small for the agent's request; request (21556 tokens) exceeds the available
  context size (16384 tokens); it is idle`, and the body holds the raw JSON

#### Scenario: Another unknown error

- **WHEN** a turn ends on an `UnknownError` that does not hold `exceed_context_size_error`
- **THEN** its line and body stay as the CLI gave them

## MODIFIED Requirements

### Requirement: The warning says where to act

The warning about a context SHALL say where to change it: the setting of a server of a known type, and
the section of `docs/install.md`. In the launch window the name `docs/install.md` SHALL be a link to that
section on GitHub, opening in a new tab; `lado start` SHALL print the same text with no link. The folded
Advanced SHALL name each warning of the chosen model in a few words of its own.

#### Scenario: A server of a known type

- **WHEN** the model too small is on LM Studio
- **THEN** the warning names `lms load --context-length`

#### Scenario: The link of the launch window

- **WHEN** the launch window shows the warning
- **THEN** `docs/install.md ↗` in it links to `docs/install.md#what-to-expect-of-a-small-model` on
  GitHub, and a warning about a key over http has no link

#### Scenario: The folded Advanced

- **WHEN** the chosen model is too small and its key goes over plain http
- **THEN** the folded Advanced reads `⚠ key over http, context too small`; with the context alone,
  `⚠ context too small`

### Requirement: Overflows in a row stop the turn

The plugin SHALL stop a turn at the third context overflow with no successful model step of the turn
between them, and the turn SHALL end on that error, whatever the abort itself reports. The error's text
SHALL say the context is too small for the agent's request. A successful step of the turn or a new prompt
SHALL reset the count; the step of a compaction SHALL not, as its own small request succeeds in the loop
this stops.

#### Scenario: A long message of the server

- **WHEN** a turn is stopped and the server's message passes the limit of an error's line
- **THEN** the chat's line still says the context is too small and ends `; it is idle`, and the
  message's body holds the server's whole text

#### Scenario: The body does not repeat the line

- **WHEN** a turn is stopped with a message of the server
- **THEN** the message's body holds that text alone, without LADO's words

#### Scenario: A fixed request larger than the context

- **WHEN** every request of a turn is refused as a context overflow, and only the compaction's own
  requests succeed
- **THEN** the third overflow stops the turn, the agent becomes idle, and the chat shows the turn's error

#### Scenario: A compaction that helps

- **WHEN** an overflow is followed by a compaction and a successful step
- **THEN** the turn goes on and the count starts again
