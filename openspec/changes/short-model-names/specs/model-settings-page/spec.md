## MODIFIED Requirements

### Requirement: A default name of a server's model

A model ticked or added SHALL be named by its model as the server gives it, whole, cut to 64
characters. A name taken ignoring case SHALL get ` · <CLI title>` when the model holding it is of
another CLI and ` · <server>` when it is of the same CLI, then ` · <server> · <CLI title>`, and then
` (2)`, ` (3)` until free. No saved model SHALL be renamed by it.

#### Scenario: A server several CLIs suit
- **WHEN** `LM Studio дома` suits OpenCode and Kilo CLI, no model is saved, and the human ticks
  OpenCode for `qwen3-8b`
- **THEN** the model is named `qwen3-8b`

#### Scenario: A taken name
- **WHEN** `qwen3-8b` is saved as a name of an OpenCode model and the human ticks Kilo CLI under
  `qwen3-8b` on `lms`
- **THEN** the new model is named `qwen3-8b · Kilo CLI`, and the OpenCode one keeps `qwen3-8b`

#### Scenario: The same model on another server
- **WHEN** `qwen3-8b` is saved as a name of Kilo CLI's model on `lms` and the human ticks Kilo CLI
  under `qwen3-8b` on `Ollama`
- **THEN** the new model is named `qwen3-8b · Ollama`

#### Scenario: Both suffixes taken
- **WHEN** Kilo CLI's `qwen3-8b` on `lms` is saved, and the names `qwen3-8b · Ollama` and
  `qwen3-8b · Ollama · Kilo CLI` are taken, and the human ticks Kilo CLI under `qwen3-8b` on
  `Ollama`
- **THEN** the new model is named `qwen3-8b · Ollama · Kilo CLI (2)`

#### Scenario: An id with its vendor
- **WHEN** the human ticks OpenCode under `qwen/qwen3-coder` on a gateway
- **THEN** the model is named `qwen/qwen3-coder`

### Requirement: One picker of a model

The field Default model SHALL be a picker over the list the core computes for the CLI, read when
it opens, in this order, an empty group not shown: `<CLI>'s settings` with `no model set: the
agent CLI chooses`; YOUR MODELS, with their id and server; BUILT-IN, the CLI's list or its
aliases (`BUILT-IN · aliases`); `Other name…`, kept at the bottom, only when the CLI gives no
full list. Any later place that picks a model SHALL use this component. A model of YOUR MODELS
whose id is its name ignoring case SHALL show no id, in the list and in the field.

#### Scenario: OpenCode with a server
- **WHEN** the human opens the picker of OpenCode with two of its models saved
- **THEN** it shows OpenCode's settings, those two with `LM Studio дома`, then its built-in
  models, and no `Other name…`

#### Scenario: Codex CLI on OpenAI
- **WHEN** the human opens the picker of Codex CLI logged in to OpenAI
- **THEN** it shows the full list and no `Other name…`

#### Scenario: A model named by its id
- **WHEN** Kilo CLI's default is its model `qwen3.8-27b`, of the model `qwen3.8-27b` on
  `LM Studio`, and the human opens its picker in a window 768 px wide
- **THEN** the field shows `qwen3.8-27b` once, whole, and the badge `LM Studio`, and its row in
  the list shows no id under the name

### Requirement: Your models fits a narrow window

At 900 px and narrower Your models SHALL have no header row, and each model SHALL show its name
and × on one line, then `<model> · <server> · <agent CLI>` on the next, wrapped whole, the model
left out when it is the name ignoring case; × SHALL be 32 px, and 44 px on a phone.

#### Scenario: Tablet
- **WHEN** the human opens Model servers in a window 768 px wide with four models
- **THEN** each model takes two lines, no name or id is cut, and the page does not scroll sideways

#### Scenario: A model named by its id on a phone
- **WHEN** the human opens Model servers on a phone with Kilo CLI's default `qwen3.8-27b`, the
  model `qwen3.8-27b` on `LM Studio`
- **THEN** its second line reads `LM Studio · Kilo CLI · default`
