# repository-security Specification

## Purpose
What the public repository's own files do for its security: workflows that run only
pinned actions and start the Claude Code job only for the repository's people, Dependabot
keeping the pins and the dependencies current, and a security policy that tells a
reporter where to send a vulnerability (`.github/`, `SECURITY.md`).

## Requirements

### Requirement: Workflows pin every action to a commit

Every `uses:` of a workflow in `.github/workflows/` MUST name the action by a full
40-character commit SHA followed by a comment `# vX.Y.Z` with the release that commit is,
GitHub's own actions included.

#### Scenario: An action referenced by tag

- **WHEN** a workflow has `uses: actions/checkout@v7`
- **THEN** the unit tests fail and name that line

#### Scenario: A pinned action without its version

- **WHEN** a workflow has `uses: astral-sh/setup-uv@<40 hex>` with no `# vX.Y.Z` after it
- **THEN** the unit tests fail and name that line

### Requirement: Claude runs only for the repository's people

The Claude Code workflow SHALL start its job only for a `@claude` comment, review comment,
review or issue whose author's `author_association` is `OWNER`, `MEMBER` or
`COLLABORATOR`.

#### Scenario: A stranger mentions Claude

- **WHEN** a user with no rights in the repository comments `@claude` on a pull request
- **THEN** the workflow's job is skipped and the secret is not used

#### Scenario: The maintainer asks for a review

- **WHEN** an organisation member comments `@claude review` on a pull request
- **THEN** the job runs as before

### Requirement: Dependabot keeps actions and dependencies current

The repository SHALL have `.github/dependabot.yml` updating `github-actions` and `uv` at
the root and `npm` in `web/` every week, minor and patch updates grouped into one pull
request per ecosystem, with a cooldown of 7 days for version updates.

#### Scenario: The config lacks an ecosystem

- **WHEN** `.github/dependabot.yml` has no `npm` entry for `/web`
- **THEN** the unit tests fail

### Requirement: A security policy says how to report

The repository SHALL have a `SECURITY.md` that sends vulnerability reports to GitHub's
private vulnerability reporting, names the latest final release as the only supported one
and says when a reporter can expect an answer.

#### Scenario: A reporter looks for the way

- **WHEN** someone opens the repository's Security tab
- **THEN** it shows the policy with the private reporting link and the supported versions

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
