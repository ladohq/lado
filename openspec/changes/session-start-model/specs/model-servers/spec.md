## ADDED Requirements

### Requirement: A server's key reaches an agent only through its environment

The key of every server with a model ticked for an agent's CLI SHALL reach that agent only as a
variable of its launch, named in its config as `{env:…}`. It SHALL NOT be in a config file, config
content, `lado.db`, a log, a warning, a refusal or an API answer, nor in the environment of an
agent of a CLI with no model on that server.

#### Scenario: The key in the environment only
- **WHEN** an OpenCode agent starts with a model ticked on a server with a key
- **THEN** its config content has `{env:LADO_MODEL_KEY_<ID>}`, that variable has the key, and no file
  under `LADO_HOME` but the server's key file has it

#### Scenario: A worker of another CLI
- **WHEN** that session spawns a Claude worker
- **THEN** the worker's environment has no such variable

### Requirement: A key that cannot reach an agent stops only its own server

A key file that cannot be read, or a key holding `"`, `\` or a control character, which the CLIs
put into their config's text as it is, SHALL refuse the start of an agent on that server, and leave that server's models out
of another agent's config with a warning; neither SHALL show the key.

#### Scenario: Another server's key cannot be read
- **WHEN** the key file of a server other than the start model's cannot be read
- **THEN** the agent starts without that server's models, and the warnings name the server

#### Scenario: A key that would break the config
- **WHEN** the key of the start model's server holds `"`
- **THEN** the start is refused naming the server, with no part of the key, and no server is asked

### Requirement: lado doctor promises only what the probe saw

For a server its probe found, `lado doctor` SHALL say that it lists its models: the probe sends no
chat, so it cannot say that the server works.

#### Scenario: A server that fails every chat
- **WHEN** a server lists its models and answers each chat with an error
- **THEN** the line `Model servers` says `<server> lists its models (<type>)`

### Requirement: lado doctor names a default that cannot start

With a default model set, `lado doctor` SHALL print one line `Default models`: `OK`, or `WARN`
naming each default whose server's probe failed, with why, whose server's list lacks it, or whose
built-in name its CLI no longer lists, or that it cannot check as the agents' environment cannot be
read. It SHALL ask each server no more than the line `Model servers` did, and its exit status SHALL
be as without the line. With no default it SHALL print no line.

#### Scenario: A default on a silent server
- **WHEN** OpenCode's default is `Локальная Qwen` and `LM Studio дома` does not answer
- **THEN** `lado doctor` prints `[WARN] Default models:` naming OpenCode, the model and that the
  server does not answer

#### Scenario: A built-in default the list lost
- **WHEN** Codex CLI's default is `gpt-5.4-old` and its list no longer has it
- **THEN** the line names Codex CLI and that its list lacks the model
