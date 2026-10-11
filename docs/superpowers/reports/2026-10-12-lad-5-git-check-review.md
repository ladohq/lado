# LAD-5 lad-5-git-check: review report

Pull request #1 `fix/lad-5-git-check` → `main`. Scale: tweak, review depth: precision.
Head reviewed last: `6ff6c50`; the archive commit follows it.

## Rounds

- **Round 1** (`origin/main...af20260`): local breadth review (spec, tests, silent
  failures, comments, types, general, architecture against AGENTS.md) and an external
  round by a stand-in agent, as the Claude Code Action was not installed yet
  (https://github.com/ladohq/lado/pull/1#issuecomment-6113559217).
- **Round 2** (`af20260..e0fe67f`, only the merge of `main` with the Action's workflow):
  precision, and a real external round by the Claude Code Action, which the human asked
  for at `merge_ok` beyond the tweak's cap of one external round
  (https://github.com/ladohq/lado/pull/1#issuecomment-6113865909). No blockers, no
  important findings; F8–F11.
- **Round 3** (`e0fe67f..6ff6c50`, specs only): after the first archive failed
  (`openspec archive` wrote a placeholder `## Purpose` into the two new capabilities, which
  `openspec validate --specs --strict` refuses), the deltas got their Purpose and F2 was
  fixed. The archive and the strict validation were reproduced on a throwaway copy.
  No external round: the cap was spent and the delta has no code.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | external (stand-in) | `repo_root` turns a `no_git` `FolderProblem` into "not inside a git repository" | confirmed | minor | declined: both callers turn the error into None, no one sees the text |
| F2 | 1 | local: spec | The spec did not name the Linux command of the `git_broken` hint | confirmed | minor | fixed in `6ff6c50` |
| F3 | 1 | external (stand-in) + local: tests | Any stderr of `rev-parse --verify --quiet HEAD` reads as `git_refused` (e.g. with `GIT_TRACE`); no test of that branch | confirmed | minor | declined: rare, git's line is shown |
| F4 | 1 | local: reading | `FolderHint` without a `key` keeps "Press ⌘C" when moving to another hinted folder | confirmed | minor | declined: only when every copy path failed |
| F5 | 1 | external (stand-in) | Only the CLI and `GET /api/folders` show the hint | confirmed | minor | declined: the spec says so (D7) |
| F6 | 1 | external (stand-in) | The `no_git` text shows the server's PATH in the API | refuted | — | the spec's text; the API is behind the token |
| F7 | 1 | external (stand-in) | The `not_repo` hint's `git add -A` is risky for a folder picked by mistake | refuted | — | the spec's text, approved at design_ok |
| F8 | 2 | external (Action) | `check_git()` takes no `which` | refuted | — | D2: the same look as the folder check |
| F9 | 2 | external (Action) | An unparsable version is `OK` | refuted | — | D9 |
| F10 | 2 | external (Action) | No cache in `git_version`; the macOS stub may show its install dialog at each folder check | unverifiable | minor | declined: D2; the old code ran git at each check too; no Mac without the tools at hand |
| F11 | 2 | external (Action) | Another `OSError` in `_run_git` is a `LadoError` without a kind | refuted | — | D4; unreachable from `check_repo` |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 2 (F2, F4) | 0 | — |
| external, stand-in | 3 (F1, F3, F5) | 2 (F6, F7) | — |
| external, Claude Code Action | 0 | 3 (F8, F9, F11) | 1 (F10) |

No blocker or important finding in any round.

## Checks

- On `af20260`: `make lint` clean, `make test` 2343 passed, `make web` 621 vitest passed,
  UI e2e 10 passed.
- On `6ff6c50`: lint clean, `make test` 2343 passed, `openspec validate lad-5-git-check
  --strict` valid; CI green (check 3.10/3.13, ui, js, smoke on Linux and macOS for claude,
  codex, kilo, opencode).
- At archive: `openspec validate --specs --strict` 2 passed, 0 failed.

## Residual risk

- Live tests were not run, though `runtime.py` and `providers/gitpaths.py` changed; the
  smoke passed in CI on Linux and macOS.
- The real macOS git stub and a real "dubious ownership" were checked only with a fake
  `git` script; F10 could not be checked.
