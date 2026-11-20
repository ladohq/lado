## Purpose

The permission modes a session's agents run in: which values each agent CLI takes and how
LADO stores them.

## ADDED Requirements

### Requirement: A permission mode's other name starts its mode

`lado start --permission-mode` and the server's start and resume SHALL take a name a provider
gives as another name of one of its permission modes, and store and launch the session in the
mode it names; `lado start --help` SHALL list only the modes. Claude Code's `manual` SHALL be
another name of `default`.

#### Scenario: manual from the CLI
- **WHEN** `lado start <repo> --provider claude --permission-mode manual` runs
- **THEN** the session starts, its permission mode is stored as `default`, and its agents
  launch with `--permission-mode default`

#### Scenario: A stored manual resumes
- **WHEN** a Claude Code session stored with `manual` before this change is resumed
- **THEN** it resumes, and its permission mode is stored as `default`
