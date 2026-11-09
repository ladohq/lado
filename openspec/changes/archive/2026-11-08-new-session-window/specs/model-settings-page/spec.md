## MODIFIED Requirements

### Requirement: The UI calls Claude Code, Codex CLI, OpenCode and Kilo CLI agent CLIs

The UI SHALL name what runs an agent "agent CLI": Settings' section `Agent CLIs and environment`,
the system panel's `Agent CLIs`, and every line pointing to that section `Settings → Agent CLIs and
environment`; the New session window's field SHALL read `Agent`, its notes `agent CLI` or the CLI's
title. The section Models SHALL say `agent CLI`, or `CLI` where room is short. The section's anchor
and the commands' options (`--provider`, `--cli`) SHALL stay as they are.

#### Scenario: A worker refused for a CLI not logged in
- **WHEN** a session starts with Claude Code not logged in
- **THEN** the refusal says `log in in Settings → Agent CLIs and environment`, and that
  heading shows in Settings

#### Scenario: An old link
- **WHEN** the human opens `/settings#providers-and-environment`
- **THEN** the page scrolls to Agent CLIs and environment
