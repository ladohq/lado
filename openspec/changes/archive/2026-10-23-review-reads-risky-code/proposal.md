Task: LAD-133

## Why

The external review (Claude Code Action, `.github/workflows/claude.yml`, on a `@claude`
comment) reads a pull request's diff selectively. In epic LAD-116 the second external
round of several steps (S2, S2b, S3, S4, S5b) went mostly into reading what the first one
had skipped, and the reviewer built its coverage table from a guess at the comment's text.

Cause, in the workflow's setup:

- `actions/checkout` with `fetch-depth: 1`: the checkout has no `origin/main` history, so
  `git diff origin/main...HEAD` cannot be computed.
- No `claude_args`: the Action's comment mode allows Claude only reading tools and git's
  writing commands; `git diff`, `git log` and `gh pr diff` are refused.
- No standing instruction: on a large pull request (40+ files) one run takes what it finds
  first within its turns and says nothing about the rest.

The human decided on 2026-10-23 that a full review of every file is not needed: texts
(specs, docs, tests, OpenAPI) stay read locally (decision #949 of epic LAD-116). What is
needed is that risky code is read for certain, and that the answer shows it.

Options weighed:

- A (taken): `fetch-depth: 0`, and `claude_args` with `--allowedTools` for the three
  reading commands and `--append-system-prompt` with the standing instruction. The
  Action stays in its comment mode, so the request in the comment still drives the run
  and the progress comment still ends with "Claude finished", which the project's
  **External reviewer** settings wait for. Cost: one workflow edit and a unit test.
- B: the Action's `prompt` input with the instruction. Rejected: with `prompt` set, the
  pinned Action (`src/modes/detector.ts`) switches a comment event to its automation
  mode: no progress comment, so a round can no longer be seen to finish, and the
  comment's own request is no longer the task.
- C: a review instruction file in the repository (e.g. `CLAUDE.md` rules) that the
  Action's Claude reads. Rejected: `CLAUDE.md` is every agent's file (it includes
  AGENTS.md, the project's map); a review rule there reaches LADO's own agents too, and
  it still would not open the three commands or the history.

## What Changes

- `.github/workflows/claude.yml`: checkout with `fetch-depth: 0`; `claude_args` allows
  `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(gh pr diff:*)` and appends the standing
  review instruction (design.md, D2). The Action's SHA, the job's `permissions`,
  `additional_permissions`, the people guard and the secret stay as they are.
- `tests/test_workflow_security.py`: the setup above is checked.
- `.lado/sdlc.md`, **External reviewer**: a line on coverage: it is taken from the lists
  of files at the end of Claude's comment.
- `docs/testing.md`: the paragraph on `claude.yml` says what the reviewer may run and
  what its answer ends with.
- BACKLOG.md: the Action's comment mode lets Claude edit files and commit (found on the
  way, out of scope here).
- Living spec `repository-security`: a new requirement.

## Scope

`.github/workflows/claude.yml`, `tests/test_workflow_security.py`, `.lado/sdlc.md`,
`docs/testing.md`, BACKLOG.md, this change.

## Out of scope

- The Action's version (pinned SHA): the task keeps it.
- The workflow's `permissions` and the secret `CLAUDE_CODE_OAUTH_TOKEN`: the task keeps
  them; reading needs nothing more.
- The write tools the Action's comment mode grants by itself (file edits, `git add`,
  `git commit`, its push script): the Action's default, whether a push succeeds depends
  on the GitHub App's rights, and closing it would also stop `@claude` from making a
  change asked for in a comment. A BACKLOG.md entry, not this task.
- A full review of every file of the diff: the human's decision of 2026-10-23 (#949):
  texts stay read locally.
- The sdlc kit's `review-loop` (another repository): it has no notion of coverage; the
  project's **External reviewer** settings are where a project says what its reviewer's
  answer holds, so the kit needs no change.
- `docs/epics/` (epic LAD-116 runs in parallel), `src/`, `web/`: not touched.
- A CHANGELOG.md line and a version bump: nothing a user of LADO sees changes.
- More turns for the Action (`--max-turns`): not asked; the instruction's order (risky
  code first) and the lists make a short budget visible instead of hidden.

## Acceptance criteria

- AC-1: The checkout of `claude.yml` has `fetch-depth: 0` (unit test).
- AC-2: `claude_args` allows exactly `Bash(git diff:*)`, `Bash(git log:*)` and
  `Bash(gh pr diff:*)` and no other tool; the job's `permissions` are exactly
  `contents`, `pull-requests`, `issues`, `actions` read and `id-token` write, as before;
  the Action has no `prompt` input (unit tests).
- AC-3: The appended instruction names `origin/main...HEAD`, the four kinds of risky code,
  the headings `Files read` and `Files not read`, and the line `Risky code not fully
  read` (unit test).
- AC-4: `actionlint` reports nothing on `.github/workflows/claude.yml`; `make lint` and
  `make test` pass; CI is green on the pull request's last commit.
- AC-5: After the merge, a `@claude review` on the next pull request answers with both
  lists at the end and every risky file of its diff under `Files read` (or the line
  `Risky code not fully read` with those files first under `Files not read`). Checked by
  hand on that pull request; the workflow of an `issue_comment` comes from the default
  branch, so this pull request's own `@claude` still runs the old setup.

## Impact

- No change to LADO's code, CLI, MCP or API; no schema migration; no version bump, no
  CHANGELOG.md line.
- Neutral core: not touched; the workflow concerns the repository's CI only.
- Living spec: `repository-security`, one requirement added.
