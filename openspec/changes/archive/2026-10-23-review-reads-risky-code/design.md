## Context

Facts of the pinned Action (`anthropics/claude-code-action@1d6de8c`, v1.0.248), read in
its source at that commit:

- `src/modes/detector.ts`: a comment event with a `prompt` input runs in the automation
  mode; without it, in the comment ("tag") mode, which posts and updates the progress
  comment that ends with "Claude finished".
- `src/modes/tag/index.ts`: the comment mode allows `Glob`, `Grep`, `LS`, `Read`, its own
  GitHub tools and git's `add`/`commit`/`rm` and its push script, with
  `--permission-mode acceptEdits`, then appends the user's `claude_args`.
- `base-action/src/parse-sdk-options.ts`: every `--allowedTools` of `claude_args` is
  merged with the mode's list, not put in its place.
- `src/github/operations/fetch-depth.ts`: on a complete checkout the Action fetches the
  pull request's branch without `--depth`, so the merge base with `origin/main` stays.
- `src/entrypoints/run.ts`: `GH_TOKEN` is set for Claude's session, so `gh pr diff` works.
- `docs/migration-guide.md`: `claude_args: --append-system-prompt "…"` is the documented
  way of standing instructions; it keeps Claude Code's own system prompt.

## Decisions

### D1. The instruction goes in `claude_args`, not in `prompt`

`claude_args` carries `--allowedTools "Bash(git diff:*),Bash(git log:*),Bash(gh pr diff:*)"`
and `--append-system-prompt "<instruction>"`, as a YAML block scalar (`|`). No `prompt`:
it would switch the comment event to the automation mode (Context) and the project's
**External reviewer** could no longer see a round finish. The commented-out boilerplate
of `prompt` and `claude_args` in the workflow goes; a comment above `claude_args` says why
there is no `prompt`.

### D2. What the standing instruction says

Written in English, in the project's own words (clean-room), at most about 25 lines:

1. It applies when the request is a review of a pull request; on an issue, or a request
   that is not a review, it does nothing. The comment's request may narrow it (e.g. "only
   the delta `<a>..<b>`") or extend it; the request wins.
2. Get the changed files with `git diff --stat origin/main...HEAD` (or `gh pr diff`).
3. Read risky code first, every changed line of it and enough around it to judge it.
   Risky code is decided by its kind; the paths are this repository's examples:
   - security and secrets: `src/lado/server/auth.py`, `src/lado/mcp_exec.py`,
     `.github/workflows/`, `docker/`;
   - deleting data: `src/lado/uninstall.py`, `src/lado/self_update.py`, migrations in
     `src/lado/state.py`, removal in `src/lado/projects.py` and `src/lado/runtime.py`;
   - agents' environment: `src/lado/agent_env.py`, `src/lado/providers/`,
     `src/lado/hooks.py`, `src/lado/runtime.py`;
   - the server's API: `src/lado/server/`.
4. Then the rest of the code as far as the run allows. Texts (specs, docs, tests,
   `web/openapi.json`, generated files) are read locally by the project; read them only
   when the request asks.
5. End the answer with two lists of paths: `Files read` and `Files not read` (each file of
   the diff in exactly one). When a risky file is not read in full, put
   `Risky code not fully read` at the top of the answer and those files first under
   `Files not read`, marked `(risky)`.

The headings are fixed strings so that the reviewer and the unit test can find them.

### D3. The unit test reads the workflow, not the Action

`tests/test_workflow_security.py` (unit layer: the workflow is a file, nothing crosses a
process) loads `claude.yml` with the existing `claude` fixture and checks:

- the checkout step's `with.fetch-depth == 0`;
- the Action's step has no `prompt`;
- `claude_args` split with `shlex.split`: the values of every `--allowedTools` /
  `--allowed-tools`, split on `,`, are exactly the three reading commands; no
  `--dangerously-skip-permissions`, `--permission-mode` or `--disallowedTools` that
  changes the mode's set (only the two flags of D1 are present);
- the `--append-system-prompt` value contains `origin/main...HEAD`, `Files read`,
  `Files not read`, `Risky code not fully read`;
- the job's `permissions` equal `{contents: read, pull-requests: read, issues: read,
  id-token: write, actions: read}`.

A failing check names what it found (the extra tool, the input), as the pinning test
does. Each new test fails on today's `claude.yml`.

### D4. `actionlint` through mise

The repository has no `actionlint`; the developer runs it with
`mise exec actionlint@1.7.12 -- actionlint .github/workflows/claude.yml` (installed
into the home volume, no version file added; on today's file it reports nothing). When mise cannot get it, a YAML load
of the file (the unit tests do it) and CI stand in, and `build-report` says so.

### D5. Coverage is the answer's lists

`.lado/sdlc.md`, **External reviewer**, gets a line after "Finished": coverage of a round
is taken from the lists `Files read` / `Files not read` at the end of Claude's comment; a
risky file of the diff that is not under `Files read` was not reviewed externally. The
human keeps that file and agreed to the line (question #1129). The sdlc kit is not
changed (proposal, Out of scope).

## Risks

- The new setup runs only from the default branch (`issue_comment` workflows): this pull
  request's own `@claude` round still runs the old one. AC-5 is checked by hand on the
  next pull request; a miss there is fixed in a pull request of its own.
- A model may still ignore the instruction; the fixed headings make that visible at once.
