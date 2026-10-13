## ADDED Requirements

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
