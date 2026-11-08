## ADDED Requirements

### Requirement: A CLI that cannot use the server says why

Under a server's model, an agent CLI that cannot use the server SHALL have its tick disabled,
on only when a model of it is saved (then with `as <name>`), and under its title `cannot use
this server: <why>`, the core's why: its provider refuses the server's type, the server has no
API of the CLI, or that API did not answer in time. One the server suits but not installed
here SHALL say `not installed`.

#### Scenario: Codex CLI on LM Studio
- **WHEN** LM Studio answers chat completions and the Responses API, all four agent CLIs are
  installed, and the human opens `qwen3-8b`
- **THEN** the list shows Claude Code, Codex CLI, Kilo CLI and OpenCode in that order, and
  Codex CLI's tick is off and disabled with `cannot use this server: its Responses API loses
  Codex CLI's MCP tools, so the agent could not talk to LADO`

#### Scenario: A model saved on a CLI that cannot use the server now
- **WHEN** `qwen3-8b` on `LM Studio` is saved for Kilo CLI as `Kilo qwen`, and Kilo CLI is no
  longer installed
- **THEN** Kilo CLI's tick is on and disabled, with `as Kilo qwen` and `not installed`

#### Scenario: A server without the Anthropic Messages API
- **WHEN** a server answers chat completions and the Responses API only
- **THEN** Claude Code's tick is off and disabled with `cannot use this server: it has no
  Anthropic Messages API`

#### Scenario: An API that did not answer in time
- **WHEN** the server's Anthropic Messages API did not answer either time
- **THEN** Claude Code's tick is off and disabled with `cannot use this server: its Anthropic
  Messages API did not answer in time`

#### Scenario: A CLI not installed
- **WHEN** the server suits Kilo CLI and Kilo CLI is not installed here
- **THEN** Kilo CLI's tick is off and disabled with `not installed`

#### Scenario: No installed CLI can use the server
- **WHEN** the server suits only Claude Code and Claude Code is not installed
- **THEN** the server says `No installed CLI can use this server.`, and a model still opens to
  the list of CLIs, none of them tickable, each with its reason

## MODIFIED Requirements

### Requirement: A server's model opens its CLIs

A click on a model of an open server, or Enter on it, SHALL open under its row a list of
every agent CLI LADO knows, in LADO's order, one under the other; Esc SHALL close it. An
installed agent CLI that can use the server SHALL have its tick and under its title `as
<name>` when ticked. The row SHALL say `in <CLI title>, …` for the agent CLIs it is configured
in. A server no installed agent CLI can use SHALL say `No installed CLI can use this server.`.

#### Scenario: qwen3-8b in OpenCode and Kilo CLI
- **WHEN** the human opens `LM Studio`, clicks `qwen3-8b` and ticks OpenCode and Kilo CLI
- **THEN** two models of `qwen3-8b` on `LM Studio` are saved, one of each agent CLI, and the
  row says `in OpenCode, Kilo CLI`

#### Scenario: More CLIs
- **WHEN** a server suits six installed agent CLIs
- **THEN** the list under the row shows six ticks one under the other, and the row is no
  wider
