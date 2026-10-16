# agent-instructions Specification

## Purpose
The instructions every agent loads at the start of a session: AGENTS.md (CLAUDE.md is
`@AGENTS.md`) stays a short map of the project, and the details live in the documents it
links (docs/design/agents.md, docs/design/modules.md, docs/testing.md, docs/cli.md).

## Requirements

### Requirement: AGENTS.md is a bounded map

AGENTS.md SHALL be at most 200 lines, and every relative Markdown link in it SHALL name a
file or folder of the repository; a unit test checks both.

#### Scenario: AGENTS.md grows past the limit

- **WHEN** AGENTS.md has 201 lines
- **THEN** the unit test fails, naming the count and the limit

#### Scenario: A link names a moved or deleted file

- **WHEN** AGENTS.md links `docs/design/agents.md` and that file is not in the repository
- **THEN** the unit test fails, naming the link

#### Scenario: The map as it is

- **WHEN** AGENTS.md is at most 200 lines and each of its relative links names a path of
  the repository
- **THEN** the unit test passes
