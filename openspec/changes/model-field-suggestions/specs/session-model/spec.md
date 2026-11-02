## MODIFIED Requirements

### Requirement: lado start and the launch window choose the session's model

`lado start` SHALL take `--model <model>` for the session's provider's CLI, and the
launch window SHALL take the same in its Model field. A model SHALL be taken without the
spaces around it, in `lado start` and the API as in the window; a model of only spaces
SHALL count as `''`. A new session without a model SHALL run its CLI's default. A resume
without a model SHALL keep the session's table; a resume with `--model ''` (or an emptied
field) SHALL drop it; a resume that changes the provider without a model SHALL drop a
table whose CLI is another, and say so among the resume's changes.

#### Scenario: A resume keeps the model
- **WHEN** a stopped session has the model `gpt-5.6-sol` for `codex` and the human runs
  `lado start <session>` with no `--model`
- **THEN** its agents start on `gpt-5.6-sol` again

#### Scenario: A resume goes back to the CLI's default
- **WHEN** the human resumes that session with `--model ''`
- **THEN** it has no table, and `lado start` prints `changed model: codex gpt-5.6-sol -> CLI default`

#### Scenario: A resume changes the provider
- **WHEN** the human resumes that session with `--provider claude` and no `--model`
- **THEN** it has no table, its agents start on Claude Code's default model, and the
  changes printed include `model: codex gpt-5.6-sol -> CLI default`

#### Scenario: Spaces around the model
- **WHEN** the human runs `lado start --provider codex --model ' gpt-5.6-sol '`
- **THEN** the model is checked and kept as `gpt-5.6-sol`

#### Scenario: Only spaces
- **WHEN** the human resumes a session that has a model with `--model '  '`
- **THEN** it has no table, as with `--model ''`

### Requirement: A model is checked against its CLI before the start

Before a session starts with a model given, or resumes with a model given or kept, LADO
SHALL check the model against its CLI: an alias of the CLI or a model in the CLI's own
list starts; a model not in the list is refused before anything starts, naming the
model, the CLI and the command that prints its list; when the CLI gives no list, the
session starts with a warning that LADO cannot check the model. A refusal of the model a
resume keeps SHALL also say that the session ran on it before and name `--model ''` for
the CLI's default and `--model <model>` for another. The same check SHALL hold for
`lado start <session>`, the launch window's Resume and the resumes LADO makes by itself,
which leave the session stopped and log the refusal.

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

### Requirement: The launch window's Model field

The launch window's Advanced SHALL have a Model field before Switch off, in New session
and Resume: free text in a combobox of the window's own with the chosen provider's
aliases (marked `alias`) and then its models as suggestions, filtered by what is typed
and opened by its arrow, ↓ or typing; the field SHALL have the height, frame, font and
chevron of the window's Provider field and take a column of the window's grid as Provider
does (the whole row on a narrow window). A note SHALL stand under the field, as far below
it as the notes of the window's other fields and out of the reach of its focus ring, with
the check's result (empty: the CLI's default; ✓ in the list or an alias; the warning; the
refusal, with Start off). In Resume a refusal of the session's kept model SHALL add `The
session ran on it before. Empty the field to resume on <CLI>'s default, or pick another
model.` and a button `Use <CLI>'s default` that empties the field. A list of models the
server could not read SHALL be read again at the next check, not kept. Folded with a
model, its summary SHALL read `Advanced: model <model>`. Changing the provider SHALL
empty the field; in Resume it SHALL start with the session's model.

#### Scenario: A model the list lacks in the window
- **WHEN** the human picks Codex, opens Advanced and types `gpt-9`
- **THEN** the note under Model reads `gpt-9 is not in Codex CLI's list of models; codex
  debug models prints the list` and Start session is off

#### Scenario: The folded summary
- **WHEN** the human types `gpt-5.6-sol` and folds Advanced
- **THEN** its summary reads `Advanced: model gpt-5.6-sol`

#### Scenario: Another provider
- **WHEN** the human has typed `gpt-5.6-sol` for Codex and picks Claude Code
- **THEN** the Model field is empty and its suggestions are Claude Code's aliases

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Permission mode is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Advanced is open
- **THEN** the Model field has Provider's height and width and a chevron at its right end

#### Scenario: Picking a suggestion
- **WHEN** the human picks Claude Code, clicks Model's arrow and picks `opus`
- **THEN** the list closes, the field reads `opus` and its note reads `✓ an alias of
  Claude Code`

#### Scenario: The way out of a kept model in Resume
- **WHEN** the human opens Resume for a Codex session that keeps `gpt-5.4-old`, which
  Codex's list no longer has
- **THEN** the note refuses it with the way out, Resume is off, and `Use Codex CLI's
  default` empties the field, after which Resume is on

#### Scenario: A list that could not be read
- **WHEN** `kilo models` fails while the human types a model, and then answers
- **THEN** the next check after it answers shows Kilo's list, not the warning of the
  failed one
