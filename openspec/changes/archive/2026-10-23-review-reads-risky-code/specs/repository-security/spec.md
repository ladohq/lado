## ADDED Requirements

### Requirement: The Claude reviewer can read the diff and nothing more

The Claude Code workflow MUST check out the full history (`fetch-depth: 0`), allow Claude
no tool of its own beyond `Bash(git diff:*)`, `Bash(git log:*)` and `Bash(gh pr diff:*)`,
keep the job's permissions at reading (with `id-token: write` for the Action's login), and
set no `prompt` input, so that a comment's request still drives the run and the progress
comment still reports that Claude finished.

#### Scenario: A writing command is allowed

- **WHEN** `claude_args` of `claude.yml` allows `Bash(git push:*)`
- **THEN** the unit tests fail and name the extra tool

#### Scenario: The review instruction is moved to the prompt input

- **WHEN** the Action's step in `claude.yml` has a `prompt` input
- **THEN** the unit tests fail

#### Scenario: A shallow checkout

- **WHEN** the checkout of `claude.yml` has `fetch-depth: 1`
- **THEN** the unit tests fail

### Requirement: The Claude reviewer reads risky code first and names what it read

The Claude Code workflow SHALL append a standing instruction for a review asked on a pull
request: read the diff `origin/main...HEAD`, read risky code in full first, the rest of
the code as far as the run allows, and end the answer with a list `Files read` and a list
`Files not read`. Risky code is security and secrets, deleting data, agents' environment
and the server's API. The comment's request may narrow or extend the instruction.

#### Scenario: The maintainer asks for a review of a large pull request

- **WHEN** an organisation member comments `@claude review` on a pull request of 40 files
- **THEN** Claude's progress comment ends with `Files read` and `Files not read`, and every
  risky file of the diff is under `Files read`

#### Scenario: The run ends before all risky code is read

- **WHEN** Claude's turns run out with a risky file of the diff not read in full
- **THEN** the answer says `Risky code not fully read` and lists that file first under
  `Files not read`

#### Scenario: The instruction loses its lists

- **WHEN** the appended instruction of `claude.yml` no longer names `Files read`,
  `Files not read` or `Risky code not fully read`
- **THEN** the unit tests fail
