# session-model Specification

## Purpose
One model for a session's agents, chosen with `lado start --model` or the launch window's
Model field: kept with the session as a power table, checked against its CLI's own aliases
and list before the start, and passed to every agent of that CLI by the CLI's own way,
while an agent of another CLI runs its own default, loudly.

## Requirements

### Requirement: A session keeps its model as a power table

A session SHALL keep the model chosen for it as a power table: the rows `light`, `normal`
and `heavy`, each a CLI (a provider's name) and a model, kept in `lado.db` with the
session. A session for which no model is chosen SHALL have no table. A session's chosen
model SHALL fill all three rows with the same CLI and model, and every agent SHALL take
the `normal` row.

#### Scenario: A session started with a model
- **WHEN** the human runs `lado start --provider codex --model gpt-5.6-sol`
- **THEN** the session's table has the rows `light`, `normal` and `heavy`, each with the
  CLI `codex` and the model `gpt-5.6-sol`

#### Scenario: Sessions of an older LADO after the migration
- **WHEN** `lado.db` of schema 36 holds sessions and LADO migrates it to schema 37
- **THEN** each of those sessions has no table, and its agents start on their CLI's
  default model as before

### Requirement: lado start and the launch window choose the session's model

`lado start` SHALL take `--model <model>` for the session's provider's CLI, and the
launch window SHALL take the same in its Model field. A new session without a model SHALL
run its CLI's default. A resume without a model SHALL keep the session's table; a resume
with `--model ''` (or an emptied field) SHALL drop it; a resume that changes the provider
without a model SHALL drop a table whose CLI is another, and say so among the resume's
changes.

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

### Requirement: Each agent of the session's CLI starts on the session's model

Every agent whose provider is the CLI of the session's `normal` row SHALL be started on
its model through its CLI's own way, never through the user's global config: Claude Code
by `--model`, Codex by `model` in its own `CODEX_HOME`'s config.toml (top level and the
carried profile, over the carried value), OpenCode and Kilo by `model` in their config
content. The agent's record SHALL have that model with the source `session` from its
launch on.

#### Scenario: A Claude Code agent
- **WHEN** a session's table names `claude` and `opus` and its supervisor is launched
- **THEN** its command line has `--model opus`, and its model is `opus` with the source
  `session`

#### Scenario: A Codex agent with a carried profile
- **WHEN** the user's Codex config has `profile = "work"` with `[profiles.work] model =
  "gpt-5.5"`, and a session's table names `codex` and `gpt-5.6-sol`
- **THEN** the agent's config.toml has `model = "gpt-5.6-sol"` at the top level and in
  `[profiles.work]`, the user's file is unchanged, and the agent's model is `gpt-5.6-sol`
  with the source `session` while its carried effort keeps the source `cli-config`

#### Scenario: An OpenCode or Kilo agent
- **WHEN** a session's table names `kilo` and `anthropic/claude-sonnet-5-5`
- **THEN** the agent's `KILO_CONFIG_CONTENT` has `"model": "anthropic/claude-sonnet-5-5"`
  and its model is that name with the source `session`, also while Kilo has reported no
  model

#### Scenario: No model chosen
- **WHEN** a session has no table
- **THEN** no launch passes a model, and every agent's model has the source it had
  before this change (`cli`, or `cli-config` for a model carried from the user's Codex
  config)

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

### Requirement: A CLI's list of models is its own and local

LADO SHALL take a CLI's list of models only from the CLI's aliases, its own list command
or its local cache, and SHALL make no request to a model API for it: Claude Code has its
aliases and no list; Codex has `codex debug models --bundled` and the account's cached
catalogue, and no list when its carried model provider is not OpenAI's; OpenCode and Kilo
have `opencode models` and `kilo models`. A list command that fails or overruns its time
limit SHALL count as no list, with why.

#### Scenario: Codex on another model provider
- **WHEN** the user's Codex config carries `model_provider = "ollama"` and the human
  starts a Codex session with `--model qwen3-coder`
- **THEN** the session starts with a warning that Codex CLI gives no list of models for
  the model provider `ollama`, so LADO cannot check `qwen3-coder`

#### Scenario: A list command that fails
- **WHEN** `kilo models` exits with an error during the check
- **THEN** the session starts with a warning that names the failure and that LADO cannot
  check the model

### Requirement: An agent of another CLI runs its own default, loudly

An agent whose provider is not the CLI of the session's `normal` row (a worker spawned
with another provider) SHALL start on its CLI's default model; `spawn_worker` SHALL warn
that the session's model is for the other CLI, and the agent's model SHALL have the source
`cli` with the detail `the session's model <model> is for <CLI title>`, kept when its CLI
first names a model.

#### Scenario: A Claude worker in a Codex session
- **WHEN** a session's table names `codex` and `gpt-5.6-sol` and the supervisor spawns a
  worker `w1` with the provider `claude`
- **THEN** `spawn_worker`'s warnings include `w1 runs on Claude Code's default model: the
  session's model gpt-5.6-sol is for Codex CLI`, w1's command line has no `--model`, and
  its page reads Model `CLI default, the session's model gpt-5.6-sol is for Codex CLI`

#### Scenario: The worker's CLI names its model
- **WHEN** w1's SessionStart names `claude-opus-5-5`
- **THEN** its model is `claude-opus-5-5` with the source `cli` and the same detail

### Requirement: The launch window's Model field

The launch window's Advanced SHALL have a Model field before Switch off, in New session
and Resume: free text with the chosen provider's aliases and models as suggestions, and a
note under it with the check's result (empty: the CLI's default; ✓ in the list or an
alias; the warning; the refusal, with Start off). Folded with a model, its summary SHALL
read `Advanced: model <model>`. Changing the provider SHALL empty the field; in Resume it
SHALL start with the session's model.

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
