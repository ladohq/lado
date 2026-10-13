## 1. Workflows

- [x] 1.1 `claude.yml`: each event's condition also requires its author's
  `author_association` in `OWNER`, `MEMBER`, `COLLABORATOR`
  (`github.event.comment`, `github.event.review`, `github.event.issue`); checkout `v4` →
  `v7`. Check: `tests/test_workflow_security.py` "Claude runs only for the repository's
  people" (every branch of the `if` names its event's `author_association` with the three
  values; no branch without it).
- [x] 1.2 Pin every `uses:` in `ci.yml`, `release.yml`, `claude.yml`, `windows-shell.yml`
  to its commit with `# vX.Y.Z` (today's major, its latest release; an annotated tag
  dereferenced). Check: `tests/test_workflow_security.py` "Workflows pin every action to a
  commit" over all `.github/workflows/*.yml`; drop the `actions/checkout` exemption from
  `tests/test_ci_workflow.py` and `tests/test_windows_shell_workflow.py` (or drop those two
  tests for the general one); each SHA checked by hand against `gh api
  repos/<owner>/<repo>/commits/<tag> --jq .sha`, listed in the build report.

## 2. Repository files

- [x] 2.1 `.github/dependabot.yml`: version 2; `github-actions` `/`, `uv` `/`, `npm`
  `/web`; `schedule.interval: weekly`; a group of `minor` and `patch` per ecosystem;
  `cooldown.default-days: 7`. Check: `tests/test_workflow_security.py` "Dependabot keeps
  actions and dependencies current" (yaml parsed: the three entries, weekly, grouped,
  cooldown).
- [x] 2.2 `SECURITY.md` (English): private vulnerability reporting link
  (`https://github.com/ladohq/lado/security/advisories/new`), no public issues; supported:
  the latest final release only, fixes in its next patch, release candidates not
  supported; an answer within 7 days aimed at, no fixed deadline for a fix. Check: read.
- [x] 2.3 `docs/design/macos-gui-session.md`: `10.73.10.235` and `10.73.112.3` → `<host>`.
  Check: `grep -rnE '\b10\.[0-9]+\.[0-9]+\.[0-9]+\b' docs` finds nothing.
- [x] 2.4 AGENTS.md, the CI paragraph: every action pinned to a commit with its version,
  Dependabot (`.github/dependabot.yml`) updates them and the dependencies weekly.

## 3. Regression

- [ ] 3.1 `openspec validate public-repo-hardening --strict`, `make lint`, `make test`;
  CI green on the pull request.

## 4. After the merge (the human, by hand)

- [ ] 4.1 Merge with the fixes of 0.37.0rc2 (the human's choice at the design's approval;
  main is frozen at 0.37.0rc1). Then switch on "Require actions to be pinned to a full-length commit SHA" (organisation or
  repository Actions settings) and check Insights → Dependency graph → Dependabot.
