## MODIFIED Requirements

### Requirement: lado model-server remove --with-models removes its models too

`lado model-server remove <name> --with-models` SHALL remove every configured model that
refers to the server, printing `Removed model "<model>".` for each, and after it
`<CLI title>'s default model is cleared.` for each agent CLI whose default was one of them,
then the server and its key file, in one transaction for the models, the defaults and the
server, and exit 0.

#### Scenario: A server with its models
- **WHEN** the models `coder-oc` and `sp` refer to `lms` and the human runs `lado
  model-server remove lms --with-models`
- **THEN** it prints `Removed model "coder-oc".`, `Removed model "sp".` and `Removed model
  server "lms".`, exits 0, and neither the models, the server nor its key folder is left

#### Scenario: A server with a default on it
- **WHEN** `coder-oc` on `lms` is OpenCode's default model and the human runs `lado
  model-server remove lms --with-models`
- **THEN** it prints `Removed model "coder-oc".`, `OpenCode's default model is cleared.` and
  `Removed model server "lms".`, and `lado model default` shows OpenCode with no default
