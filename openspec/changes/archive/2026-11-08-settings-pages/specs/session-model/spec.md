## MODIFIED Requirements

### Requirement: An agent of another CLI runs its own default, loudly

An agent whose provider is not the CLI of the session's `normal` row (a worker spawned
with another provider and no `model`) SHALL start on its CLI's default model from Settings → Agent CLIs, else as
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
  Settings → Agent CLIs.`, and starting sends no model

#### Scenario: A server that does not answer
- **WHEN** the field holds `Локальная Qwen` and its server does not answer
- **THEN** Advanced is open, the note reads `LM Studio дома does not answer (<why>); qwen3-8b is on
  it. Start the server or pick another model.` with `Check again` and `Use OpenCode's settings`,
  and Start session is off

#### Scenario: A CLI that runs on no server
- **WHEN** the field holds Codex CLI's `Локальная GPT`, on LM Studio
- **THEN** the note has the refusal and `Use Codex CLI's settings`, without `Check again`

#### Scenario: The window says agent CLI
- **WHEN** the human opens the window
- **THEN** the field above Permission mode reads `Agent CLI`, and its notes say `agent CLI`, never
  `provider`

#### Scenario: A key over http
- **WHEN** the chosen model's server gets its key over plain http to a public address
- **THEN** the note warns with `⚠ The key of <server> goes unencrypted (http) to an address outside
  your machine and network.`, and Start session stays on

### Requirement: The launch window's Resume says the way out of a kept model

In the launch window's Resume, a refusal of the session's kept model SHALL add `The
session ran on it before. Pick another model, or resume on <CLI>'s settings.` and a button `Use
<CLI>'s settings`; an external model no longer saved SHALL read `The session ran on the model
<name>, which is no longer in Settings → Model servers. Pick a model or use <CLI>'s settings.` with `not in
Settings` in the field, and in its list a row of its own above the groups with the same mark.

#### Scenario: The way out of a kept model in Resume
- **WHEN** the human opens Resume for a Codex session that keeps `gpt-5.4-old`, which
  Codex's list no longer has
- **THEN** the note refuses it with the way out, Resume is off, and `Use Codex CLI's
  settings` puts the field on them, after which Resume is on

### Requirement: An agent starts on the session's model, else its CLI's default

A worker spawned with a `model` SHALL start on it. Any other agent SHALL start on the session's
model when the table has a row of its CLI; else on its CLI's default model from Settings → Agent CLIs;
else as before any model existed. This SHALL be read at each launch: a default changed later SHALL
reach the next resume and the next worker, not a running agent. The agent's model SHALL have the
source `supervisor`, `session`, `default` or `cli`.

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

#### Scenario: A worker's model over the session's
- **WHEN** a session's table names `opencode/big-pickle` and the supervisor spawns a worker with
  `model="Локальная Qwen"`
- **THEN** the worker starts on `Локальная Qwen` with the source `supervisor`

### Requirement: The window's Model field takes Settings in a new tab

The Model list's foot SHALL read `The default comes from Settings → Agent CLIs.`, its link opening `/settings/agent-clis` in a new tab; what was entered in the window SHALL stay, and the window SHALL
read the list again when it gets the focus back, an open list too.

#### Scenario: Back from Settings
- **WHEN** the human has typed a first message, opens Settings → Agent CLIs from the foot, picks OpenCode's default model and comes back
- **THEN** the message is there and the field shows the new default

### Requirement: The Model field's notes

Under the default the note SHALL read `<CLI>'s default model, from Settings → Agent CLIs.`; under
another pick `For this session only. <CLI>'s default model is <name>.`, no such line without a
default; under `<CLI>'s settings` with a default `For this session only: the agent CLI chooses, not
<name>.`

#### Scenario: Another pick
- **WHEN** OpenCode's default is `Локальная Qwen` and the human picks `Рабочая Qwen`
- **THEN** the note reads `For this session only. OpenCode's default model is Локальная Qwen.`

#### Scenario: The agent CLI's settings past a default
- **WHEN** the human picks `OpenCode's settings`
- **THEN** the note reads `For this session only: the agent CLI chooses, not Локальная Qwen.`, and
  starting sends `''`
