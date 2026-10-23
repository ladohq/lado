# LAD-138 project-page: review report

Pull request #157 `feature/lad-138-project-page` → `main`. Scale: full, reviewed breadth
first. Head reviewed last: `a96b79e9` (= the remote head). `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged: no live tests
needed before the merge.

## Rounds

- **Round 1** (`origin/main..12b352af`): a local breadth pass (spec, tests, silent
  failures, comments, types, general, the architecture against AGENTS.md); every
  requirement and scenario of the delta has code and a test, `tasks.md` 1.1-4.2 checked,
  D1-D17 kept. **External 1** (Claude Code GitHub Action, request 6372717792, answer at
  19:12:06Z): X1-X5. Coverage of #949 in full: `unpushed`, `_checkout_lines`, `removal`,
  `remove_repo`, the removal/DELETE/PATCH routes, `ProjectRepos.tsx`, `cloneJob.ts`, the
  diff of `Launch.tsx`, `TitleEdit.tsx`.
- **Round 2** (`12b352af..a96b79e9`, one commit): a local precision pass over the fix
  (the root is added past `listed` only when `own`; a root `.git` file, a worktree, takes
  no neighbours; `_GitFailed` is swallowed and the root's line says `could not check`).
  **External 2** (request 6372974216, answer at 19:26:19Z): no finding. Risky files not
  reread: unchanged since round 1.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"nothing more" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| X1 | 1 | external 1 | `unpushed`: a worktree inside a project folder that is itself a repository was listed twice | confirmed | important | fixed in `a96b79e9`, `test_a_worktree_of_the_project_folder_inside_it_is_listed_once` red on the old code |
| X2 | 1 | external 1 | the docstring of `_checkouts` did not match the code | confirmed | minor | fixed in `a96b79e9` |
| X3 | 1 | external 1 | the removal preview can go stale: `DELETE` does not recheck the confirmed unpushed work | confirmed | minor | declined: the CLI works the same (preview, then `--yes`); one core function (D9, D11) |
| X4 | 1 | external 1 | a stopped session of another project with a folder inside the repository is not forgotten | refuted: by D9 a session of another project is never matched by its path; running sessions of any project block the removal | — | dropped |
| X5 | 1 | external 1 | Add repository keeps the previous URL's name after a failed URL | confirmed | minor | declined: cosmetic, Clone stays disabled without a branch list |
| F1 | 1 | local | Back inside the app during an Add repository clone does not cancel the job (AC-6) | confirmed | minor | declined: the spec names the `pagehide` beacon, which is there; the server cancels it after 150 s |
| F2 | 1 | local | a project folder that is itself a repository always shows `uncommitted changes` | confirmed | minor | declined: pinned by a test, says more not less (D10) |
| F3 | 1 | local | a late Cancel clone closes Add repository silently as a success | confirmed | minor | declined: a race; the new row is shown |
| F4 | 1 | local | the Sessions block labels a `tmux_gone` session `running` | confirmed | minor | declined: by D8 other statuses go with running ones; only the label differs |

Metrics: 2 local rounds, 2 external, 0 substitutes. Local confirmed 4 (all minor);
external confirmed 4 (1 important, 3 minor), refuted 1. Findings in code changed by the
developer's cleanup: 0. The important finding has a test seen red.

## Checks

- `12b352af`: `make lint` green; `make test` 4203 passed, 2 skipped; `make web` (vitest
  1089 passed); `-m ui` on 5 files: 64 passed; openspec change valid, specs 47 of 47.
- `a96b79e9`: `make lint` green; `make test` 4204 passed, 2 skipped; `openspec validate
  project-page --strict` valid; CI run 40009922368, `ci-ok` green.
- The epic lead's checks (#1361): the window's clone tests unchanged, the canary
  untouched, #949 coverage full, the path guards of `remove_repo` and `delete` unchanged
  and tested, `LADO_TELEMETRY=0` in `docs/release.md`.
- At archive: `openspec validate --specs --strict` 47 of 47.

## Found on the way

- Nothing outside the scope.

## Not checked

- Locally: `make test-integration`, `make check` as a whole, `make test-js`, smoke and
  live; CI ran the integration layer, the UI and the smoke green.
- After `a96b79e9` `make web` and the UI tests were not rerun locally: `web/` and
  `tests/ui/` did not change; the UI shards of CI were green.
- The external reviewer did not read the tests, the documents and the CSS.
