# LAD-313 commit-author-nobody-left: review report

Pull request #363 `fix/lad-313-commit-author-nobody-left` → `main`. Scale: tweak. Head
reviewed: `7865bf9f`. A clear or a show of a commit author (LADO's, a git server's, a
project's) that leaves nobody to sign agents' commits now says agents cannot commit and how
to set an author, and a clear ends with `Running agents keep the author they started with
until they restart.` instead of the restart promise. Where an author is left, the output is
unchanged.

## Rounds

1. Local, precision, `origin/main...7865bf9f` (src, tests, docs, CHANGELOG, openspec) and a
   check against the spec: F1 minor declined.
   External 1, Claude Code GitHub Action (request 10:23:41Z, "Claude finished" 10:24:38Z):
   read `cli.py`, `commit_authors.py`, `git_servers.py`, every risky file; not the tests or
   docs, read locally. F2, F4 minor declined, F3 refuted.

External rounds used: 1 of 1.

## Findings

| ID | Finding | Level | Outcome |
|---|---|---|---|
| F1 | The `--help` of `lado project author --clear` still says agents commit as LADO's or a git server's author | minor | declined: help text only, the command's output is right |
| F2 | `PROJECT_AUTHOR_NONE` is inexact when only git's own author signs | minor | declined: an older text, AC-5 keeps the output unchanged; can be fixed with F1 |
| F3 | A server is judged at `/`, missing a repository's local `user.*` | — | refuted: design D3, documented in docs/cli.md |
| F4 | `_lado_author` recognises "nobody" by comparing lines with `LADO_NOBODY` | minor | declined: right now, a test guards it |

Metrics: 1 local round, 1 external, 0 substitute; 1 local finding confirmed (minor), 2
external confirmed (minor), 1 refuted; no fixing commits; 0 findings in code changed by the
developer's clean-up.

## Checks at `7865bf9f`

- `make lint`: clean
- `make test`: 6258 passed, 14 skipped
- `openspec validate commit-author-nobody-left --strict`: valid; trial archive and `openspec
  validate --specs --strict`: 92 passed
- CI: 27/27 pass, `ci-ok` pass, `mergeStateStatus: CLEAN`

## Not checked, residual risk

- Not run locally: integration, UI, smoke, container; CI ran them, and the diff crosses no
  process.
- `GIT_AUTHOR_*` variables of the agents' environment are not counted in "nobody signs"
  (out of scope; the launch warns of them, LAD-312).
- `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
  unchanged: no live tests needed before the merge.

Found on the way: none.
