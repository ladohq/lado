Task: LAD-39

## Why

ladohq/lado is public. A GitHub security audit of 2026-10-13 found five problems the
repository's own files must fix; the repository settings it found (rulesets on `main` and
`v*` tags, the `pypi` environment, secret scanning, push protection, private vulnerability
reporting, the organisation's 2FA) are applied already.

- `.github/workflows/claude.yml` runs on any `@claude` comment, review or issue, whoever
  wrote it, with the organisation's `CLAUDE_CODE_OAUTH_TOKEN`. The action checks the
  actor's write access itself, but the job, its checkout and the secret are already there
  by then.
- Actions are referenced by tag (`actions/checkout@v7`, `astral-sh/setup-uv@v10.2.0`,
  `anthropics/claude-code-action@v1`, ...), which their owners can move. `release.yml`
  runs with `id-token: write`, the right to publish to PyPI. The tests of `ci.yml`'s smoke
  job and of `windows-shell.yml` already require a pin, except for `actions/checkout`.
- No Dependabot: pinned actions and the Python and npm dependencies would age unseen.
- No `SECURITY.md`: a reporter does not know where to send a vulnerability.
- `docs/design/macos-gui-session.md` names two private IP addresses of the maintainers'
  network (`10.73.10.235`, `10.73.112.3`).

## What Changes

- `claude.yml`: the job's `if` also requires the author's `author_association` to be
  `OWNER`, `MEMBER` or `COLLABORATOR`, per event (the comment's, the review's, the
  issue's); its checkout moves from `v4` to the `v7` the other workflows use.
- Every `uses:` of every workflow in `.github/workflows/` is a full 40-character commit
  SHA followed by `# vX.Y.Z`, the release it is, `actions/checkout` included; the same
  major versions as today.
- `.github/dependabot.yml` (new): `github-actions` (`/`), `uv` (`/`) and `npm` (`/web`),
  weekly; per ecosystem one grouped pull request for minor and patch updates, majors
  each on their own; a cooldown of 7 days for version updates.
- `SECURITY.md` (new, English): report through GitHub's private vulnerability reporting
  (Security → Report a vulnerability), never in a public issue; only the latest final
  release is supported, fixes come as its next patch, release candidates are not
  supported; the maintainers aim to answer within 7 days, no fixed deadline for a fix.
- `docs/design/macos-gui-session.md`: both addresses become `<host>`.
- Tests: one test over all workflows enforces the pins (the `actions/checkout` exemption
  of the two existing pin tests goes), one the guard of `claude.yml`, one the Dependabot
  config.
- AGENTS.md (the CI paragraph) says that every action is pinned and Dependabot updates
  the pins.
- Version: no package code changes, no CHANGELOG line (nothing a user of LADO sees).

## Scope

- `.github/workflows/{ci,claude,release,windows-shell}.yml`, `.github/dependabot.yml`,
  `SECURITY.md`, `docs/design/macos-gui-session.md`, AGENTS.md.
- `tests/test_workflow_security.py` (new), `tests/test_ci_workflow.py`,
  `tests/test_windows_shell_workflow.py`.

## Out of scope

- The repository and organisation settings: applied already by the human. After the
  merge the human switches on "Require actions to be pinned to a full-length commit SHA"
  (last task); before the merge it would break CI on `main`.
- The private addresses in the git history: rewriting a public repository's history
  breaks every clone and fork, and the addresses are of a private network.
- `npm/` (the placeholder package): no dependencies, nothing to update.
- The release: `main` is frozen at `0.37.0rc1` (docs/release.md, The freeze). At the
  design's approval the human chose to merge this with the fixes that make `0.37.0rc2`
  (rc1 had problems), so the change ships in the next release candidate and the final is
  its code (`scripts/release_check.py`); no version or CHANGELOG change here.

## Acceptance criteria

- AC-1: `claude.yml` starts its job only for a `@claude` comment, review comment, review or
  issue whose author is `OWNER`, `MEMBER` or `COLLABORATOR`; the maintainer's
  `@claude review` (author_association `MEMBER`) still starts it.
- AC-2: Every `uses:` in `.github/workflows/*.yml` is `<owner>/<repo>@<40 hex>` followed by
  `# vX.Y.Z`, and the SHA is the commit of that tag in the action's repository.
- AC-3: `.github/dependabot.yml` has the three ecosystems, weekly, grouped minor and patch
  updates and a 7-day cooldown, and GitHub accepts it (Insights → Dependency graph →
  Dependabot shows no error after the merge).
- AC-4: `SECURITY.md` says where to report, which versions are supported and when to
  expect an answer, as listed above.
- AC-5: No private IP address is left in `docs/design/macos-gui-session.md`.
- AC-6: The new and changed tests pass, `make lint` and `make test` pass, and CI is green
  on the pull request.

## Impact

- CI and release workflows: the same actions at the same majors, pinned; a broken SHA
  shows on the pull request's own CI (ci.yml) or not until the next tag (release.yml)
  and the next Windows probe run, so the developer checks each SHA against its tag.
- No `src/` change: the reviewer's precision review; no live tests needed.

## Decisions for the record

- Scale tweak: a known shape, repository files only, no behaviour of LADO changes.
- `actions/checkout` is pinned too: the "pinned SHA" setting covers GitHub's own actions,
  and one rule for every action is simpler than an exemption.
- Each pin keeps today's major and takes its latest release of that major (`claude-code-
  action` its latest `v1.x`), resolved with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`
  (an annotated tag dereferenced to its commit); the comment gives the exact version so
  Dependabot can update SHA and comment together.
- The guard checks `author_association` in the workflow's `if`, not in a step: the job
  (and its secret) never starts for anyone else.
- One general pin test over all workflow files replaces two partial ones: a new workflow
  is covered without a new test.
- Dependabot's `uv` ecosystem, not `pip`: the project's lock file is `uv.lock`.
- No test for the IP addresses: a one-off text fix.
