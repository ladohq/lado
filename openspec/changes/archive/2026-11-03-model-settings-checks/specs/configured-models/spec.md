## MODIFIED Requirements

### Requirement: lado model remove removes a model

`lado model remove <name> [<name> …]` SHALL find every name given (ignoring case, a name
given twice counted once) before it removes any; when one is no model's, it SHALL be
refused with `no model "<name>" is saved; lado model list names them` (`no models "<name>",
"<name>" are saved; …` for several), remove nothing and exit 1. Otherwise it SHALL remove
each model in the order given, print `Removed model "<name>".` for each and exit 0. Their
servers SHALL stay.

#### Scenario: Removing the last model of a server
- **WHEN** `Локальная Qwen` is the only model on `LM Studio дома` and the human removes it
- **THEN** it is gone from `lado model list`, `LM Studio дома` stays, and `lado
  model-server remove "LM Studio дома"` then succeeds

#### Scenario: Several models at once
- **WHEN** `coder-codex`, `coder-oc` and `sp` are saved and the human runs `lado model
  remove "coder-codex" "coder-oc" "sp"`
- **THEN** it prints `Removed model "coder-codex".`, `Removed model "coder-oc".` and
  `Removed model "sp".`, and exits 0

#### Scenario: One name of several not saved
- **WHEN** `coder-codex` is saved, `nowhere` is not, and the human runs `lado model remove
  coder-codex nowhere`
- **THEN** it exits 1 with `no model "nowhere" is saved; lado model list names them`, and
  `coder-codex` stays

## ADDED Requirements

### Requirement: An embeddings model is no agent's model

A model on a server whose `GET /api/v0/models` types it `embeddings` SHALL be refused by
`lado model add` with `<model> is an embeddings model on <server>; an agent needs a chat
model: lado model-server probe <address> lists the models` and exit 1, after the check that
the server suits the CLI and before the check against its list; nothing SHALL be saved. A
model the server gives no type for SHALL be checked as before.

#### Scenario: The embeddings model of LM Studio
- **WHEN** `lms` is LM Studio at `http://10.73.10.235:1234` and types
  `text-embedding-nomic-embed-text-v1.5` `embeddings`, and the human runs `lado model add
  emb --cli opencode --model text-embedding-nomic-embed-text-v1.5 --server lms`
- **THEN** it exits 1 with `text-embedding-nomic-embed-text-v1.5 is an embeddings model on
  lms; an agent needs a chat model: lado model-server probe http://10.73.10.235:1234 lists
  the models`, and nothing is saved

#### Scenario: A chat model of the same server
- **WHEN** the same server types `qwen3-8b` `llm` and the human adds `--model qwen3-8b`
  on it
- **THEN** the model is saved

#### Scenario: A server without types
- **WHEN** the server is Ollama and lists `nomic-embed-text`
- **THEN** `lado model add … --model nomic-embed-text --server <it>` is checked against the
  list as before and saved
