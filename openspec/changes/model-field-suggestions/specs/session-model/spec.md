## MODIFIED Requirements

### Requirement: A model is checked against its CLI before the start

Before a session starts with a model given, or resumes with a model given or kept, LADO
SHALL check the model against its CLI: an alias of the CLI or a model in the CLI's own
list starts; a model not in the list is refused before anything starts, naming the
model, the CLI and the command that prints its list; when the CLI gives no list, the
session starts with a warning that LADO cannot check the model.

#### Scenario: A model in Codex's list
- **WHEN** the human starts a Codex session with `--model gpt-5.6-sol` and Codex's list
  has it
- **THEN** the session starts with no warning about the model

#### Scenario: A model not in the list
- **WHEN** the human starts a Codex session with `--model gpt-9`, which Codex's list lacks
- **THEN** `lado start` refuses before any agent starts with `gpt-9 is not in Codex CLI's
  list of models; codex debug models prints the list`, and no session is stored

#### Scenario: A Claude Code full name
- **WHEN** the human starts a Claude session with `--model claude-opus-5-5`
- **THEN** it starts, and `lado start` and the session's start warnings say that Claude
  Code gives no list of models beyond its aliases, so LADO cannot check `claude-opus-5-5`

#### Scenario: A Claude Code alias
- **WHEN** the human starts a Claude session with `--model sonnet`
- **THEN** it starts with no warning about the model

## ADDED Requirements

### Requirement: The Model field's suggestions are the window's own

The Model field SHALL be a combobox of the window's own, not the browser's: its arrow, ↓
or typing opens the suggestions, the provider's aliases (marked `alias`) and then its
models, filtered by what is typed; ↑↓ and Enter pick one, Esc closes them, and free text
stays.

#### Scenario: Picking a suggestion
- **WHEN** the human picks Claude Code, clicks Model's arrow and picks `opus`
- **THEN** the list closes, the field reads `opus` and its note reads `✓ an alias of
  Claude Code`

### Requirement: A model is taken without the spaces around it

A model given to `lado start --model`, to the API or in the launch window SHALL be taken
without the spaces around it; a model of only spaces SHALL count as `''`.

#### Scenario: Spaces around the model
- **WHEN** the human runs `lado start --provider codex --model ' gpt-5.6-sol '`
- **THEN** the model is checked and kept as `gpt-5.6-sol`

#### Scenario: Only spaces
- **WHEN** the human resumes a session that has a model with `--model '  '`
- **THEN** it has no table, as with `--model ''`

### Requirement: A resume refuses a kept model its CLI no longer lists

A resume that keeps the session's model SHALL check it as a model given, in
`lado start <session>`, the launch window's Resume and the resumes LADO makes by itself.
Its refusal SHALL also say that the session ran on it before and name `--model ''` for
the CLI's default and `--model <model>` for another; the session SHALL stay stopped with
its table, and a resume LADO makes by itself SHALL log the refusal.

#### Scenario: A kept model the list no longer has
- **WHEN** a stopped Codex session keeps the model `gpt-5.4-old`, Codex's list no longer
  has it, and the human runs `lado start <session>` with no `--model`
- **THEN** `lado start` refuses before any agent starts with `gpt-5.4-old is not in Codex
  CLI's list of models; codex debug models prints the list; the session ran on it before:
  resume it with --model '' for Codex CLI's default or --model <model> for another`, and
  the session stays stopped with its table

#### Scenario: LADO's own resume of a kept model the list lacks
- **WHEN** that session is to be resumed at the container's start
- **THEN** it stays stopped and the log says `could not resume session "<session>" at the
  container's start:` with the same refusal

### Requirement: The launch window's Resume says the way out of a kept model

In the launch window's Resume, a refusal of the session's kept model SHALL add `The
session ran on it before. Empty the field to resume on <CLI>'s default, or pick another
model.` and a button `Use <CLI>'s default` that empties the field.

#### Scenario: The way out of a kept model in Resume
- **WHEN** the human opens Resume for a Codex session that keeps `gpt-5.4-old`, which
  Codex's list no longer has
- **THEN** the note refuses it with the way out, Resume is off, and `Use Codex CLI's
  default` empties the field, after which Resume is on

### Requirement: The Model field looks like the window's other fields

The Model field SHALL have the height, frame, font and a chevron like the window's
Provider field and take a column of the window's grid as Provider does (the whole row on
a narrow window). Its note SHALL stand under it as far below as the notes of the
window's other fields, out of the reach of its focus ring.

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Permission mode is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Advanced is open
- **THEN** the Model field has Provider's height and width and a chevron at its right end

### Requirement: The server reads again a list of models it could not read

The server SHALL keep a CLI's list of models for the Model field's checks only once it
was read; a list it could not read SHALL be read again at the next check.

#### Scenario: A list that could not be read
- **WHEN** `kilo models` fails while the human types a model, and then answers
- **THEN** the next check after it answers shows Kilo's list, not the warning of the
  failed one
