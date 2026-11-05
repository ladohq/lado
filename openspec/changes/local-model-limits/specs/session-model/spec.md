## ADDED Requirements

### Requirement: OpenCode on a model server does not wait for npm

An OpenCode agent that starts on a model of a server SHALL have `npm_config_fetch_retries=0` and
`npm_config_fetch_timeout=5000` in its environment, unless the user's environment sets them. An agent
on any other model, and a Kilo agent, SHALL not have them from LADO.

#### Scenario: A first start with no way out

- **WHEN** an OpenCode agent starts on a server's model on a fresh `HOME` and outside traffic is refused
- **THEN** its first request reaches the server within 15 s

#### Scenario: A built-in model

- **WHEN** an OpenCode agent starts on a built-in model
- **THEN** LADO sets neither variable

#### Scenario: The user's own value

- **WHEN** the user's environment sets `npm_config_fetch_retries`
- **THEN** the agent keeps that value

### Requirement: An agent's new state folder keeps the user's TUI settings

A new state folder of an OpenCode or Kilo agent SHALL take a copy of the user's `kv.json`, when there is
one, once; the user's file SHALL only be read. A file that cannot be read SHALL give a start warning, and
the agent SHALL start without it.

#### Scenario: A new agent

- **WHEN** the user's state folder holds `kv.json` and the agent's folder is new
- **THEN** the agent's folder holds a copy, and the user's file is unchanged

#### Scenario: A resume

- **WHEN** the agent's folder already holds `kv.json`
- **THEN** it stays as it is
