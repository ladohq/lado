## MODIFIED Requirements

### Requirement: A server's key reaches an agent only through its environment

The key of every server with a model ticked for an agent's CLI SHALL reach that agent only as a
variable of its launch, named in its config as `{env:…}`, or for Claude Code in its own settings
as `apiKeyHelper: printenv <variable>`. It SHALL NOT be in a config file, config
content, `lado.db`, a log, a warning, a refusal or an API answer, nor in the environment of an
agent of a CLI with no model on that server.

#### Scenario: The key in the environment only
- **WHEN** an OpenCode agent starts with a model ticked on a server with a key
- **THEN** its config content has `{env:LADO_MODEL_KEY_<ID>}`, that variable has the key, and no file
  under `LADO_HOME` but the server's key file has it

#### Scenario: A worker of another CLI
- **WHEN** that session spawns a Claude worker
- **THEN** the worker's environment has no such variable

#### Scenario: A Claude agent's key
- **WHEN** a Claude agent starts on a model of a server with a key
- **THEN** its settings have `apiKeyHelper` `printenv LADO_MODEL_KEY_<ID>`, that variable has the key,
  and no file under `LADO_HOME` but the server's key file has it
