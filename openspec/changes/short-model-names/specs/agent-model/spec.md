## MODIFIED Requirements

### Requirement: The agent's page, the Team tooltip and lado ls show the model

The agent's page SHALL show the model's name in its head line after the role and the
provider ("CLI default model" when it has none) and the facts Model and Effort, each its
name and its source's words; an external model's fact SHALL read `<saved name> · <model> · server
<server>, <address> · <source's words>`, the model left out when it is the saved name ignoring
case, and its saved name stand in the head line. The Team chip's
tooltip SHALL add the model's name when it has one. `lado ls` SHALL show the model's name, or `-`,
after the agent's time.

#### Scenario: A Codex agent on its page
- **WHEN** the human opens the page of a Codex agent whose model is `gpt-5.6-sol` and
  effort `high`, both from `cli-config` with the detail `profile work`
- **THEN** its head line reads `developer · codex · gpt-5.6-sol`, Model reads
  `gpt-5.6-sol · your Codex config, profile work` and Effort reads
  `high · your Codex config, profile work`

#### Scenario: A CLI that has named nothing yet
- **WHEN** the human opens the page of a Kilo agent whose CLI has reported nothing
- **THEN** its head line ends with `CLI default model`, and Model and Effort read
  `CLI default`

#### Scenario: lado ls
- **WHEN** a session has a Claude supervisor whose model is `claude-opus-5-5` and a worker
  whose CLI has named no model, and the human runs `lado ls`
- **THEN** the supervisor's line has `claude-opus-5-5` and the worker's line has `-` after
  their times

#### Scenario: An external model on the page
- **WHEN** the human opens the page of an OpenCode agent on `Локальная Qwen`, chosen for the session
- **THEN** its head line ends with `Локальная Qwen`, and Model reads `Локальная Qwen · qwen3-8b ·
  server LM Studio дома, http://localhost:1234 · chosen for the session`

#### Scenario: An external model named by its id
- **WHEN** the human opens the page of a Kilo agent on `qwen3.8-27b`, the model `qwen3.8-27b` on
  `LM Studio` at `http://localhost:1234`, Kilo CLI's default model
- **THEN** Model reads `qwen3.8-27b · server LM Studio, http://localhost:1234 · Kilo CLI's default
  model`
