## ADDED Requirements

### Requirement: An agent starts on the session's model, else its CLI's default

An agent SHALL start on the session's model when the table has a row of its CLI; else on its
CLI's default model from Settings → Models; else as before any model existed. This SHALL be read
at each launch: a default changed later SHALL reach the next resume and the next worker, not a
running agent. The agent's model SHALL have the source `session`, `default` or `cli`.

#### Scenario: The CLI's default with no choice
- **WHEN** OpenCode's default is `Локальная Qwen` and the human runs `lado start ~/shop --provider
  opencode`
- **THEN** the session has no table, its supervisor starts on `Локальная Qwen` and its model has
  the source `default`

#### Scenario: The session's model over the default
- **WHEN** that default is set and the human starts with `--model opencode/big-pickle`
- **THEN** the supervisor starts on `opencode/big-pickle` with the source `session`

#### Scenario: A default changed before a resume
- **WHEN** a stopped session has no table, ran on `Локальная Qwen` as the default, and the human
  sets OpenCode's default to `Рабочая Qwen` and resumes it
- **THEN** the supervisor starts on `Рабочая Qwen` with the source `default`, and `lado start` and
  the session's start warnings say `changed model: Локальная Qwen -> Рабочая Qwen`

#### Scenario: A worker of another CLI with its default
- **WHEN** a session's table names `opencode` and Kilo CLI's default is `Qwen в Kilo`, and the
  supervisor spawns a worker with the provider `kilo`
- **THEN** the worker starts on `Qwen в Kilo` with the source `default`

### Requirement: The session's model is where an agent starts, not a limit

For an agent of a CLI whose models on a server sit beside its own, LADO SHALL put every external
model ticked for that CLI into the agent's config, whatever the session chose: a built-in model,
an external model, or nothing. The agent's own CLI's built-in models SHALL stay. An agent of a CLI
holding one model per process SHALL get none of this.

#### Scenario: A built-in model chosen
- **WHEN** a session on OpenCode has `opencode/big-pickle` chosen, and `Локальная Qwen` and `Рабочая
  Qwen` on two servers are ticked for OpenCode
- **THEN** the agent's config has a provider for each server with its models, and its model is
  `opencode/big-pickle`

#### Scenario: An external model chosen
- **WHEN** the session has `Локальная Qwen` chosen
- **THEN** the agent's config has the same two providers, and it starts on `Локальная Qwen`

#### Scenario: Nothing chosen
- **WHEN** the session has no table and OpenCode has no default
- **THEN** the agent's config has the same two providers, no `model`, no `--model`, and the CLI
  chooses

#### Scenario: A Claude Code agent
- **WHEN** an external model is ticked for Claude Code and a Claude session starts on its settings
- **THEN** the agent's launch has nothing of the server

### Requirement: Each server is a provider marked as LADO's

For each server the agent's config SHALL have one OpenAI-compatible provider with the id
`lado-<server id>` and the label `LADO · <server name>`, each model under its saved name. A server
renamed SHALL keep its provider's id; the user's own providers SHALL be left alone. A name or a
model that holds `{env:` or `{file:` SHALL be left out of the config with a warning.

#### Scenario: In the CLI's /model
- **WHEN** the human opens `/model` in an OpenCode or Kilo agent
- **THEN** the group `LADO · LM Studio дома` lists `Локальная Qwen` beside the built-in models

#### Scenario: A server renamed
- **WHEN** the human renames the server and resumes the session
- **THEN** the provider's id is the same and its label has the new name

#### Scenario: A model id that would expand
- **WHEN** a ticked model's id holds `{file:`
- **THEN** it is not in the config, and the start's warnings name it

### Requirement: The server of the start model is checked before the start

Before a session starts and at each resume, for a model given, kept or default, LADO SHALL check
the server of the model the agent starts on, by the probe that saving a model uses, within its
timeout: a server that does not answer, asks for or refuses the key, or lacks the model SHALL be
refused before anything starts. A server with no list SHALL start with the warning that LADO cannot
check the model. A silent server of another ticked model SHALL stop nothing.

#### Scenario: The server does not answer
- **WHEN** the human runs `lado start ~/shop --provider opencode --model "Локальная Qwen"` and `LM
  Studio дома` does not answer
- **THEN** it refuses with `http://localhost:1234 does not answer (<why>); LADO cannot check
  qwen3-8b`, and no session is stored

#### Scenario: The model is gone from the server
- **WHEN** the server answers and its list lacks `qwen3-8b`
- **THEN** it refuses with `qwen3-8b is not in LM Studio дома's list of models; lado model-server
  probe http://localhost:1234 prints the list`

#### Scenario: A silent server of another model
- **WHEN** the session starts on `Локальная Qwen`, and the server of `Рабочая Qwen`, also ticked,
  does not answer
- **THEN** the session starts, and that server is not asked

#### Scenario: LADO's own resume
- **WHEN** a session on that model is to be resumed at the container's start and its server does
  not answer
- **THEN** it stays stopped and the log says `could not resume session "<session>" at the
  container's start:` with the refusal

#### Scenario: Nothing to check
- **WHEN** a session starts on its CLI's settings
- **THEN** no server is asked

### Requirement: A CLI that runs on no server is refused

A start model on a server for a CLI that does not run on one yet SHALL be refused before any
request, naming the CLIs that do and that the server suits; a spawned worker SHALL be refused the
same way.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `Шлюз`, which also suits OpenCode, and the human
  starts a Claude session
- **THEN** it refuses with `Шлюз Opus is on the model server Шлюз; Claude Code does not run on a
  model server yet, OpenCode does`, adding the default's way out, and `Шлюз` is not asked

#### Scenario: A worker of that CLI
- **WHEN** the supervisor of an OpenCode session spawns a worker with the provider `claude`
- **THEN** `spawn_worker` fails with the same line and no worker exists

### Requirement: A key over plain http is warned about before the start

For each server in the agent's config with a key whose address `model-servers` warns about, the
start's warnings SHALL hold that warning, and the session SHALL start. The launch window SHALL show
it only for the chosen model's server.

#### Scenario: A gateway over http
- **WHEN** a ticked model's server is `http://llm.example.com` with a key, and the session starts on
  another model
- **THEN** `lado start` and the session's start warnings say the key goes to `llm.example.com` over
  plain http, and it starts

### Requirement: A table that cannot be read breaks no session

A session's table with an unknown key SHALL read as if without it. Text that is no JSON, a top
level or row that is no object, and a row without a string `cli` or `model` SHALL read as an
unreadable table: listing sessions and agents SHALL work, and its resume SHALL be refused with
`--model ''` and `--model <model>` as the way out.

#### Scenario: A row with an unknown key
- **WHEN** a row has a key this LADO does not know
- **THEN** the session reads with the row's `cli` and `model`

#### Scenario: A broken table
- **WHEN** `sessions.power` of one stopped session holds text that is no JSON
- **THEN** `lado ls` and the UI list every session, and `lado start <session>` refuses with `the
  session's model cannot be read; resume it with --model '' for <CLI>'s settings or --model <model>
  for another`

### Requirement: A worker takes nothing of its spawner's launch

When agents take the starting process's environment (`LADO_AGENT_ENV=inherit`), a worker SHALL NOT
inherit the variables LADO or the provider set for the launch of the agent that spawned it.

#### Scenario: A worker of another CLI
- **WHEN** an OpenCode supervisor with a server's key in its environment spawns a Claude worker in
  that mode
- **THEN** the worker's environment has neither the key nor `OPENCODE_CONFIG_CONTENT`

### Requirement: The window's Model field takes Settings in a new tab

The Model list's foot SHALL read `The default comes from Settings → Models.`, its link opening
Settings → Models in a new tab; what was entered in the window SHALL stay, and the window SHALL
read the list again when it gets the focus back.

#### Scenario: Back from Settings
- **WHEN** the human has typed a first message, opens Settings → Models from the foot, ticks a model
  and comes back
- **THEN** the message is there and the list has the new model

### Requirement: A refused default names its way out

A refusal of a CLI's default model at a start or resume SHALL add `it is <CLI>'s default model:
start with --model '' for its settings, or change it with lado model default <cli>`.

#### Scenario: A default that cannot start
- **WHEN** OpenCode's default is `Локальная Qwen`, its server does not answer, and the human starts
  with no `--model`
- **THEN** it refuses, adding `it is OpenCode's default model: start with --model '' for its
  settings, or change it with lado model default opencode`

### Requirement: The Model field's notes

Under the default the note SHALL read `<CLI>'s default model, from Settings → Models.`; under
another pick `For this session only. <CLI>'s default model is <name>.`, no such line without a
default; under `<CLI>'s settings` with a default `For this session only: the agent CLI chooses, not
<name>.` A pick lost to another agent CLI SHALL leave `<name> belongs to <CLI>, so the model is back
to <new CLI>'s default.`

#### Scenario: Another pick
- **WHEN** OpenCode's default is `Локальная Qwen` and the human picks `Рабочая Qwen`
- **THEN** the note reads `For this session only. OpenCode's default model is Локальная Qwen.`

#### Scenario: The agent CLI's settings past a default
- **WHEN** the human picks `OpenCode's settings`
- **THEN** the note reads `For this session only: the agent CLI chooses, not Локальная Qwen.`, and
  starting sends `''`

### Requirement: A refused model in the window

A model in the field SHALL be checked as the start checks it, Start staying on while the check runs.
A refusal SHALL open Advanced, turn Start off and stand under the field with `Use <CLI>'s settings`,
and with `Check again` where a new try can help. A start refused after a good check SHALL show `Not
started: <short reason>. See Model above.` above the buttons and do the same to the field.

#### Scenario: Refused at Start
- **WHEN** the server answered the check and stops answering before the human presses Start
- **THEN** above the buttons reads `Not started: LM Studio дома does not answer. See Model above.`,
  Advanced is open, the focus is on Model, and Start session is off

### Requirement: Advanced's summary names the model

Folded with a model, Advanced's summary SHALL read `Advanced: model <name> on <server>`, or
`Advanced: model <model>` for a built-in one, adding `⚠ key over http` or `! <short reason>`.

#### Scenario: A folded refusal
- **WHEN** the field holds a model of a silent server and the human folds Advanced
- **THEN** its summary ends with `! not answering`

## MODIFIED Requirements

### Requirement: A session keeps its model as a power table

A session SHALL keep the model chosen for it as a power table in `lado.db`: the rows `light`,
`normal` and `heavy`, each a CLI (a provider's name) and a model reference: built-in, external (the
entry's id with a copy of its name and model), or the CLI's own settings (an empty model). A session
with nothing chosen SHALL have no table. A chosen model SHALL fill all three rows, and every agent
SHALL take the `normal` row.

#### Scenario: A session started with a model
- **WHEN** the human runs `lado start --provider codex --model gpt-5.6-sol`
- **THEN** the session's table has the rows `light`, `normal` and `heavy`, each with the
  CLI `codex` and the model `gpt-5.6-sol`

#### Scenario: Sessions of an older LADO after the migration
- **WHEN** `lado.db` of schema 36 holds sessions and LADO migrates it to schema 37
- **THEN** each of those sessions has no table, and its agents start on their CLI's
  default model as before

#### Scenario: A session on an external model
- **WHEN** the human runs `lado start ~/shop --provider opencode --model "Локальная Qwen"`
- **THEN** the rows name that entry by its id

#### Scenario: A model renamed after the start
- **WHEN** the human renames `Локальная Qwen` to `Qwen дома` and resumes the session
- **THEN** its agents start on the same model and server, and the session's model reads `Qwen дома`

#### Scenario: A table of a built-in model from before
- **WHEN** a stored row holds only `cli` and `model`
- **THEN** it reads as that built-in model, with no migration

### Requirement: lado start and the launch window choose the session's model

`lado start` SHALL take `--model <name>`, read as `lado model default` reads a name for the
session's CLI, and the launch window the same in its Model field; the model SHALL NOT change the
session's CLI. `--model ''` SHALL choose the CLI's own settings, past any default, kept at a resume.
A new session without a model SHALL have no table. A resume without one SHALL keep the table, unless
the provider changes to another CLI: it is then dropped, and the resume's changes say so.

#### Scenario: A resume keeps the model
- **WHEN** a stopped session has the model `gpt-5.6-sol` for `codex` and the human runs
  `lado start <session>` with no `--model`
- **THEN** its agents start on `gpt-5.6-sol` again

#### Scenario: A resume goes back to the CLI's default
- **WHEN** the human resumes that session with `--model ''`
- **THEN** its rows hold the CLI's settings, its agents pass no model, and `lado start` prints
  `changed model: codex gpt-5.6-sol -> Codex CLI's settings`

#### Scenario: A resume changes the provider
- **WHEN** the human resumes that session with `--provider claude` and no `--model`
- **THEN** it has no table, its agents start on Claude Code's default model, and the
  changes printed include `model: codex gpt-5.6-sol -> CLI default`, or the default's name when
  Claude Code has one set

#### Scenario: Past a default
- **WHEN** OpenCode's default is `Локальная Qwen` and the human runs `lado start ~/shop --provider
  opencode --model ''`
- **THEN** the session's agents pass no model, their source is `cli`, and its server is not asked;
  a resume with no `--model` does the same

#### Scenario: Another CLI's external model
- **WHEN** the human runs `lado start ~/shop --provider claude --model "Локальная Qwen"`, which is
  OpenCode's
- **THEN** it refuses with `"Локальная Qwen" is a model of OpenCode, not of Claude Code`, and no
  session is stored

### Requirement: Each agent of the session's CLI starts on the session's model

Every agent of the CLI of the session's `normal` row SHALL start on its model through its CLI's
own way, never through the user's global config: Claude Code by `--model`, Codex by `model` in its
own `CODEX_HOME`'s config.toml (top level and carried profile), OpenCode and Kilo by `model` in
their config content and by `--model`. The agent's record SHALL have that model with the source
`session` from its launch on; a CLI's default SHALL go the same way with the source `default`.

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
- **THEN** the agent's `KILO_CONFIG_CONTENT` has `"model": "anthropic/claude-sonnet-5-5"`, its
  command line has `--model anthropic/claude-sonnet-5-5`, and its model is that name with the source
  `session`, also while Kilo has reported no model

#### Scenario: No model chosen
- **WHEN** a session has no table and its CLI no default
- **THEN** no launch passes a model, and every agent's model has the source it had
  before this change (`cli`, or `cli-config` for a model carried from the user's Codex
  config)

#### Scenario: Kilo remembers another pick
- **WHEN** the human's last `/model` pick in Kilo is another model and a session on Kilo has a model
- **THEN** the agent starts on the session's model

### Requirement: A model is checked against its CLI before the start

Before a session starts with a model given, or resumes with a model given or kept, or starts on a
built-in default, LADO SHALL check a built-in model against its CLI: an alias of the CLI or a model
in the CLI's own list starts; a model not in the list is refused before anything starts, naming
the model, the CLI and the command that prints its list; when the CLI gives no list, the
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

### Requirement: An agent of another CLI runs its own default, loudly

An agent whose provider is not the CLI of the session's `normal` row (a worker spawned
with another provider) SHALL start on its CLI's default model from Settings → Models, else as
its CLI chooses; with no such default `spawn_worker` SHALL warn that the session's model is for the
other CLI, and the agent's model SHALL have the source `cli` with the detail `the session's model
<model> is for <CLI title>`, kept when its CLI first names a model.

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

The launch window's Advanced SHALL have a Model field before Switch off, in New session and Resume:
the model picker of the chosen agent CLI, optional, asking for no address or key, holding that CLI's
default when the window opens (in Resume the session's model, else the default). The value left as
it came SHALL send no model, another pick its name, `<CLI>'s settings` with a default `''`. Another
agent CLI SHALL set the field to that CLI's default.

#### Scenario: A model the list lacks in the window
- **WHEN** the human picks Codex, opens Advanced and gives `gpt-9` as an other name, or a saved
  built-in default Codex's list lost is in the field
- **THEN** the note under Model reads `gpt-9 is not in Codex CLI's list of models` with `Use
  Codex CLI's settings`, and Start session is off

#### Scenario: The folded summary
- **WHEN** the human picks `Локальная Qwen` on `LM Studio дома` and folds Advanced
- **THEN** its summary reads `Advanced: model Локальная Qwen on LM Studio дома`

#### Scenario: Another provider
- **WHEN** the human has picked `Локальная Qwen` for OpenCode and picks Claude Code with no default
- **THEN** the Model field reads `Claude Code's settings`, its list is Claude Code's, and the note
  reads `Локальная Qwen belongs to OpenCode, so the model is back to Claude Code's default.`

#### Scenario: The default chosen in advance
- **WHEN** OpenCode's default is `Локальная Qwen` and the human picks OpenCode
- **THEN** the field holds it, marked `default`, the note reads `OpenCode's default model, from
  Settings → Models.`, and starting sends no model

#### Scenario: A server that does not answer
- **WHEN** the field holds `Локальная Qwen` and its server does not answer
- **THEN** Advanced is open, the note reads `LM Studio дома does not answer (<why>); qwen3-8b is on
  it. Start the server or pick another model.` with `Check again` and `Use OpenCode's settings`,
  and Start session is off

#### Scenario: A CLI that runs on no server
- **WHEN** the field holds Claude Code's `Шлюз Opus`
- **THEN** the note has the refusal and `Use Claude Code's settings`, without `Check again`

#### Scenario: The window says agent CLI
- **WHEN** the human opens the window
- **THEN** the field above Permission mode reads `Agent CLI`, and its notes say `agent CLI`, never
  `provider`

#### Scenario: A key over http
- **WHEN** the chosen model's server gets its key over plain http to a public address
- **THEN** the note warns with `⚠ The key of <server> goes unencrypted (http) to an address outside
  your machine and network.`, and Start session stays on

### Requirement: A model is taken without the spaces around it

A model given to `lado start --model`, to the API or in the launch window SHALL be taken
without the spaces around it; a model of only spaces SHALL count as `''`.

#### Scenario: Spaces around the model
- **WHEN** the human runs `lado start --provider codex --model ' gpt-5.6-sol '`
- **THEN** the model is checked and kept as `gpt-5.6-sol`

#### Scenario: Only spaces
- **WHEN** the human resumes a session that has a model with `--model '  '`
- **THEN** it is on the CLI's settings, as with `--model ''`

### Requirement: A resume refuses a kept model its CLI no longer lists

A resume that keeps the session's model SHALL check it as a model given, in
`lado start <session>`, the launch window's Resume and the resumes LADO makes by itself; an
external model no longer saved SHALL be refused as well. Its refusal SHALL also say that the
session ran on it before and name `--model ''` for the CLI's settings and `--model <model>` for
another; the session SHALL stay stopped with its table, and a resume LADO makes by itself SHALL log
the refusal.

#### Scenario: A kept model the list no longer has
- **WHEN** a stopped Codex session keeps the model `gpt-5.4-old`, Codex's list no longer
  has it, and the human runs `lado start <session>` with no `--model`
- **THEN** `lado start` refuses before any agent starts with `gpt-5.4-old is not in Codex
  CLI's list of models; codex debug models prints the list; the session ran on it before:
  resume it with --model '' for Codex CLI's settings or --model <model> for another`, and
  the session stays stopped with its table

#### Scenario: LADO's own resume of a kept model the list lacks
- **WHEN** that session is to be resumed at the container's start
- **THEN** it stays stopped and the log says `could not resume session "<session>" at the
  container's start:` with the same refusal

#### Scenario: A kept model no longer saved
- **WHEN** a stopped session keeps `Рабочая Qwen`, which was removed, and the human resumes it
- **THEN** `lado start` refuses with `the session ran on the model Рабочая Qwen, which is no longer
  saved; resume it with --model '' for OpenCode's settings or --model <model> for another`

### Requirement: The launch window's Resume says the way out of a kept model

In the launch window's Resume, a refusal of the session's kept model SHALL add `The
session ran on it before. Pick another model, or resume on <CLI>'s settings.` and a button `Use
<CLI>'s settings`; an external model no longer saved SHALL read `The session ran on the model
<name>, which is no longer in Settings → Models. Pick a model or use <CLI>'s settings.` with `not in
Settings` in the field.

#### Scenario: The way out of a kept model in Resume
- **WHEN** the human opens Resume for a Codex session that keeps `gpt-5.4-old`, which
  Codex's list no longer has
- **THEN** the note refuses it with the way out, Resume is off, and `Use Codex CLI's
  settings` puts the field on them, after which Resume is on

### Requirement: The Model field looks like the window's other fields

The Model field SHALL have the height, frame, font and a chevron like the window's Agent CLI field
and take the whole row of Advanced, so a model's name, id and server fit. Its note SHALL stand under
it as far below as the notes of the window's other fields, out of the reach of its focus ring.

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Permission mode is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Advanced is open
- **THEN** the Model field has Agent CLI's height, the whole row's width and a chevron at its right
  end

## REMOVED Requirements

### Requirement: The Model field's suggestions are the window's own

**Reason**: The field is the model picker now; free text with suggestions goes with it.
**Migration**: `Other name…` keeps a name outside the list for a CLI with no full list.
