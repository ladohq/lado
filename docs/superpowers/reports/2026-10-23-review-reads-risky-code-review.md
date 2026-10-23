# LAD-133 review-reads-risky-code: review report

Pull request #149 `fix/lad-133-review-reads-risky-code` → `main`. Scale: tweak, reviewed
by precision. Head reviewed last: `c1013be` (merge base with main `8b920dd`). Only the
Claude Code workflow (`.github/workflows/claude.yml`), its unit test, `.lado/sdlc.md`,
`docs/testing.md`, BACKLOG.md and the change changed; `src/` and `web/` did not, and
neither did `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`, so no live tests were needed. The workflow was read in full as
security code.

## Rounds

- **Round 1, local** (`8b920dd..c1013be`, the whole pull request): the diff of all 9
  files, the change's spec and the tests. Checked against the pinned Action's source
  (`parse-sdk-options.ts`, `modes/tag/index.ts`, `fetch-depth.ts` at `1d6de8c`):
  `--allowedTools` of `claude_args` is merged with the mode's list, not put in its place;
  `--append-system-prompt` reaches the CLI; shell-quote 1.8.1 splits `claude_args` into
  exactly 4 arguments, the multi-line instruction stays one value. The example paths of
  the instruction exist. Five mutated copies of the workflow (`fetch-depth: 1`, an extra
  `Bash(git push:*)`, the flag `--allowed-tools`, a `prompt` input, a lost
  `Files not read`) were each caught by the tests.
- **Round 1, external** (Claude Code GitHub Action; request 07:41:47Z, "Claude finished"
  07:42:48Z): it still ran main's old setup, so `git diff origin/main...HEAD` failed with
  `no merge base`, the very cause this pull request fixes; it compared `8b920dd..c1013be`
  directly. Files read: `claude.yml`, `test_workflow_security.py`, `.lado/sdlc.md`,
  `BACKLOG.md`, `docs/testing.md` (the one risky file read); Files not read: the 4
  openspec files (texts, read locally). The answer to its findings is in the pull
  request (issuecomment-6360055527). It is of the same model family, so its "nothing
  more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the instruction fixes `origin/main...HEAD`, the wrong base for a pull request into an epic branch | confirmed | minor | declined: the task sets it; the last 40 pull requests all target `main`; the comment's request may replace the range |
| E1 | 1 | external | after `fetch-depth: 0` the Action may make the clone shallow again (`fetch --depth`) | refuted: `fetch-depth.ts@1d6de8c` adds `--depth` only for a shallow repository | — | dropped |
| E2a | 1 | external | `git diff --no-index` opens a new way to read any file | refuted: the comment mode already allows `Read` on any path (`tagModeTools`) | — | dropped |
| E2b | 1 | external | `git diff --output=<path>` may write a file outside the workspace | unverifiable without a run | — | residual risk |
| E3 | 1 | external | `tools - READING == set()` repeats `tools == READING` in the test | confirmed | minor | declined: harmless, gives the "extra tools" message |
| E4 | 1 | external | texts end up under `Files not read` | refuted: steps 3 and 4 of the instruction agree | — | dropped |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 1 (F1), refuted 0;
external confirmed 1 (E3), refuted 3 (E1, E2a, E4), unverifiable 1 (E2b). Findings in
code changed by the developer's cleanup: 0.

## Checks

- `uv run pytest tests/test_workflow_security.py`: 17 passed.
- `make lint`: clean. `actionlint` 1.7.12 (mise): clean.
- `openspec validate review-reads-risky-code --strict`: valid; `openspec validate --specs
  --strict`: 46 of 46 after the archive.
- CI on `c1013be`: 23 of 23 success.
- Not run by the reviewer: the full `make test` (the developer's 3971 passed, CI green);
  integration and UI tests not touched.

## Not checked

- AC-5 only after the merge: an `issue_comment` workflow comes from the default branch.
  On the next pull request `@claude review` must end with `Files read` / `Files not
  read`, every risky file of its diff under `Files read`.
- E2b: whether `git diff --output=` can write outside the workspace; the added risk is
  small (the mode already has `git commit` and Edit in the workspace, and only the
  repository's people start it). To be decided with the BACKLOG entry "The `@claude`
  reviewer may edit files and commit".
- The Action's live parsing of `claude_args`, checked only by its source and shell-quote.
